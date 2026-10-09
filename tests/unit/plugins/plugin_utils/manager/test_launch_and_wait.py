# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for launch_resource() and wait_for_completion() SDK methods."""

from __future__ import absolute_import, division, print_function

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import (  # noqa: E402
    DEFAULT_WAIT_INTERVAL,
    DEFAULT_WAIT_TIMEOUT,
    TERMINAL_STATUSES,
    WaitTimeoutError,
)


class TestWaitTimeoutError(unittest.TestCase):
    def test_stores_last_result(self):
        exc = WaitTimeoutError("timed out", last_result={"id": 42, "status": "pending"})
        self.assertEqual(str(exc), "timed out")
        self.assertEqual(exc.last_result["id"], 42)
        self.assertEqual(exc.last_result["status"], "pending")

    def test_default_last_result_is_empty_dict(self):
        exc = WaitTimeoutError("timed out")
        self.assertEqual(exc.last_result, {})


class TestConstants(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(DEFAULT_WAIT_TIMEOUT, 3600.0)
        self.assertEqual(DEFAULT_WAIT_INTERVAL, 10.0)

    def test_terminal_statuses(self):
        self.assertIn("successful", TERMINAL_STATUSES)
        self.assertIn("failed", TERMINAL_STATUSES)
        self.assertIn("error", TERMINAL_STATUSES)
        self.assertIn("canceled", TERMINAL_STATUSES)
        self.assertNotIn("pending", TERMINAL_STATUSES)
        self.assertNotIn("running", TERMINAL_STATUSES)


class TestPlatformManagerLaunchResource(unittest.TestCase):
    def _make_manager(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService

        config = MagicMock()
        config.base_url = "https://gw.example.com"
        config.verify_ssl = False
        config.ca_bundle = None
        config.request_timeout = 30
        config.requests_verify = False
        config.connection_mode = "direct"
        mgr = PlatformService.__new__(PlatformService)
        mgr.config = config
        mgr.session = MagicMock()
        mgr.request_timeout = 30
        mgr.base_url = "https://gw.example.com"
        mgr._last_activity = time.time()
        mgr._activity_lock = threading.Lock()
        mgr._last_activity_monotonic = time.monotonic()
        mgr.registry = MagicMock()
        mgr.api_versions = {}
        return mgr

    def test_launch_posts_payload(self):
        mgr = self._make_manager()
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 99, "status": "pending", "url": "/api/controller/v2/jobs/99/"}
        mock_response.raise_for_status = MagicMock()
        mgr.session.post.return_value = mock_response
        mgr._build_url = MagicMock(return_value="https://gw.example.com/api/controller/v2/job_templates/1/launch/")

        result = mgr.launch_resource("/api/controller/v2/job_templates/1/launch/", {"extra_vars": "{}"}, service="controller")

        self.assertEqual(result["id"], 99)
        self.assertEqual(result["status"], "pending")
        mgr.session.post.assert_called_once()

    def test_wait_returns_on_successful(self):
        mgr = self._make_manager()
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 99, "status": "successful"}
        mock_response.raise_for_status = MagicMock()
        mgr.session.get.return_value = mock_response
        mgr._build_url = MagicMock(return_value="https://gw.example.com/api/controller/v2/jobs/99/")

        result = mgr.wait_for_completion("/api/controller/v2/jobs/99/", timeout=30, interval=1, service="controller")

        self.assertEqual(result["status"], "successful")

    def test_wait_returns_on_failed(self):
        mgr = self._make_manager()
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 99, "status": "failed"}
        mock_response.raise_for_status = MagicMock()
        mgr.session.get.return_value = mock_response
        mgr._build_url = MagicMock(return_value="https://gw.example.com/api/controller/v2/jobs/99/")

        result = mgr.wait_for_completion("/api/controller/v2/jobs/99/", timeout=30, interval=1, service="controller")

        self.assertEqual(result["status"], "failed")

    @patch("time.sleep")
    def test_wait_polls_until_terminal(self, mock_sleep):
        mgr = self._make_manager()
        responses = [
            {"id": 99, "status": "pending"},
            {"id": 99, "status": "running"},
            {"id": 99, "status": "successful"},
        ]
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = responses
        mgr.session.get.return_value = mock_response
        mgr._build_url = MagicMock(return_value="https://gw.example.com/api/controller/v2/jobs/99/")

        result = mgr.wait_for_completion("/api/controller/v2/jobs/99/", timeout=60, interval=1, service="controller")

        self.assertEqual(result["status"], "successful")
        self.assertEqual(mock_sleep.call_count, 2)

    def test_wait_timeout_raises_with_last_result(self):
        mgr = self._make_manager()
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 99, "status": "pending"}
        mock_response.raise_for_status = MagicMock()
        mgr.session.get.return_value = mock_response
        mgr._build_url = MagicMock(return_value="https://gw.example.com/api/controller/v2/jobs/99/")

        with self.assertRaises(WaitTimeoutError) as ctx:
            mgr.wait_for_completion("/api/controller/v2/jobs/99/", timeout=0, interval=1, service="controller")

        self.assertEqual(ctx.exception.last_result.get("id"), 99)
        self.assertEqual(ctx.exception.last_result.get("status"), "pending")


class TestRPCClientWrappers(unittest.TestCase):
    def test_launch_resource_delegates(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient

        client = ManagerRPCClient.__new__(ManagerRPCClient)
        client.service_proxy = MagicMock()
        client.service_proxy.launch_resource.return_value = {"id": 1}

        result = client.launch_resource("/launch/", {"key": "val"}, service="controller")

        self.assertEqual(result["id"], 1)
        client.service_proxy.launch_resource.assert_called_once_with("/launch/", {"key": "val"}, "controller")

    def test_wait_for_completion_delegates(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient

        client = ManagerRPCClient.__new__(ManagerRPCClient)
        client.service_proxy = MagicMock()
        client.service_proxy.wait_for_completion.return_value = {"id": 1, "status": "successful"}

        result = client.wait_for_completion("/jobs/1/", timeout=30, interval=5, service="controller")

        self.assertEqual(result["status"], "successful")
        client.service_proxy.wait_for_completion.assert_called_once_with("/jobs/1/", 30, 5, "controller")


if __name__ == "__main__":
    unittest.main()
