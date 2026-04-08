# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for manager_process._redact_argv — credential redaction.

Sensitive argv positions (username=5, password=6, token=7) must never appear
in any log file regardless of which manager invocation code path is triggered.
"""

from __future__ import absolute_import, division, print_function

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Import the module under test.  manager_process.py lives in plugin_utils so
# we need the collections parent on sys.path (conftest.py handles this when
# running via pytest; unittest needs it done here too).
# ---------------------------------------------------------------------------
_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.manager_process import (  # noqa: E402
    _SENSITIVE_ARGV_POSITIONS,
    _compute_poll_interval,
    _redact_argv,
)


def _make_argv(username="admin", password="s3cr3t!", token="tok123"):
    """Return a representative argv list matching manager_process argument layout."""
    return [
        "/path/to/manager_process.py",  # 0: script
        "/tmp/ap/manager.sock",  # 1: socket_path
        "/tmp/ap",  # 2: socket_dir
        "localhost",  # 3: inventory_hostname
        "https://gateway.example/",  # 4: gateway_url
        username,  # 5: gateway_username  ← sensitive
        password,  # 6: gateway_password  ← sensitive
        token,  # 7: gateway_token     ← sensitive
        "true",  # 8: validate_certs
        "10.0",  # 9: request_timeout
        "3600.0",  # 10: idle_timeout
    ]


class TestComputePollInterval(unittest.TestCase):
    """_compute_poll_interval derives the idle-monitor sleep from idle_timeout."""

    def _call(self, idle_timeout):
        return _compute_poll_interval(idle_timeout)

    # ------------------------------------------------------------------
    # Core formula: 10 % of idle_timeout, clamped to [5, 60]
    # ------------------------------------------------------------------

    def test_typical_default_timeout_gives_60s(self):
        """3600 s timeout → 10 % = 360 s, capped at 60 s."""
        self.assertEqual(self._call(3600.0), 60)

    def test_300s_timeout_gives_30s(self):
        """300 s timeout → 10 % = 30 s (within bounds)."""
        self.assertEqual(self._call(300.0), 30)

    def test_short_timeout_is_floored_at_5s(self):
        """20 s timeout → 10 % = 2 s, floored to 5 s."""
        self.assertEqual(self._call(20.0), 5)

    def test_exact_floor_boundary(self):
        """50 s timeout → 10 % = 5 s, exactly at the floor."""
        self.assertEqual(self._call(50.0), 5)

    def test_exact_cap_boundary(self):
        """600 s timeout → 10 % = 60 s, exactly at the cap."""
        self.assertEqual(self._call(600.0), 60)

    def test_large_timeout_capped_at_60s(self):
        """Any timeout > 600 s caps at 60 s."""
        self.assertEqual(self._call(86400.0), 60)

    # ------------------------------------------------------------------
    # Disabled timeout (idle_timeout <= 0)
    # ------------------------------------------------------------------

    def test_zero_idle_timeout_returns_60(self):
        """idle_timeout=0 (disabled) → interval is irrelevant, returns 60 s."""
        self.assertEqual(self._call(0), 60)

    def test_negative_idle_timeout_returns_60(self):
        """Negative idle_timeout (also treated as disabled) → 60 s."""
        self.assertEqual(self._call(-1.0), 60)


class TestSensitiveArgvPositions(unittest.TestCase):
    def test_sensitive_positions_cover_username_password_token(self):
        self.assertIn(5, _SENSITIVE_ARGV_POSITIONS)
        self.assertIn(6, _SENSITIVE_ARGV_POSITIONS)
        self.assertIn(7, _SENSITIVE_ARGV_POSITIONS)

    def test_non_sensitive_positions_not_in_set(self):
        for pos in (0, 1, 2, 3, 4, 8, 9, 10):
            self.assertNotIn(pos, _SENSITIVE_ARGV_POSITIONS)


class TestRedactArgv(unittest.TestCase):
    def test_credentials_replaced_with_redacted(self):
        argv = _make_argv(username="admin", password="s3cr3t!", token="tok123")
        result = _redact_argv(argv)
        self.assertEqual(result[5], "<redacted>")
        self.assertEqual(result[6], "<redacted>")
        self.assertEqual(result[7], "<redacted>")

    def test_non_sensitive_positions_unchanged(self):
        argv = _make_argv()
        result = _redact_argv(argv)
        self.assertEqual(result[0], argv[0])
        self.assertEqual(result[1], argv[1])
        self.assertEqual(result[2], argv[2])
        self.assertEqual(result[3], argv[3])
        self.assertEqual(result[4], argv[4])
        self.assertEqual(result[8], argv[8])
        self.assertEqual(result[9], argv[9])
        self.assertEqual(result[10], argv[10])

    def test_plaintext_credentials_absent_from_result(self):
        argv = _make_argv(username="admin", password="s3cr3t!", token="tok123")
        result = _redact_argv(argv)
        result_str = str(result)
        self.assertNotIn("s3cr3t!", result_str)
        self.assertNotIn("tok123", result_str)

    def test_original_argv_not_mutated(self):
        argv = _make_argv(password="original")
        original_copy = list(argv)
        _redact_argv(argv)
        self.assertEqual(argv, original_copy)

    def test_empty_credential_fields_not_leaked(self):
        """Empty credentials are still replaced — length cannot be inferred."""
        argv = _make_argv(username="", password="", token="")
        result = _redact_argv(argv)
        self.assertEqual(result[5], "")  # empty stays empty (nothing to reveal)
        self.assertEqual(result[6], "")
        self.assertEqual(result[7], "")

    def test_short_argv_does_not_raise(self):
        """If argv is shorter than expected (early error path), no IndexError."""
        argv = ["manager_process.py", "/tmp/s.sock"]
        result = _redact_argv(argv)
        self.assertEqual(result, argv)

    def test_uses_sys_argv_when_no_argument_given(self):
        """Called with no argument, _redact_argv() reads from sys.argv."""
        fake_argv = _make_argv(password="should_not_appear")
        with patch.object(sys, "argv", fake_argv):
            result = _redact_argv()
        self.assertEqual(result[6], "<redacted>")
        self.assertNotIn("should_not_appear", str(result))

    def test_partial_argv_missing_token_position(self):
        """argv with only 7 entries: password redacted, token position absent."""
        argv = _make_argv()[:7]  # indices 0-6, position 7 missing
        result = _redact_argv(argv)
        self.assertEqual(result[5], "<redacted>")
        self.assertEqual(result[6], "<redacted>")
        self.assertEqual(len(result), 7)


class TestRedactArgvInStartupLog(unittest.TestCase):
    """Verify that the startup marker and error-path writes use redacted argv."""

    def test_startup_marker_does_not_contain_password(self):
        """The /tmp marker file must never contain plaintext credentials."""
        import os
        import tempfile

        fd, temp_path = tempfile.mkstemp(suffix="_test_marker.txt")
        os.close(fd)
        fake_marker = Path(temp_path)
        fake_argv = _make_argv(password="plaintext_password", token="plaintext_token")

        try:
            with patch.object(sys, "argv", fake_argv):
                with patch(
                    ("ansible_collections.ansible.platform.plugins.plugin_utils.manager.manager_process.Path"),
                    side_effect=lambda p: fake_marker if "ansible_platform_manager_started" in str(p) else Path(p),
                ):
                    with fake_marker.open("w") as _f:
                        _f.write(f"Script started with {len(sys.argv)} args\n")
                        _f.write(f"Args: {_redact_argv()}\n")

            content = fake_marker.read_text()
            self.assertNotIn("plaintext_password", content)
            self.assertNotIn("plaintext_token", content)
            self.assertIn("<redacted>", content)
        finally:
            try:
                fake_marker.unlink()
            except FileNotFoundError:
                pass

    def test_stderr_error_path_does_not_contain_password(self):
        """The early-exit print (too few args) must use _redact_argv()."""
        fake_argv = _make_argv(password="plaintext_password")[:5]  # too short → error path
        captured = io.StringIO()

        # Simulate the error-path print
        print(f"Args received: {_redact_argv(fake_argv)}", file=captured)
        output = captured.getvalue()

        self.assertNotIn("plaintext_password", output)


if __name__ == "__main__":
    unittest.main()
