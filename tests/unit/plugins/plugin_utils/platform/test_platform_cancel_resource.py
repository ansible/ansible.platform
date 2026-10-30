"""Tests for SDK resource cancellation."""

import threading
from unittest import TestCase
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import BaseAPIClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError, NetworkError
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.retry import RetryConfig


class TestCancelResource(TestCase):
    """Verify cancellation uses the shared SDK client path."""

    def setUp(self):
        self.client = DirectHTTPClient.__new__(DirectHTTPClient)
        self.client._build_url = MagicMock(return_value="https://controller.example/api/controller/v2/ad_hoc_commands/42/cancel/")
        self.client._post_json = MagicMock(return_value={})
        self.client.wait_for_completion = MagicMock(return_value={"status": "canceled"})

    def test_posts_to_service_scoped_cancel_endpoint(self):
        result = self.client.cancel_resource(42, "ad_hoc_commands", service="controller")

        self.assertEqual(result, {"changed": True, "id": 42, "status": "canceled"})
        self.client._build_url.assert_called_once_with("/ad_hoc_commands/42/cancel/", service="controller")
        self.client._post_json.assert_called_once_with(
            "https://controller.example/api/controller/v2/ad_hoc_commands/42/cancel/",
            {},
            operation="cancel_resource",
            resource="ad_hoc_commands",
            retry=False,
        )
        self.client.wait_for_completion.assert_called_once_with("/ad_hoc_commands/42/", timeout=-1, interval=1.0, service="controller")

    def test_direct_client_handles_empty_cancel_response(self):
        client = DirectHTTPClient.__new__(DirectHTTPClient)
        client._ensure_authenticated = MagicMock()
        client._build_url = MagicMock(return_value="https://controller.example/api/controller/v2/ad_hoc_commands/42/cancel/")
        client.wait_for_completion = MagicMock(return_value={"id": 42, "status": "canceled"})
        response = MagicMock()
        response.read.return_value = b""
        client._make_request = MagicMock(return_value=response)

        result = client.cancel_resource(42, "ad_hoc_commands", service="controller")

        self.assertEqual(result, {"changed": True, "id": 42, "status": "canceled"})
        client.wait_for_completion.assert_called_once_with("/ad_hoc_commands/42/", timeout=-1, interval=1.0, service="controller")

    def test_persistent_client_handles_empty_cancel_response(self):
        client = PlatformService.__new__(PlatformService)
        client._build_url = MagicMock(return_value="https://controller.example/api/controller/v2/ad_hoc_commands/42/cancel/")
        client.record_activity = MagicMock()
        client.wait_for_completion = MagicMock(return_value={"id": 42, "status": "canceled"})
        response = MagicMock()
        response.content = b""
        client._make_request = MagicMock(return_value=response)

        result = client.cancel_resource(42, "ad_hoc_commands", service="controller")

        self.assertEqual(result, {"changed": True, "id": 42, "status": "canceled"})
        response.json.assert_not_called()
        client.wait_for_completion.assert_called_once_with("/ad_hoc_commands/42/", timeout=-1, interval=1.0, service="controller")

    def test_checks_cancel_endpoint_before_check_mode_return(self):
        self.client._get_json = MagicMock(return_value={"can_cancel": True})

        can_cancel = self.client.can_cancel_resource(42, "ad_hoc_commands", service="controller")

        self.assertTrue(can_cancel)
        self.client._build_url.assert_called_once_with("/ad_hoc_commands/42/cancel/", service="controller")
        self.client._get_json.assert_called_once_with(
            "https://controller.example/api/controller/v2/ad_hoc_commands/42/cancel/",
            operation="can_cancel_resource",
            resource="ad_hoc_commands",
        )

    def test_rejects_unexpected_cancel_endpoint_response(self):
        self.client._get_json = MagicMock(return_value={"status": "running"})

        with self.assertRaisesRegex(ValueError, "unexpected response"):
            self.client.can_cancel_resource(42, "ad_hoc_commands", service="controller")

    def test_passes_timeout_and_interval_to_waiter(self):
        self.client.cancel_resource(42, "ad_hoc_commands", timeout=30, interval=0.25, service="controller")

        self.client.wait_for_completion.assert_called_once_with("/ad_hoc_commands/42/", timeout=30, interval=0.25, service="controller")

    def test_not_running_is_noop_unless_requested_to_fail(self):
        self.client._post_json.side_effect = APIError("Cannot cancel", status_code=405)

        result = self.client.cancel_resource(42, "ad_hoc_commands", service="controller")

        self.assertEqual(result, {"changed": False, "id": 42, "status": "already finished"})
        with self.assertRaisesRegex(ValueError, "not running"):
            self.client.cancel_resource(42, "ad_hoc_commands", fail_if_not_running=True, service="controller")

    def test_not_running_detects_http_response_status(self):
        error = Exception("Cannot cancel")
        error.response = MagicMock(status_code=405)
        self.client._post_json.side_effect = error

        result = self.client.cancel_resource(42, "ad_hoc_commands", service="controller")

        self.assertEqual(result, {"changed": False, "id": 42, "status": "already finished"})
        self.client.wait_for_completion.assert_not_called()

    def test_invalid_wait_options_fail_before_cancel_request(self):
        with self.assertRaisesRegex(ValueError, "interval must be positive"):
            self.client.cancel_resource(42, "ad_hoc_commands", interval=0, service="controller")
        with self.assertRaisesRegex(ValueError, "Timeout must be 0 or greater"):
            self.client.cancel_resource(42, "ad_hoc_commands", timeout=-1, service="controller")

        self.client._post_json.assert_not_called()

    def test_cancel_post_is_not_retried_by_persistent_client(self):
        client = PlatformService.__new__(PlatformService)
        client._build_url = MagicMock(return_value="https://controller.example/api/controller/v2/ad_hoc_commands/42/cancel/")
        client.session = MagicMock()
        client.session.post.side_effect = NetworkError("connection reset")
        client._lock = threading.Lock()
        client._http_request_count = 0
        client.record_activity = MagicMock()
        client.request_timeout = 5
        client.retry_config = RetryConfig(max_attempts=3, initial_delay=0, jitter=False)

        with self.assertRaises(NetworkError):
            client.cancel_resource(42, "ad_hoc_commands", service="controller")

        self.assertEqual(client.session.post.call_count, 1)

    def test_rpc_client_exposes_shared_cancel_operation(self):
        rpc_client = ManagerRPCClient.__new__(ManagerRPCClient)
        rpc_client.service_proxy = MagicMock()
        rpc_client.service_proxy.cancel_resource.return_value = {"changed": True, "id": 42, "status": "canceled"}

        result = rpc_client.cancel_resource(42, "ad_hoc_commands", timeout=30, interval=0.5, service="controller")

        self.assertEqual(result, {"changed": True, "id": 42, "status": "canceled"})
        rpc_client.service_proxy.cancel_resource.assert_called_once_with(42, "ad_hoc_commands", False, 30, 0.5, "controller")

    def test_rpc_client_exposes_cancel_eligibility_check(self):
        rpc_client = ManagerRPCClient.__new__(ManagerRPCClient)
        rpc_client.service_proxy = MagicMock()
        rpc_client.service_proxy.can_cancel_resource.return_value = True

        result = rpc_client.can_cancel_resource(42, "ad_hoc_commands", service="controller")

        self.assertTrue(result)
        rpc_client.service_proxy.can_cancel_resource.assert_called_once_with(42, "ad_hoc_commands", "controller")

    def test_both_api_clients_inherit_cancellation(self):
        self.assertTrue(hasattr(BaseAPIClient, "cancel_resource"))
        self.assertTrue(hasattr(BaseAPIClient, "can_cancel_resource"))
        self.assertTrue(hasattr(DirectHTTPClient, "can_cancel_resource"))
        self.assertTrue(hasattr(DirectHTTPClient, "cancel_resource"))
        self.assertTrue(hasattr(PlatformService, "can_cancel_resource"))
        self.assertTrue(hasattr(PlatformService, "cancel_resource"))


if __name__ == "__main__":
    import unittest

    unittest.main()
