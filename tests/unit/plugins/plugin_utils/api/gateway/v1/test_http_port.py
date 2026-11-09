"""Tests for HTTP-port API requests in both client modes."""

import json
import threading
import time
import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.http_port import AnsibleHttpPort
from ansible_collections.ansible.platform.plugins.plugin_utils.api.gateway.v1.http_port import APIHttpPort_v1, HttpPortTransformMixin_v1
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient


class TestHttpPortRenamePayload(unittest.TestCase):
    def test_name_only_update_preserves_current_number_in_both_client_modes(self):
        current_resource = {"id": 17, "name": "old-port", "number": 8443, "use_https": False, "is_api_port": False}
        renamed_resource = {**current_resource, "name": "new-port"}

        for client_mode, client_class in (("direct", DirectHTTPClient), ("persistent", PlatformService)):
            with self.subTest(client_mode=client_mode):
                client = self._client(client_class, current_resource, renamed_resource)

                result = client.execute("update", "http_port", {"id": 17, "name": "old-port", "new_name": "new-port"})

                patch_call = next(call for call in client._make_request.call_args_list if call.args[0].upper() == "PATCH")
                self.assertEqual(patch_call.kwargs["json"]["name"], "new-port")
                self.assertEqual(patch_call.kwargs["json"]["number"], 8443)
                self.assertTrue(result["changed"])

    @staticmethod
    def _client(client_class, current_resource, renamed_resource):
        client = client_class.__new__(client_class)
        client.registry = MagicMock()
        client.registry.get_service_for_module.return_value = "gateway"
        client.loader = MagicMock()
        client.loader.load_classes_for_module.return_value = (AnsibleHttpPort, APIHttpPort_v1, HttpPortTransformMixin_v1)
        client.api_versions = {"controller": "2", "gateway": "1"}
        client.cache = {}
        client.base_url = "https://gateway.example"
        client.verify_ssl = True
        client.request_timeout = 10
        client.session = MagicMock()
        client.session.headers = {}
        find_result = current_resource
        if client_class is DirectHTTPClient:
            find_result = {"count": 1, "results": [current_resource]}
        client._make_request = MagicMock(side_effect=[TestHttpPortRenamePayload._response(find_result), TestHttpPortRenamePayload._response(renamed_resource)])

        if client_class is DirectHTTPClient:
            client._authenticated = True
            client._lock = threading.Lock()
            client._http_request_count = 0
        else:
            client._activity_lock = threading.Lock()
            client._last_activity_monotonic = time.monotonic()

        return client

    @staticmethod
    def _response(data):
        response = MagicMock()
        response.read.return_value = json.dumps(data).encode()
        response.content = json.dumps(data).encode()
        response.json.return_value = data
        response.ok = True
        return response


if __name__ == "__main__":
    unittest.main()
