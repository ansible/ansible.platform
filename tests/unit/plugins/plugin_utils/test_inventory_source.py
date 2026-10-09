# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for inventory_source v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.inventory_source import AnsibleInventorySource  # noqa: E402
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.inventory_source import (  # noqa: E402
    InventorySourceTransformMixin_v2,
)


class TestInventorySourceTransform(unittest.TestCase):
    """Ansible <-> API round-trip tests for inventory_source."""

    def test_post_init_normalizes_source_vars_dict(self):
        ansible = AnsibleInventorySource(name="src", inventory="1", source_vars={"private": False})
        self.assertIsInstance(ansible.source_vars, str)
        self.assertEqual(json.loads(ansible.source_vars), {"private": False})

    def test_post_init_preserves_source_vars_string(self):
        ansible = AnsibleInventorySource(name="src", inventory="1", source_vars='{"private": false}')
        self.assertEqual(ansible.source_vars, '{"private": false}')

    def test_create_includes_all_fields(self):
        ansible = AnsibleInventorySource(
            name="ec2-src",
            inventory="5",
            source="ec2",
            description="EC2 source",
            source_path="/path",
            source_vars={"key": "val"},
            enabled_var="status",
            enabled_value="running",
            host_filter=".*linux.*",
            limit="web*",
            credential="10",
            execution_environment="3",
            overwrite=True,
            overwrite_vars=False,
            timeout=300,
            verbosity=1,
            update_on_launch=True,
            update_cache_timeout=60,
            source_project="7",
            scm_branch="main",
        )
        api = InventorySourceTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "ec2-src")
        self.assertEqual(api.inventory, 5)
        self.assertEqual(api.source, "ec2")
        self.assertEqual(api.description, "EC2 source")
        self.assertIs(api.overwrite, True)
        self.assertEqual(api.timeout, 300)
        self.assertEqual(api.verbosity, 1)
        self.assertEqual(api.credential, 10)
        self.assertEqual(api.execution_environment, 3)
        self.assertEqual(api.source_project, 7)
        self.assertEqual(api.scm_branch, "main")
        self.assertEqual(json.loads(api.source_vars), {"key": "val"})

    def test_create_omits_unset_fields(self):
        ansible = AnsibleInventorySource(name="minimal", inventory="1", source="ec2")
        api = InventorySourceTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "minimal")
        self.assertEqual(api.inventory, 1)
        self.assertEqual(api.source, "ec2")
        self.assertIsNone(api.description)
        self.assertIsNone(api.credential)
        self.assertIsNone(api.source_vars)

    def test_fk_inventory_resolved_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 42
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleInventorySource(name="src", inventory="Production", source="ec2")
        api = InventorySourceTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("inventories", "name", "Production", service="controller")
        self.assertEqual(api.inventory, 42)

    def test_fk_credential_resolved_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 99
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleInventorySource(name="src", inventory="1", source="ec2", credential="AWS Cred")
        api = InventorySourceTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("credentials", "name", "AWS Cred", service="controller")
        self.assertEqual(api.credential, 99)

    def test_fk_ee_resolved_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 7
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleInventorySource(name="src", inventory="1", source="ec2", execution_environment="My EE")
        api = InventorySourceTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("execution_environments", "name", "My EE", service="controller")
        self.assertEqual(api.execution_environment, 7)

    def test_fk_source_project_resolved_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 15
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleInventorySource(name="src", inventory="1", source="scm", source_project="My Project")
        api = InventorySourceTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("projects", "name", "My Project", service="controller")
        self.assertEqual(api.source_project, 15)

    def test_fk_id_skips_lookup(self):
        ansible = AnsibleInventorySource(name="src", inventory="42", source="ec2", credential="10")
        api = InventorySourceTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.inventory, 42)
        self.assertEqual(api.credential, 10)

    def test_update_with_new_name(self):
        ansible = AnsibleInventorySource(name="old", inventory="1", new_name="new")
        api = InventorySourceTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "new")

    def test_update_without_new_name_echoes(self):
        ansible = AnsibleInventorySource(name="keep", inventory="1")
        api = InventorySourceTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "keep")

    def test_from_api_returns_ansible_instance(self):
        api_data = {
            "id": 99,
            "name": "ec2-src",
            "description": "EC2 source",
            "inventory": 5,
            "source": "ec2",
            "source_vars": '{"key": "val"}',
            "credential": 10,
            "execution_environment": 3,
            "source_project": 7,
            "overwrite": True,
            "timeout": 300,
        }
        ansible = InventorySourceTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleInventorySource)
        self.assertEqual(ansible.id, 99)
        self.assertEqual(ansible.name, "ec2-src")
        self.assertEqual(ansible.inventory, "5")
        self.assertEqual(ansible.credential, "10")
        self.assertEqual(ansible.execution_environment, "3")
        self.assertEqual(ansible.source_project, "7")
        self.assertEqual(ansible.source_vars, '{"key": "val"}')
        self.assertIs(ansible.overwrite, True)

    def test_from_api_handles_missing_fields(self):
        ansible = InventorySourceTransformMixin_v2.from_api({"name": "bare", "inventory": 1, "source": "ec2"}, {})
        self.assertEqual(ansible.name, "bare")
        self.assertIsNone(ansible.description)
        self.assertIsNone(ansible.credential)
        self.assertIsNone(ansible.id)

    def test_from_api_null_fk_fields(self):
        ansible = InventorySourceTransformMixin_v2.from_api(
            {"name": "src", "inventory": 1, "credential": None, "execution_environment": None, "source_project": None}, {}
        )
        self.assertIsNone(ansible.credential)
        self.assertIsNone(ansible.execution_environment)
        self.assertIsNone(ansible.source_project)

    def test_endpoint_operations_use_controller_paths(self):
        ops = InventorySourceTransformMixin_v2.get_endpoint_operations()
        for op_name, op in ops.items():
            self.assertTrue(
                op.path.startswith("/api/controller/v2/inventory_sources"),
                f"{op_name} path should start with /api/controller/v2/inventory_sources, got {op.path}",
            )

    def test_lookup_field_is_name(self):
        self.assertEqual(InventorySourceTransformMixin_v2.get_lookup_field(), "name")

    def test_id_passthrough_for_update(self):
        ansible = AnsibleInventorySource(name="src", inventory="1", id=99)
        api = InventorySourceTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 99)


if __name__ == "__main__":
    unittest.main()
