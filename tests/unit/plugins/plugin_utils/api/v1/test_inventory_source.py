# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the inventory_source v1 transform mixin (AAP-91390)."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.inventory_source import (  # noqa: E402
    AnsibleInventorySource,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.inventory_source import (  # noqa: E402
    APIInventorySource_v1,
    InventorySourceTransformMixin_v1,
)


def _make_context(lookup_returns=None, default=1):
    manager = MagicMock()
    if lookup_returns is not None:

        def _side_effect(endpoint, field, value):
            return lookup_returns.get((endpoint, value), default)

        manager.lookup_resource_id.side_effect = _side_effect
    else:
        manager.lookup_resource_id.return_value = default
    context = MagicMock()
    context.manager = manager
    return context


class TestInventorySourceTransform(unittest.TestCase):
    def test_from_ansible_data_resolves_all_fk_fields(self):
        ansible = AnsibleInventorySource(
            name="src",
            inventory="Demo Inventory",
            source="scm",
            credential="Demo Credential",
            execution_environment="Default EE",
            source_project="Demo Project",
        )
        lookups = {
            ("/api/controller/v2/inventories/", "Demo Inventory"): 10,
            ("/api/controller/v2/credentials/", "Demo Credential"): 20,
            ("/api/controller/v2/execution_environments/", "Default EE"): 30,
            ("/api/controller/v2/projects/", "Demo Project"): 40,
        }
        context = _make_context(lookup_returns=lookups)

        api = InventorySourceTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.inventory, 10)
        self.assertEqual(api.credential, 20)
        self.assertEqual(api.execution_environment, 30)
        self.assertEqual(api.source_project, 40)
        self.assertEqual(api.source, "scm")

    def test_from_ansible_data_uses_new_name_when_set(self):
        ansible = AnsibleInventorySource(name="old", new_name="new", inventory="inv")
        context = _make_context()

        api = InventorySourceTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.name, "new")

    def test_from_ansible_data_serializes_source_vars_dict_to_json(self):
        ansible = AnsibleInventorySource(name="src", inventory="inv", source_vars={"private": False})
        context = _make_context()

        api = InventorySourceTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.source_vars, '{"private": false}')

    def test_from_ansible_data_includes_id_for_update_url(self):
        ansible = AnsibleInventorySource(name="src", inventory="inv", id=99)
        context = _make_context()

        api = InventorySourceTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.id, 99)

    def test_from_api_round_trips_source_vars_json_string(self):
        ansible = InventorySourceTransformMixin_v1.from_api(
            {"id": 1, "name": "src", "inventory": 10, "source_vars": '{"private": false}'},
            _make_context(),
        )

        self.assertEqual(ansible.inventory, "10")
        self.assertEqual(ansible.source_vars, {"private": False})

    def test_get_endpoint_operations_use_controller_paths(self):
        ops = InventorySourceTransformMixin_v1.get_endpoint_operations()
        for op_name in ("create", "list"):
            self.assertTrue(ops[op_name].path.startswith("/api/controller/v2/inventory_sources"))

    def test_get_find_list_query_params_scopes_by_inventory(self):
        api_data = APIInventorySource_v1(name="src", inventory=10)
        params = InventorySourceTransformMixin_v1.get_find_list_query_params(api_data)
        self.assertEqual(params, {"inventory": 10})


if __name__ == "__main__":
    unittest.main()
