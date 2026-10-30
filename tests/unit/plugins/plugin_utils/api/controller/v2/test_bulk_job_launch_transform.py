# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the bulk job launch transform."""

from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock, call

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.bulk_job_launch import AnsibleBulkJobLaunch
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.bulk_job_launch import APIBulkJobLaunch_v2, BulkJobLaunchTransformMixin_v2
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext

__metaclass__ = type


def _context(manager):
    return TransformContext(manager=manager, session=MagicMock(), cache={}, api_version="2", service="controller", operation="create")


class TestBulkJobLaunchTransform(unittest.TestCase):
    def test_from_ansible_data_maps_fields_and_scopes_inventory_lookup(self):
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = [22, 71]
        ansible_data = AnsibleBulkJobLaunch(
            jobs=[{"unified_job_template": 7}],
            name="Bulk launch",
            description="Deploy services",
            organization="Engineering",
            inventory="Shared Inventory",
            limit="webservers",
            scm_branch="main",
            extra_vars={"release": "stable"},
            job_tags="deploy",
            skip_tags="debug",
        )

        api_data = BulkJobLaunchTransformMixin_v2.from_ansible_data(ansible_data, _context(manager))

        self.assertEqual(
            api_data,
            APIBulkJobLaunch_v2(
                jobs=[{"unified_job_template": 7}],
                name="Bulk launch",
                description="Deploy services",
                organization=22,
                inventory=71,
                limit="webservers",
                scm_branch="main",
                extra_vars={"release": "stable"},
                job_tags="deploy",
                skip_tags="debug",
            ),
        )
        self.assertEqual(
            manager.lookup_resource_id.call_args_list,
            [
                call("organizations", "name", "Engineering", service="controller"),
                call(
                    "inventories",
                    "name",
                    "Shared Inventory",
                    service="controller",
                    require_unique=True,
                    extra_query_params={"organization": 22},
                ),
            ],
        )

    def test_numeric_organization_and_inventory_ids_are_converted_without_lookups(self):
        manager = MagicMock()
        ansible_data = AnsibleBulkJobLaunch(jobs=[{"unified_job_template": 7}], organization="22", inventory="71")

        api_data = BulkJobLaunchTransformMixin_v2.from_ansible_data(ansible_data, _context(manager))

        self.assertEqual(api_data.organization, 22)
        self.assertEqual(api_data.inventory, 71)
        manager.lookup_resource_id.assert_not_called()

    def test_unscoped_inventory_name_requires_unique_match(self):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 71
        ansible_data = AnsibleBulkJobLaunch(jobs=[{"unified_job_template": 7}], inventory="Shared Inventory")

        api_data = BulkJobLaunchTransformMixin_v2.from_ansible_data(ansible_data, _context(manager))

        self.assertEqual(api_data.inventory, 71)
        manager.lookup_resource_id.assert_called_once_with("inventories", "name", "Shared Inventory", service="controller", require_unique=True)

    def test_named_inventory_url_is_passed_to_shared_resolver(self):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 71
        ansible_data = AnsibleBulkJobLaunch(jobs=[{"unified_job_template": 7}], inventory="Default++Shared Inventory")

        api_data = BulkJobLaunchTransformMixin_v2.from_ansible_data(ansible_data, _context(manager))

        self.assertEqual(api_data.inventory, 71)
        manager.lookup_resource_id.assert_called_once_with("inventories", "name", "Default++Shared Inventory", service="controller", require_unique=True)

    def test_resolve_performs_reference_lookups_without_creating_resource(self):
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = [22, 71]
        ansible_data = AnsibleBulkJobLaunch(organization="Engineering", inventory="Shared Inventory")

        resolved = BulkJobLaunchTransformMixin_v2.resolve(ansible_data, _context(manager))

        self.assertEqual(resolved, {"organization": 22, "inventory": 71})
        self.assertEqual(
            manager.lookup_resource_id.call_args_list,
            [
                call("organizations", "name", "Engineering", service="controller"),
                call(
                    "inventories",
                    "name",
                    "Shared Inventory",
                    service="controller",
                    require_unique=True,
                    extra_query_params={"organization": 22},
                ),
            ],
        )

    def test_from_api_preserves_launch_response(self):
        response = {"id": 42, "status": "pending", "type": "workflow_job", "url": "/api/controller/v2/workflow_jobs/42/"}

        ansible_data = BulkJobLaunchTransformMixin_v2.from_api(response, _context(MagicMock()))

        self.assertEqual(ansible_data.id, 42)
        self.assertEqual(ansible_data.status, "pending")
        self.assertEqual(ansible_data.job_info, response)

    def test_create_operation_posts_all_supported_payload_fields(self):
        operation = BulkJobLaunchTransformMixin_v2.get_endpoint_operations()["create"]

        self.assertEqual(operation.path, "/api/controller/v2/bulk/job_launch/")
        self.assertEqual(operation.method, "POST")
        self.assertEqual(
            operation.fields,
            ["jobs", "name", "description", "organization", "inventory", "limit", "scm_branch", "extra_vars", "job_tags", "skip_tags"],
        )
