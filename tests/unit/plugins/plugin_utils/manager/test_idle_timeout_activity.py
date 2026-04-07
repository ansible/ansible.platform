# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests proving that _authenticate() / _re_authenticate() / _refresh_token()
do NOT call record_activity(), leaving the idle monitor blind to auth work.

These are regression tests for a blocking review comment on PR #152.
Run against the unpatched branch: all tests marked FAIL should fail.
After adding `self.record_activity()` inside each auth method: all pass.
"""

from __future__ import absolute_import, division, print_function

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Minimal stub that replicates only the idle-relevant state of PlatformService
# so we can test _authenticate(), _re_authenticate(), _refresh_token() without
# starting a real HTTP session or connecting to a gateway.
# ---------------------------------------------------------------------------


def _make_service_stub():
    """Return a PlatformService instance with all heavy __init__ work bypassed.

    We define record_activity / seconds_since_last_activity / should_exit_for_idle
    directly on the stub so the test is self-contained regardless of which branch
    of platform_manager.py is under test.
    """
    from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService

    # Bypass __init__ entirely — we'll set up only what the auth methods need
    svc = object.__new__(PlatformService)

    # Minimal state required by the idle-tracking methods below
    svc._activity_lock = threading.Lock()
    svc._last_activity_monotonic = time.monotonic()
    svc._shutdown_requested = False
    svc._shutdown_lock = threading.Lock()

    # Minimal state required by _authenticate()
    svc._auth_lock = threading.Lock()
    svc._last_auth_error = None
    svc.request_timeout = 10.0
    svc.verify_ssl = True
    svc.base_url = "https://gateway.test.invalid"

    # Fake session that always returns HTTP 200
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.raise_for_status = MagicMock()
    fake_session = MagicMock()
    fake_session.get.return_value = fake_response
    fake_session.post.return_value = fake_response
    svc.session = fake_session

    # Fake credential store — returns username/password, no oauth token
    fake_store = MagicMock()
    fake_store.get_auth_credentials.return_value = ("testuser", "testpassword", None)
    fake_store.token_info = None
    svc.credential_store = fake_store

    # ---------------------------------------------------------------------------
    # Bind idle-tracking methods directly on the instance so the test is
    # self-contained and doesn't depend on which version of PlatformService is
    # being imported.
    # ---------------------------------------------------------------------------
    import types

    def _record_activity(self):
        with self._activity_lock:
            self._last_activity_monotonic = time.monotonic()

    def _seconds_since_last_activity(self):
        with self._activity_lock:
            return time.monotonic() - self._last_activity_monotonic

    def _should_exit_for_idle(self):
        if self.config.idle_timeout <= 0:
            return False
        with self._shutdown_lock:
            if self._shutdown_requested:
                return False
        return self.seconds_since_last_activity() >= self.config.idle_timeout

    svc.record_activity = types.MethodType(_record_activity, svc)
    svc.seconds_since_last_activity = types.MethodType(_seconds_since_last_activity, svc)
    svc.should_exit_for_idle = types.MethodType(_should_exit_for_idle, svc)

    return svc


class TestAuthenticateDoesNotRecordActivity(unittest.TestCase):
    """_authenticate() must call record_activity() so the idle monitor sees auth work."""

    def test_authenticate_resets_idle_clock(self):
        """After _authenticate() the idle clock should be reset (record_activity called).

        FAILS on unpatched code — passes after `self.record_activity()` is added
        to the end of _authenticate().
        """
        svc = _make_service_stub()

        # Wind the clock back so seconds_since_last_activity is clearly non-zero
        svc._last_activity_monotonic = time.monotonic() - 500.0

        before = svc.seconds_since_last_activity()
        self.assertGreater(before, 400, "Pre-condition: idle gap should be > 400s")

        # Run _authenticate() — with patched requests so no real network call
        with patch(
            "ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager._get_requests",
            return_value=MagicMock(),
        ):
            svc._authenticate()

        after = svc.seconds_since_last_activity()

        # If record_activity() was called the clock should have reset to ~0
        self.assertLess(
            after,
            5.0,
            f"_authenticate() did not reset the idle clock. seconds_since_last_activity={after:.1f}s — record_activity() was never called.",
        )

    def test_authenticate_calls_record_activity(self):
        """record_activity() should be invoked exactly once by _authenticate().

        Uses a spy so the failure message is unambiguous.
        FAILS on unpatched code.
        """
        svc = _make_service_stub()
        svc.record_activity = MagicMock(wraps=svc.record_activity)

        with patch(
            "ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager._get_requests",
            return_value=MagicMock(),
        ):
            svc._authenticate()

        svc.record_activity.assert_called_once_with()


class TestReAuthenticateDoesNotRecordActivity(unittest.TestCase):
    """_re_authenticate() wraps _authenticate() — the idle clock must reset here too."""

    def test_re_authenticate_resets_idle_clock(self):
        """After _re_authenticate() succeeds the idle clock should be reset.

        FAILS on unpatched code.
        """
        svc = _make_service_stub()
        svc._last_activity_monotonic = time.monotonic() - 500.0

        with patch(
            "ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager._get_requests",
            return_value=MagicMock(),
        ):
            result = svc._re_authenticate()

        self.assertTrue(result, "_re_authenticate() should return True on success")

        after = svc.seconds_since_last_activity()
        self.assertLess(
            after,
            5.0,
            f"_re_authenticate() did not reset the idle clock. seconds_since_last_activity={after:.1f}s",
        )


class TestRefreshTokenDoesNotRecordActivity(unittest.TestCase):
    """_refresh_token() performs a real HTTP call — the idle clock must reset on success."""

    def test_refresh_token_resets_idle_clock(self):
        """After a successful token refresh the idle clock should be reset.

        FAILS on unpatched code.
        """
        svc = _make_service_stub()
        svc._last_activity_monotonic = time.monotonic() - 500.0

        # Give the store a real token_info so _refresh_token doesn't bail early
        fake_token_info = MagicMock()
        fake_token_info.refresh_token = "old_refresh_token"
        svc.credential_store.token_info = fake_token_info

        # Simulate a successful refresh response
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
        }
        svc.session.post.return_value = fake_response

        result = svc._refresh_token()

        self.assertTrue(result, "_refresh_token() should return True on success")

        after = svc.seconds_since_last_activity()
        self.assertLess(
            after,
            5.0,
            f"_refresh_token() did not reset the idle clock. seconds_since_last_activity={after:.1f}s — record_activity() was never called.",
        )


class TestIdleTimeoutNotFiredDuringAuthWork(unittest.TestCase):
    """End-to-end: a manager that only re-authenticates must not be considered idle."""

    def test_should_not_exit_immediately_after_authenticate(self):
        """should_exit_for_idle() must return False right after _authenticate().

        Simulates the race: last real API call was 500s ago, then _authenticate()
        fires. If _authenticate() doesn't call record_activity(), the idle monitor
        sees 500s of inactivity and kills the manager.

        FAILS on unpatched code with idle_timeout=300.
        """
        svc = _make_service_stub()

        # Simulate a tight idle_timeout
        svc.config = MagicMock()
        svc.config.idle_timeout = 300.0  # 5 minutes

        svc._shutdown_requested = False
        svc._shutdown_lock = threading.Lock()

        # Wind clock back: last real API call was 500s ago (beyond the timeout)
        svc._last_activity_monotonic = time.monotonic() - 500.0

        # _authenticate() fires (e.g. token refresh triggers re-auth)
        with patch(
            "ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager._get_requests",
            return_value=MagicMock(),
        ):
            svc._authenticate()

        # The idle monitor should NOT fire — manager just did real work
        self.assertFalse(
            svc.should_exit_for_idle(),
            "should_exit_for_idle() returned True even though _authenticate() just ran. This means _authenticate() does not call record_activity().",
        )


if __name__ == "__main__":
    unittest.main()
