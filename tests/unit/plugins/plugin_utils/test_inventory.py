# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for inventory v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.inventory import AnsibleInventory  # noqa: E402
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.inventory import InventoryTransformMixin_v2  # noqa: E402


class TestInventoryTransform(unittest.TestCase):
    """Ansible <-> API round-trip tests for inventory."""

    def test_post_init_normalizes_variables_dict(self):
        ansible = AnsibleInventory(name="inv", organization="Default", variables={"foo": "bar"})
        self.assertIsInstance(ansible.variables, str)
        self.assertEqual(json.loads(ansible.variables), {"foo": "bar"})

    def test_post_init_preserves_variables_string(self):
        ansible = AnsibleInventory(name="inv", organization="Default", variables='{"foo": "bar"}')
        self.assertEqual(ansible.variables, '{"foo": "bar"}')

    def test_create_includes_all_fields(self):
        ansible = AnsibleInventory(
            name="Production",
            organization="1",
            description="Prod servers",
            kind="",
            host_filter=None,
            variables={"env": "prod"},
            prevent_instance_group_fallback=True,
        )
        api = InventoryTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "Production")
        self.assertEqual(api.organization, 1)
        self.assertEqual(api.description, "Prod servers")
        self.assertEqual(api.kind, "")
        self.assertIs(api.prevent_instance_group_fallback, True)
        self.assertEqual(json.loads(api.variables), {"env": "prod"})

    def test_create_omits_unset_fields(self):
        ansible = AnsibleInventory(name="minimal", organization="1")
        api = InventoryTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "minimal")
        self.assertEqual(api.organization, 1)
        self.assertIsNone(api.description)
        self.assertIsNone(api.kind)
        self.assertIsNone(api.variables)

    def test_create_with_org_name_resolves_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 42
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleInventory(name="inv", organization="Default")
        api = InventoryTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_called_once_with("organizations", "name", "Default")
        self.assertEqual(api.organization, 42)

    def test_create_with_org_id_skips_lookup(self):
        ansible = AnsibleInventory(name="inv", organization="42")
        api = InventoryTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.organization, 42)

    def test_org_lookup_uses_default_service_not_controller(self):
        """Organization is Gateway-owned, so lookup_resource_id should NOT pass service='controller'."""
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 1
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleInventory(name="inv", organization="Default")
        InventoryTransformMixin_v2.from_ansible_data(ansible, context)
        call_kwargs = mock_manager.lookup_resource_id.call_args
        # Should NOT have service="controller" — organization is gateway-owned
        self.assertNotIn("controller", str(call_kwargs))

    def test_update_with_new_name(self):
        ansible = AnsibleInventory(name="old", organization="1", new_name="new")
        api = InventoryTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "new")

    def test_update_without_new_name_echoes(self):
        ansible = AnsibleInventory(name="keep", organization="1")
        api = InventoryTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "keep")

    def test_smart_inventory_with_host_filter(self):
        ansible = AnsibleInventory(name="smart", organization="1", kind="smart", host_filter="os__icontains=linux")
        api = InventoryTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.kind, "smart")
        self.assertEqual(api.host_filter, "os__icontains=linux")

    def test_from_api_returns_ansible_instance(self):
        api_data = {
            "id": 99,
            "name": "Production",
            "description": "Prod servers",
            "organization": 5,
            "kind": "",
            "host_filter": None,
            "variables": '{"env": "prod"}',
            "prevent_instance_group_fallback": False,
        }
        ansible = InventoryTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleInventory)
        self.assertEqual(ansible.id, 99)
        self.assertEqual(ansible.name, "Production")
        self.assertEqual(ansible.organization, "5")
        self.assertEqual(ansible.kind, "")
        self.assertIs(ansible.prevent_instance_group_fallback, False)
        # variables kept as string from API (no deserialization)
        self.assertEqual(ansible.variables, '{"env": "prod"}')

    def test_from_api_handles_missing_fields(self):
        ansible = InventoryTransformMixin_v2.from_api({"name": "bare", "organization": 1}, {})
        self.assertEqual(ansible.name, "bare")
        self.assertIsNone(ansible.description)
        self.assertIsNone(ansible.kind)
        self.assertIsNone(ansible.id)

    def test_from_api_resolves_organization_name(self):
        mock_manager = MagicMock()
        mock_manager.lookup_organization_names.return_value = ["Default"]

        ansible = InventoryTransformMixin_v2.from_api({"name": "Production", "organization": 5}, {"manager": mock_manager})

        mock_manager.lookup_organization_names.assert_called_once_with([5])
        self.assertEqual(ansible.organization, "Default")

    def test_from_api_preserves_missing_organization_as_empty_string(self):
        mock_manager = MagicMock()

        ansible = InventoryTransformMixin_v2.from_api({"name": "bare"}, {"manager": mock_manager})

        mock_manager.lookup_organization_names.assert_not_called()
        self.assertEqual(ansible.organization, "")

    def test_endpoint_operations_use_controller_paths(self):
        ops = InventoryTransformMixin_v2.get_endpoint_operations()
        for op_name, op in ops.items():
            self.assertTrue(
                op.path.startswith("/api/controller/v2/inventories"),
                f"{op_name} path should start with /api/controller/v2/inventories, got {op.path}",
            )

    def test_lookup_field_is_name(self):
        self.assertEqual(InventoryTransformMixin_v2.get_lookup_field(), "name")

    def test_id_passthrough_for_update(self):
        ansible = AnsibleInventory(name="inv", organization="1", id=99)
        api = InventoryTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 99)

    def test_get_find_list_query_params_with_org_id(self):
        """Lookup should be scoped by organization to avoid cross-org collisions."""
        ansible = AnsibleInventory(name="inv", organization="1")
        api = InventoryTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        params = InventoryTransformMixin_v2.get_find_list_query_params(api)
        self.assertEqual(params, {"organization": 1})

    def test_get_find_list_query_params_without_org(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.inventory import APIInventory_v2

        api = APIInventory_v2(name="inv")
        params = InventoryTransformMixin_v2.get_find_list_query_params(api)
        self.assertEqual(params, {})

    def test_post_init_sorts_variables_keys(self):
        """Canonical JSON with sorted keys for idempotent comparison."""
        ansible = AnsibleInventory(name="inv", organization="Default", variables={"z": 1, "a": 2})
        self.assertEqual(ansible.variables, '{"a": 2, "z": 1}')

    def test_post_init_normalizes_json_string_key_order(self):
        """A JSON string with unsorted keys gets re-serialized with sorted keys."""
        ansible = AnsibleInventory(name="inv", organization="Default", variables='{"z": 1, "a": 2}')
        self.assertEqual(ansible.variables, '{"a": 2, "z": 1}')

    def test_variables_idempotency_dict_vs_api_string(self):
        """A dict from the task and a JSON string from the API should compare equal after normalization."""
        task_vars = {"foo": "bar", "num": 42}
        api_vars = '{"num": 42, "foo": "bar"}'

        task_model = AnsibleInventory(name="inv", organization="1", variables=task_vars)
        api_model = InventoryTransformMixin_v2.from_api({"name": "inv", "organization": 1, "variables": api_vars}, {})
        self.assertEqual(task_model.variables, api_model.variables)

    def test_from_api_normalizes_variables_key_order(self):
        """from_api should return variables with sorted keys for canonical comparison."""
        api_data = {"name": "inv", "organization": 1, "variables": '{"z": 1, "a": 2}'}
        ansible = InventoryTransformMixin_v2.from_api(api_data, {})
        self.assertEqual(ansible.variables, '{"a": 2, "z": 1}')


if __name__ == "__main__":
    unittest.main()
