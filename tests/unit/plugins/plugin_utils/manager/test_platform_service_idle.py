# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for PlatformService idle timeout activity tracking."""

from __future__ import absolute_import, division, print_function

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import ProcessManager
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig, extract_gateway_config


def _make_platform_service():
    """PlatformService with network and credentials mocked."""
    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {}
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mock_requests = MagicMock()
    mock_requests.Session.return_value = mock_session
    mock_store = MagicMock()
    mock_store.get_auth_credentials.return_value = ("admin", "admin", None)
    with patch("ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager.get_credential_manager") as mock_cred:
        mock_cred.return_value.get_or_create_store.return_value = mock_store
        with patch("ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager._get_requests") as mock_get_requests:
            mock_get_requests.return_value = mock_requests
            config = GatewayConfig(base_url="https://127.0.0.1", username="admin", password="admin", idle_timeout=30.0)
            return PlatformService(config)


class TestGatewayConfigIdle(unittest.TestCase):
    def test_gateway_config_default_idle_timeout(self):
        c = GatewayConfig(base_url="https://example.com/")
        self.assertEqual(c.idle_timeout, 3600.0)

    def test_extract_gateway_config_idle_timeout_from_task_args(self):
        c = extract_gateway_config(
            task_args={
                "gateway_url": "https://gw.example",
                "gateway_username": "a",
                "gateway_password": "b",
                "persistent_manager_idle_timeout": 7200,
            },
            host_vars={},
            required=True,
        )
        self.assertEqual(c.idle_timeout, 7200.0)

    def test_extract_gateway_config_idle_timeout_from_host_vars(self):
        c = extract_gateway_config(
            task_args={"gateway_url": "https://gw.example", "gateway_username": "a", "gateway_password": "b"},
            host_vars={"persistent_manager_idle_timeout": 1800},
            required=True,
        )
        self.assertEqual(c.idle_timeout, 1800.0)


class TestPlatformServiceIdle(unittest.TestCase):
    def setUp(self):
        self.platform_service = _make_platform_service()

    def test_should_exit_for_idle_disabled_when_zero(self):
        self.platform_service.config.idle_timeout = 0
        self.assertFalse(self.platform_service.should_exit_for_idle())

    def test_should_exit_for_idle_false_before_threshold(self):
        self.platform_service.config.idle_timeout = 1000.0
        with patch("time.monotonic", return_value=100.0):
            self.platform_service.record_activity()
        with patch("time.monotonic", return_value=200.0):
            self.assertEqual(self.platform_service.seconds_since_last_activity(), 100.0)
            self.assertFalse(self.platform_service.should_exit_for_idle())

    def test_should_exit_for_idle_true_after_threshold(self):
        self.platform_service.config.idle_timeout = 10.0
        with patch("time.monotonic", return_value=1000.0):
            self.platform_service.record_activity()
        with patch("time.monotonic", return_value=1020.0):
            self.assertTrue(self.platform_service.should_exit_for_idle())

    def test_should_exit_for_idle_false_after_shutdown_requested(self):
        self.platform_service.config.idle_timeout = 1.0
        with patch("time.monotonic", return_value=0.0):
            self.platform_service.record_activity()
        self.platform_service.shutdown()
        with patch("time.monotonic", return_value=99999.0):
            self.assertFalse(self.platform_service.should_exit_for_idle())

    def test_record_activity_updates_timestamp(self):
        with patch("time.monotonic", side_effect=[10.0, 20.0, 25.0]):
            self.platform_service.record_activity()
            self.platform_service.record_activity()
            self.assertEqual(self.platform_service.seconds_since_last_activity(), 5.0)


