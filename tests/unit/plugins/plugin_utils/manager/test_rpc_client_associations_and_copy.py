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
    def test_lookup_resource_id_passes_uniqueness_requirement_to_service(self):
        client = _rpc_client()

        result = client.lookup_resource_id("inventories", "name", "shared", service="controller", extra_query_params={"organization": 4}, require_unique=True)

        self.assertEqual(result, client.service_proxy.lookup_resource_id.return_value)
        client.service_proxy.lookup_resource_id.assert_called_once_with("inventories", "name", "shared", "controller", {"organization": 4}, True, True)

    def test_lookup_resource_id_passes_numeric_name_option_to_service(self):
        client = _rpc_client()

        result = client.lookup_resource_id("organizations", "name", "123", service="controller", numeric_is_id=False)

        self.assertEqual(result, client.service_proxy.lookup_resource_id.return_value)
        client.service_proxy.lookup_resource_id.assert_called_once_with("organizations", "name", "123", "controller", {}, True, False)

    def test_lookup_resource_ids_passes_scope_and_matching_options_to_service(self):
        client = _rpc_client()

        result = client.lookup_resource_ids(
            "workflow_job_template_nodes",
            "identifier",
            ["123", "child"],
            service="controller",
            extra_query_params={"workflow_job_template": 77},
            numeric_is_id=False,
            allow_missing=True,
        )

        self.assertEqual(result, client.service_proxy.lookup_resource_ids.return_value)
        client.service_proxy.lookup_resource_ids.assert_called_once_with(
            "workflow_job_template_nodes", "identifier", ["123", "child"], "controller", {"workflow_job_template": 77}, False, True
        )

    def test_manage_associations_delegates_to_service_proxy(self):
        client = _rpc_client()
        client.service_proxy.manage_associations.return_value = True

        result = client.manage_associations(
            "/api/controller/v2/job_templates", 42, "credentials", ["a"], "credentials", "name", "controller", preserve_existing=True, check_mode=True
        )

        self.assertTrue(result)
        client.service_proxy.manage_associations.assert_called_once_with(
            "/api/controller/v2/job_templates",
            42,
            "credentials",
            ["a"],
            "credentials",
            "name",
            "controller",
            {},
            True,
            True,
        )

    def test_manage_sub_resource_delegates_to_service_proxy(self):
        client = _rpc_client()
        client.service_proxy.manage_sub_resource.return_value = False

        result = client.manage_sub_resource("/api/controller/v2/job_templates", 42, "survey_spec", None)

        self.assertFalse(result)
        client.service_proxy.manage_sub_resource.assert_called_once_with("/api/controller/v2/job_templates", 42, "survey_spec", None, False)

    def test_copy_resource_delegates_to_service_proxy(self):
        client = _rpc_client()
        client.service_proxy.copy_resource.return_value = {"id": 99}

        result = client.copy_resource("job_template", "source", "copied", "/api/controller/v2/job_templates", "controller")

        self.assertEqual(result, {"id": 99})
        client.service_proxy.copy_resource.assert_called_once_with("job_template", "source", "copied", "/api/controller/v2/job_templates", "controller")


def test_subresource_dry_run_flag_is_forwarded_through_rpc():
    """Keep the persistent action on the same comparison path as direct mode."""
    from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient

    client = ManagerRPCClient.__new__(ManagerRPCClient)
    client.service_proxy = MagicMock()
    client.service_proxy.manage_sub_resource.return_value = True
    assert client.manage_sub_resource("/api/controller/v2/workflow_job_templates", 7, "survey_spec", {}, check_mode=True)
    client.service_proxy.manage_sub_resource.assert_called_once_with("/api/controller/v2/workflow_job_templates", 7, "survey_spec", {}, True)


if __name__ == "__main__":
    unittest.main()
