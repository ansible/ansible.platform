# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for ManagerRPCClient's thin wrappers around the new generic SDK methods."""

from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient

__metaclass__ = type


def _rpc_client():
    client = ManagerRPCClient.__new__(ManagerRPCClient)
    client.service_proxy = MagicMock()
    return client


class TestRPCWrappers(unittest.TestCase):
    def test_manage_associations_delegates_to_service_proxy(self):
        client = _rpc_client()
        client.service_proxy.manage_associations.return_value = True

        result = client.manage_associations("/api/controller/v2/job_templates", 42, "credentials", ["a"], "credentials", "name", "controller")

        self.assertTrue(result)
        client.service_proxy.manage_associations.assert_called_once_with(
            "/api/controller/v2/job_templates", 42, "credentials", ["a"], "credentials", "name", "controller"
        )

    def test_manage_sub_resource_delegates_to_service_proxy(self):
        client = _rpc_client()
        client.service_proxy.manage_sub_resource.return_value = False

        result = client.manage_sub_resource("/api/controller/v2/job_templates", 42, "survey_spec", None)

        self.assertFalse(result)
        client.service_proxy.manage_sub_resource.assert_called_once_with("/api/controller/v2/job_templates", 42, "survey_spec", None)

    def test_copy_resource_delegates_to_service_proxy(self):
        client = _rpc_client()
        client.service_proxy.copy_resource.return_value = {"id": 99}

        result = client.copy_resource("job_template", "source", "copied", "/api/controller/v2/job_templates", "controller")

        self.assertEqual(result, {"id": 99})
        client.service_proxy.copy_resource.assert_called_once_with("job_template", "source", "copied", "/api/controller/v2/job_templates", "controller")


if __name__ == "__main__":
    unittest.main()