class TestPlatformServiceIdleTokenExpiry(unittest.TestCase):
    """Idle timeout behaviour when OAuth tokens expire.

    Key design invariant under test:
      - should_exit_for_idle() is PURELY time-based — token state is irrelevant.
      - record_activity() is called at the TOP of _make_request(), BEFORE the HTTP
        call, so even a request that returns 401 (expired token) resets the idle clock.
      - Internal token refresh / re-authentication does NOT call record_activity(),
        so background auth work never keeps the manager alive artificially.
    """

    def setUp(self):
        self.svc = _make_platform_service()

    # ------------------------------------------------------------------
    # 1. Expired token alone does not suppress idle exit
    # ------------------------------------------------------------------

    def test_expired_token_alone_does_not_suppress_idle_exit(self):
        """If the token expires passively (no incoming request), idle timeout still fires."""
        self.svc.config.idle_timeout = 10.0
        with patch("time.monotonic", return_value=1000.0):
            self.svc.record_activity()

        # Simulate the credential store reporting an expired token
        with patch.object(self.svc, "_check_token_expiration", return_value=(True, -60.0)):
            with patch("time.monotonic", return_value=1020.0):
                self.assertTrue(self.svc.should_exit_for_idle())

    def test_expired_token_does_not_prevent_idle_exit_when_no_traffic(self):
        """No requests → no record_activity() → idle fires regardless of token state."""
        self.svc.config.idle_timeout = 5.0
        with patch("time.monotonic", return_value=500.0):
            self.svc.record_activity()

        # Simulate oauth_token being wiped (e.g. after expiry) but no new request
        self.svc.oauth_token = None

        with patch("time.monotonic", return_value=510.0):
            self.assertTrue(self.svc.should_exit_for_idle())

    # ------------------------------------------------------------------
    # 2. A request that hits a 401 still resets the idle timer
    # ------------------------------------------------------------------

    def test_401_response_still_resets_idle_timer(self):
        """record_activity() fires before the HTTP call, so 401s reset the idle clock."""
        self.svc.config.idle_timeout = 10.0

        # Anchor "last activity" far in the past
        with patch("time.monotonic", return_value=0.0):
            self.svc.record_activity()

        # Mock a 401 followed by a successful retry after re-auth
        mock_401 = MagicMock()
        mock_401.status_code = 401
        mock_401.text = "Unauthorized"

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.text = ""

        self.svc.session.get = MagicMock(side_effect=[mock_401, mock_200])

        with patch.object(self.svc, "_handle_auth_error", return_value=True):
            with patch("time.monotonic", return_value=999.0):
                try:
                    self.svc._make_request("get", "https://gw/api/gateway/v1/users/")
                except Exception:
                    pass
                # record_activity() was called at t=999 inside _make_request
                self.assertAlmostEqual(self.svc.seconds_since_last_activity(), 0.0, delta=0.1)

    def test_idle_not_exceeded_immediately_after_request_with_expired_token(self):
        """After any request (even a 401 one), idle timeout should not fire until inactivity resumes."""
        self.svc.config.idle_timeout = 5.0

        with patch("time.monotonic", return_value=100.0):
            # Simulate record_activity() being called (as _make_request does at its start)
            self.svc.record_activity()

        # Only 2 s have passed since the last (simulated) request
        with patch("time.monotonic", return_value=102.0):
            self.assertFalse(self.svc.should_exit_for_idle())

    # ------------------------------------------------------------------
    # 3. should_exit_for_idle() is purely time-based
    # ------------------------------------------------------------------

    def test_should_exit_for_idle_same_result_for_valid_and_expired_token(self):
        """Token validity is invisible to should_exit_for_idle() — only elapsed time matters."""
        self.svc.config.idle_timeout = 5.0
        with patch("time.monotonic", return_value=500.0):
            self.svc.record_activity()

        with patch("time.monotonic", return_value=510.0):
            with patch.object(self.svc, "_check_token_expiration", return_value=(False, 3600.0)):
                result_valid_token = self.svc.should_exit_for_idle()
            with patch.object(self.svc, "_check_token_expiration", return_value=(True, -30.0)):
                result_expired_token = self.svc.should_exit_for_idle()

        self.assertEqual(result_valid_token, result_expired_token)
        self.assertTrue(result_valid_token, "idle timeout should have fired after 10 s > 5 s threshold")

    def test_should_exit_for_idle_false_within_threshold_regardless_of_token(self):
        """Within the idle window, should_exit_for_idle() is False even if token is expired."""
        self.svc.config.idle_timeout = 60.0
        with patch("time.monotonic", return_value=200.0):
            self.svc.record_activity()

        with patch("time.monotonic", return_value=210.0):  # only 10 s elapsed
            with patch.object(self.svc, "_check_token_expiration", return_value=(True, -5.0)):
                self.assertFalse(self.svc.should_exit_for_idle())

    # ------------------------------------------------------------------
    # 4. Internal re-auth alone does NOT reset the idle timer
    # ------------------------------------------------------------------

    def test_re_authenticate_alone_does_not_reset_idle_timer(self):
        """_re_authenticate() handles auth internally and must not extend the idle lease."""
        self.svc.config.idle_timeout = 5.0
        with patch("time.monotonic", return_value=1000.0):
            self.svc.record_activity()

        # Call _re_authenticate() without going through _make_request
        with patch.object(self.svc, "_authenticate", return_value=None):
            self.svc._re_authenticate()

        # No call to record_activity() happened, so idle should fire after threshold
        with patch("time.monotonic", return_value=1010.0):
            self.assertTrue(self.svc.should_exit_for_idle())

    def test_refresh_token_alone_does_not_reset_idle_timer(self):
        """_refresh_token() makes an HTTP call but must not extend the idle lease on its own."""
        self.svc.config.idle_timeout = 5.0
        with patch("time.monotonic", return_value=2000.0):
            self.svc.record_activity()

        # Call _refresh_token() directly (simulating an internal proactive refresh)
        with patch.object(self.svc, "_authenticate", return_value=None):
            with patch.object(self.svc.credential_store, "token_info", None):
                self.svc._refresh_token()  # returns False (no token_info) without recording activity

        with patch("time.monotonic", return_value=2010.0):
            self.assertTrue(self.svc.should_exit_for_idle())


class TestProcessManagerIdleArgv(unittest.TestCase):
    def test_spawn_manager_includes_idle_timeout_in_command(self):
        cfg = GatewayConfig(base_url="https://example.com/", username="u", password="p", idle_timeout=123.0)
        # tests/unit/plugins/plugin_utils/manager/ -> five parents up to platform/
        script = Path(__file__).resolve().parent.parent.parent.parent.parent / "plugins" / "plugin_utils" / "manager" / "manager_process.py"
        with patch("ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager.subprocess.Popen") as mock_popen:
            mock_popen.return_value.pid = 99999
            ProcessManager.spawn_manager_process(
                script_path=script,
                socket_path="/tmp/x.sock",
                socket_dir="/tmp",
                identifier="h1",
                gateway_config=cfg,
                authkey_b64="YQ==",
                sys_path=["/x"],
                owner_pid=None,
            )
        cmd = mock_popen.call_args[0][0]
        self.assertEqual(cmd[-1], "123.0")


if __name__ == "__main__":
    unittest.main()
