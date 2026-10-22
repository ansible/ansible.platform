# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests service routing for sub-resource management in manager and direct modes."""

from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient

__metaclass__ = type


class TestManageSubResourceService(unittest.TestCase):
    def test_platform_service_routes_relative_path_to_requested_service(self):
        service = PlatformService.__new__(PlatformService)
        service.record_activity = MagicMock()
        service.base_url = "https://gateway.example.com"
        service.request_timeout = 30
        service.verify_ssl = True
        service.ca_bundle = None
        service.get_api_version = MagicMock(return_value="2")
        service.session = MagicMock()
        service.session.delete.return_value.status_code = 200
        service.session.delete.return_value.raise_for_status = MagicMock()

        result = service.manage_sub_resource("job_templates", 42, "survey_spec", {}, service="controller")

        self.assertTrue(result)
        service.session.delete.assert_called_once_with("https://gateway.example.com/api/controller/v2/job_templates/42/survey_spec/", timeout=30, verify=True)

    def test_direct_client_routes_relative_path_to_requested_service(self):
        client = DirectHTTPClient.__new__(DirectHTTPClient)
        client._authenticated = True
        client.base_url = "https://gateway.example.com"
        client.get_api_version = MagicMock(return_value="2")
        client._make_request = MagicMock()

        result = client.manage_sub_resource("job_templates", 42, "survey_spec", {}, service="controller")

        self.assertTrue(result)
        client._make_request.assert_called_once_with(
            "DELETE",
            "https://gateway.example.com/api/controller/v2/job_templates/42/survey_spec/",
            operation="delete_sub_resource",
            resource="survey_spec",
        )

    def test_rpc_wrapper_forwards_service(self):
        client = ManagerRPCClient.__new__(ManagerRPCClient)
        client.service_proxy = MagicMock()

        client.manage_sub_resource("job_templates", 42, "survey_spec", {}, service="controller")

        client.service_proxy.manage_sub_resource.assert_called_once_with("job_templates", 42, "survey_spec", {}, "controller")


if __name__ == "__main__":
    unittest.main()
