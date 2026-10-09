# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for PlatformService.cancel_resource."""

from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService

__metaclass__ = type


def _service(base_url="https://gw.example.com"):
    """Create a minimal PlatformService instance for testing."""
    service = PlatformService.__new__(PlatformService)
    service.record_activity = MagicMock()
    service.session = MagicMock()
    service.cache = {}
    service.base_url = base_url
    service.request_timeout = 30
    service.config = None
    service.verify_ssl = True
    service.ca_bundle = None
    service.api_versions = {"controller": "2"}
    service.registry = MagicMock()
    service.registry.get_supported_versions.return_value = ["2"]
    return service


def _resp(status_code=200, json_data=None):
    """Create a mock HTTP response."""
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    r.raise_for_status = MagicMock()
    return r


class TestCancelResource(unittest.TestCase):
    def setUp(self):
        self.svc = _service()

    def test_cancel_running_job_returns_changed(self):
        """A running job that can be canceled returns changed=True."""
        get_resp = _resp(200, {"can_cancel": True})
        post_resp = _resp(202, {})
        self.svc.session.get.return_value = get_resp
        self.svc.session.post.return_value = post_resp

        result = self.svc.cancel_resource(
            resource_id=42,
            cancel_endpoint_path="jobs",
            service="controller",
        )

        self.assertTrue(result["changed"])
        self.assertEqual(result["id"], 42)
        self.assertEqual(result["status"], "canceled")
        self.svc.session.post.assert_called_once()

    def test_cancel_finished_job_returns_not_changed(self):
        """A finished job that cannot be canceled returns changed=False."""
        get_resp = _resp(200, {"can_cancel": False})
        self.svc.session.get.return_value = get_resp

        result = self.svc.cancel_resource(
            resource_id=99,
            cancel_endpoint_path="jobs",
            service="controller",
        )

        self.assertFalse(result["changed"])
        self.assertEqual(result["id"], 99)
        self.assertEqual(result["status"], "already_completed")
        self.svc.session.post.assert_not_called()

    def test_cancel_finished_job_with_fail_if_not_running_raises(self):
        """fail_if_not_running=True raises ValueError for a finished job."""
        get_resp = _resp(200, {"can_cancel": False})
        self.svc.session.get.return_value = get_resp

        with self.assertRaises(ValueError) as ctx:
            self.svc.cancel_resource(
                resource_id=77,
                cancel_endpoint_path="jobs",
                fail_if_not_running=True,
                service="controller",
            )

        self.assertIn("not running", str(ctx.exception))
        self.svc.session.post.assert_not_called()

    def test_cancel_calls_correct_url(self):
        """cancel_resource builds the correct controller /cancel/ URL."""
        get_resp = _resp(200, {"can_cancel": True})
        post_resp = _resp(202, {})
        self.svc.session.get.return_value = get_resp
        self.svc.session.post.return_value = post_resp

        self.svc.cancel_resource(
            resource_id=123,
            cancel_endpoint_path="jobs",
            service="controller",
        )

        expected_url = "https://gw.example.com/api/controller/v2/jobs/123/cancel/"
        self.svc.session.get.assert_called_once()
        actual_get_url = self.svc.session.get.call_args[0][0]
        self.assertEqual(actual_get_url, expected_url)

        self.svc.session.post.assert_called_once()
        actual_post_url = self.svc.session.post.call_args[0][0]
        self.assertEqual(actual_post_url, expected_url)

    def test_cancel_records_activity(self):
        """cancel_resource records activity on the service."""
        get_resp = _resp(200, {"can_cancel": True})
        post_resp = _resp(202, {})
        self.svc.session.get.return_value = get_resp
        self.svc.session.post.return_value = post_resp

        self.svc.cancel_resource(
            resource_id=1,
            cancel_endpoint_path="jobs",
            service="controller",
        )

        self.svc.record_activity.assert_called_once()


class TestCancelResourceRPC(unittest.TestCase):
    """Test ManagerRPCClient.cancel_resource delegates correctly."""

    def test_rpc_cancel_delegates_to_proxy(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient

        client = ManagerRPCClient.__new__(ManagerRPCClient)
        client.service_proxy = MagicMock()
        client.service_proxy.cancel_resource.return_value = {"changed": True, "id": 5, "status": "canceled"}

        result = client.cancel_resource(
            resource_id=5,
            cancel_endpoint_path="jobs",
            fail_if_not_running=True,
            service="controller",
        )

        client.service_proxy.cancel_resource.assert_called_once_with(5, "jobs", True, "controller")
        self.assertTrue(result["changed"])
        self.assertEqual(result["id"], 5)


if __name__ == "__main__":
    unittest.main()
