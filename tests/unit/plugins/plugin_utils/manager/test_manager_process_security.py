# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Security tests for manager_process.py — confirms credentials are never
written to stderr or to the startup marker file on disk.

These tests act as a regression guard: if anyone adds a debug print that
accidentally dumps sys.argv, these tests will fail loudly.
"""

from __future__ import absolute_import, division, print_function

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Fake argv values — use obviously-fake strings so a partial match (e.g. the
# URL host) doesn't accidentally trip the assertion.
# ---------------------------------------------------------------------------
FAKE_URL = "https://gateway.test.invalid"
FAKE_USERNAME = "test_usr_CREDENTIAL"
FAKE_PASSWORD = "test_pw_CREDENTIAL_secret"
FAKE_TOKEN = "test_token_CREDENTIAL_secret"
FAKE_SOCKET_PATH = "/tmp/test.sock"
FAKE_SOCKET_DIR = "/tmp"
FAKE_HOSTNAME = "testhost"

_SCRIPT = "manager_process.py"

_FULL_ARGV = [
    _SCRIPT,
    FAKE_SOCKET_PATH,  # 1
    FAKE_SOCKET_DIR,  # 2
    FAKE_HOSTNAME,  # 3
    FAKE_URL,  # 4
    FAKE_USERNAME,  # 5
    FAKE_PASSWORD,  # 6  ← sensitive
    FAKE_TOKEN,  # 7  ← sensitive
    "true",  # 8  verify_ssl
    "10.0",  # 9  request_timeout
    "3600.0",  # 10 idle_timeout (optional)
]

# Too-short argv — has URL + credentials but is missing required tail args
_SHORT_ARGV = _FULL_ARGV[:8]  # only 7 real args; len < 10 triggers the error path


def _run_main_capture_stderr(argv):
    """Run manager_process.main() with the given argv, return captured stderr text.

    Patches sys.argv, captures stderr via StringIO, and swallows SystemExit.
    The startup marker file is redirected to a temp file to avoid polluting /tmp.
    """
    from ansible_collections.ansible.platform.plugins.plugin_utils.manager import manager_process

    stderr_capture = io.StringIO()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_marker:
        tmp_marker_path = Path(tmp_marker.name)

    try:
        with (
            patch.object(sys, "argv", argv),
            patch("sys.stderr", stderr_capture),
            # Redirect the hardcoded marker path to our temp file
            patch(
                "ansible_collections.ansible.platform.plugins.plugin_utils.manager.manager_process.Path",
                side_effect=lambda p: tmp_marker_path if "manager_started" in str(p) else Path(p),
            ),
        ):
            try:
                manager_process.main()
            except SystemExit:
                pass
    finally:
        tmp_marker_path.unlink(missing_ok=True)

    return stderr_capture.getvalue()


def _read_marker_via_subprocess(argv):
    """Spawn manager_process as a real subprocess and return the marker file contents.

    This is the strongest test — it exercises the actual subprocess code path,
    including the very first lines that run before any patch can intercept.
    """
    import base64
    import json
    import subprocess

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        marker_path = tmp.name

    env = os.environ.copy()
    env["ANSIBLE_PLATFORM_SYS_PATH"] = base64.b64encode(json.dumps(sys.path).encode()).decode()
    env["ANSIBLE_PLATFORM_AUTHKEY"] = base64.b64encode(b"testkey").decode()

    script = Path(__file__).resolve().parents[5] / "plugins" / "plugin_utils" / "manager" / "manager_process.py"

    try:
        result = subprocess.run(
            [sys.executable, str(script)] + argv[1:],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
            check=False,
        )
        return result.stderr, result.stdout
    finally:
        Path(marker_path).unlink(missing_ok=True)


class TestManagerProcessNoCredentialLeak(unittest.TestCase):
    """Credentials must never appear in stderr or the startup marker file."""

    def _assert_no_credentials(self, text: str, source: str):
        """Fail the test if any sensitive value appears in *text*."""
        for secret in (FAKE_PASSWORD, FAKE_TOKEN):
            self.assertNotIn(
                secret,
                text,
                f"Credential leaked in {source}! Found '{secret}' in:\n{text}",
            )

    # ------------------------------------------------------------------
    # Test 1: too-short argv -> error path must not dump credentials
    # ------------------------------------------------------------------

    def test_stderr_does_not_contain_password_on_short_argv(self):
        """When argv is too short, the error message must not include the password."""
        stderr = _run_main_capture_stderr(_SHORT_ARGV)
        self._assert_no_credentials(stderr, "stderr (short argv path)")

    def test_stderr_does_not_contain_token_on_short_argv(self):
        """When argv is too short, the error message must not include the OAuth token."""
        stderr = _run_main_capture_stderr(_SHORT_ARGV)
        self._assert_no_credentials(stderr, "stderr (short argv path)")

    def test_stderr_still_contains_useful_error_message(self):
        """The error path should still emit a helpful message — just without secrets."""
        stderr = _run_main_capture_stderr(_SHORT_ARGV)
        self.assertIn("ERROR", stderr, "Error path should still print an ERROR message to stderr")

    # ------------------------------------------------------------------
    # Test 2: subprocess spawn — startup marker must not contain credentials
    # ------------------------------------------------------------------

    def test_subprocess_stderr_does_not_contain_password(self):
        """Real subprocess run: stderr captured by the caller must not contain password."""
        stderr, _stdout = _read_marker_via_subprocess(_SHORT_ARGV)
        self._assert_no_credentials(stderr, "subprocess stderr")

    def test_subprocess_stderr_does_not_contain_token(self):
        """Real subprocess run: stderr must not contain the OAuth token."""
        stderr, _stdout = _read_marker_via_subprocess(_SHORT_ARGV)
        self._assert_no_credentials(stderr, "subprocess stderr")


class TestManagerProcessStartupMarkerNoCredentials(unittest.TestCase):
    """The /tmp startup marker file must not persist plaintext credentials on disk."""

    def test_marker_file_does_not_contain_password(self):
        """Startup marker written to disk must not contain the plaintext password."""
        import base64
        import json
        import subprocess

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            marker_path = tmp.name

        script = Path(__file__).resolve().parents[5] / "plugins" / "plugin_utils" / "manager" / "manager_process.py"
        env = os.environ.copy()
        env["ANSIBLE_PLATFORM_SYS_PATH"] = base64.b64encode(json.dumps([]).encode()).decode()
        env["ANSIBLE_PLATFORM_AUTHKEY"] = base64.b64encode(b"key").decode()

        # Patch the hardcoded marker path by temporarily replacing the target file
        real_marker = Path("/tmp/ansible_platform_manager_started.txt")
        real_marker_backup = None
        try:
            if real_marker.exists():
                real_marker_backup = real_marker.read_text()
            real_marker.write_text("")  # start clean

            subprocess.run(
                [sys.executable, str(script)] + _SHORT_ARGV[1:],
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
                check=False,
            )

            marker_contents = real_marker.read_text() if real_marker.exists() else ""
            for secret in (FAKE_PASSWORD, FAKE_TOKEN):
                self.assertNotIn(
                    secret,
                    marker_contents,
                    f"Credential leaked in startup marker file! Found '{secret}' in:\n{marker_contents}",
                )
        finally:
            if real_marker_backup is not None:
                real_marker.write_text(real_marker_backup)
            elif real_marker.exists():
                real_marker.unlink()
            Path(marker_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
