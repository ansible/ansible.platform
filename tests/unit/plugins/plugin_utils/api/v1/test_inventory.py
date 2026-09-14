# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the inventory v1 transform mixin (AAP-91390)."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.inventory import (  # noqa: E402
    AnsibleInventory,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.inventory import (  # noqa: E402
    APIInventory_v1,
    InventoryTransformMixin_v1,
)


def _make_context(lookup_return=1):
    manager = MagicMock()
    manager.lookup_resource_id.return_value = lookup_return
    context = MagicMock()
    context.manager = manager
    return context


class TestInventoryTransform(unittest.TestCase):
    def test_from_ansible_data_resolves_organization_via_controller_endpoint(self):
        ansible = AnsibleInventory(name="Foo Inventory", organization="Bar Org")
        context = _make_context(lookup_return=5)

        api = InventoryTransformMixin_v1.from_ansible_data(ansible, context)

        context.manager.lookup_resource_id.assert_called_once_with("/api/controller/v2/organizations/", "name", "Bar Org")
        self.assertEqual(api.organization, 5)
        self.assertEqual(api.name, "Foo Inventory")

    def test_from_ansible_data_uses_new_name_when_set(self):
        ansible = AnsibleInventory(name="Old Name", new_name="New Name", organization="Bar Org")
        context = _make_context()

        api = InventoryTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.name, "New Name")

    def test_from_ansible_data_serializes_variables_dict_to_json(self):
        ansible = AnsibleInventory(name="Foo", organization="Bar", variables={"key": "value"})
        context = _make_context()

        api = InventoryTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.variables, '{"key": "value"}')

    def test_from_ansible_data_omits_unset_optional_fields(self):
        ansible = AnsibleInventory(name="Foo", organization="Bar")
        context = _make_context()

        api = InventoryTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertIsNone(api.kind)
        self.assertIsNone(api.host_filter)
        self.assertIsNone(api.variables)
        self.assertIsNone(api.opa_query_path)

    def test_from_api_round_trips_variables_json_string(self):
        ansible = InventoryTransformMixin_v1.from_api(
            {
                "id": 10,
                "name": "Foo",
                "organization": 5,
                "variables": '{"key": "value"}',
            },
            _make_context(),
        )

        self.assertEqual(ansible.id, 10)
        self.assertEqual(ansible.organization, "5")
        self.assertEqual(ansible.variables, {"key": "value"})

    def test_from_api_handles_missing_variables(self):
        ansible = InventoryTransformMixin_v1.from_api({"id": 1, "name": "Foo", "organization": 2}, _make_context())
        self.assertIsNone(ansible.variables)

    def test_get_endpoint_operations_use_controller_paths(self):
        ops = InventoryTransformMixin_v1.get_endpoint_operations()
        for op_name in ("create", "list"):
            self.assertTrue(ops[op_name].path.startswith("/api/controller/v2/inventories"))
        self.assertEqual(ops["get"].path, "/api/controller/v2/inventories/{id}/")

    def test_get_lookup_field_is_name(self):
        self.assertEqual(InventoryTransformMixin_v1.get_lookup_field(), "name")

    def test_get_find_list_query_params_scopes_by_organization(self):
        api_data = APIInventory_v1(name="Foo", organization=5)
        params = InventoryTransformMixin_v1.get_find_list_query_params(api_data)
        self.assertEqual(params, {"organization": 5})

    def test_get_find_list_query_params_empty_without_organization(self):
        api_data = APIInventory_v1(name="Foo", organization=None)
        params = InventoryTransformMixin_v1.get_find_list_query_params(api_data)
        self.assertEqual(params, {})


if __name__ == "__main__":
    unittest.main()
