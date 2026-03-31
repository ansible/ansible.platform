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
            task_args={"gateway_url": "https://gw.example", "gateway_username": "a", "gateway_password": "b", "gateway_idle_timeout": 7200},
            host_vars={},
            required=True,
        )
        self.assertEqual(c.idle_timeout, 7200.0)

    def test_extract_gateway_config_idle_timeout_from_host_vars(self):
        c = extract_gateway_config(
            task_args={"gateway_url": "https://gw.example", "gateway_username": "a", "gateway_password": "b"},
            host_vars={"ansible_platform_manager_idle_timeout": 1800},
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
