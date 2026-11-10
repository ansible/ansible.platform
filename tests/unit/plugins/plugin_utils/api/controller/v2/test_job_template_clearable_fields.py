"""Tests for explicit empty-string updates through both API client modes."""

import json
import threading
import time
import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.job_template import AnsibleJobTemplate
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.job_template import APIJobTemplate_v2, JobTemplateTransformMixin_v2
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient


class TestJobTemplateClearableFields(unittest.TestCase):
    def test_explicit_empty_values_are_sent_in_both_client_modes(self):
        current_resource = {
            "id": 5,
            "name": "Ping",
            "job_type": "run",
            "limit": "web*",
            "scm_branch": "main",
            "job_tags": "release",
            "inventory": 7,
            "project": 8,
            "execution_environment": 9,
            "webhook_credential": 10,
        }
        updated_resource = {**current_resource, "limit": "", "scm_branch": ""}

        for client_mode, client_class in (("direct", DirectHTTPClient), ("persistent", PlatformService)):
            with self.subTest(client_mode=client_mode):
                client = self._client(client_class, current_resource, updated_resource)

                result = client.execute("update", "job_template", {"name": "Ping", "id": 5, "description": "", "limit": "", "scm_branch": ""})

                patch_call = next(call for call in client._make_request.call_args_list if call.args[0].upper() == "PATCH")
                self.assertEqual(patch_call.kwargs["json"]["limit"], "")
                self.assertEqual(patch_call.kwargs["json"]["scm_branch"], "")
                self.assertEqual(patch_call.kwargs["json"]["description"], "")
                self.assertNotIn("job_tags", patch_call.kwargs["json"])
                for association in ("inventory", "project", "execution_environment", "webhook_credential"):
                    self.assertNotIn(association, patch_call.kwargs["json"])
                self.assertTrue(result["changed"])

    @staticmethod
    def _client(client_class, current_resource, updated_resource):
        client = client_class.__new__(client_class)
        client.registry = MagicMock()
        client.registry.get_service_for_module.return_value = "controller"
        client.loader = MagicMock()
        client.loader.load_classes_for_module.return_value = (AnsibleJobTemplate, APIJobTemplate_v2, JobTemplateTransformMixin_v2)
        client.api_versions = {"controller": "2", "gateway": "1"}
        client.cache = {}
        client.base_url = "https://gateway.example"
        client.verify_ssl = True
        client.request_timeout = 10
        client.session = MagicMock()
        client.session.headers = {}
        client.search_api = MagicMock(return_value=current_resource)
        client._make_request = MagicMock(
            side_effect=[
                TestJobTemplateClearableFields._response(current_resource),
                TestJobTemplateClearableFields._response(updated_resource),
            ]
        )

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
        response.content = b"{}"
        response.json.return_value = data
        response.ok = True
        return response


if __name__ == "__main__":
    unittest.main()
