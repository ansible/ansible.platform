# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the inventory_source_update v1 transform mixin (AAP-91390)."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.inventory_source_update import (  # noqa: E402
    AnsibleInventorySourceUpdate,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.inventory_source_update import (  # noqa: E402
    InventorySourceUpdateTransformMixin_v1,
)


def _make_context(inventory_lookup_id=5, found_inventory_source=None):
    manager = MagicMock()
    manager.lookup_resource_id.return_value = inventory_lookup_id
    manager.execute.return_value = found_inventory_source if found_inventory_source is not None else {"id": 42}
    context = MagicMock()
    context.manager = manager
    return context


class TestInventorySourceUpdateTransform(unittest.TestCase):
    def test_from_ansible_data_resolves_inventory_source_id_via_find(self):
        ansible = AnsibleInventorySourceUpdate(name="src", inventory="Demo Inventory")
        context = _make_context(inventory_lookup_id=5, found_inventory_source={"id": 42})

        api = InventorySourceUpdateTransformMixin_v1.from_ansible_data(ansible, context)

        context.manager.lookup_resource_id.assert_called_once_with("/api/controller/v2/inventories/", "name", "Demo Inventory")
        context.manager.execute.assert_called_once_with(
            operation="find",
            module_name="inventory_source",
            ansible_data_dict={"name": "src", "inventory": "5"},
        )
        self.assertEqual(api.inventory_source_id, 42)
        self.assertIsNone(api.id)

    def test_from_ansible_data_reuses_id_when_already_set(self):
        """Second call, during a wait poll, must skip the find and just target {id}."""
        ansible = AnsibleInventorySourceUpdate(name="src", inventory="Demo Inventory", id=99)
        context = _make_context()

        api = InventorySourceUpdateTransformMixin_v1.from_ansible_data(ansible, context)

        context.manager.execute.assert_not_called()
        self.assertEqual(api.id, 99)
        self.assertIsNone(api.inventory_source_id)

    def test_from_ansible_data_raises_when_inventory_source_not_found(self):
        ansible = AnsibleInventorySourceUpdate(name="missing", inventory="Demo Inventory")
        context = _make_context(found_inventory_source={})

        with self.assertRaises(ValueError):
            InventorySourceUpdateTransformMixin_v1.from_ansible_data(ansible, context)

    def test_from_api_maps_launch_response(self):
        ansible = InventorySourceUpdateTransformMixin_v1.from_api(
            {"id": 86, "name": "src", "inventory": 5, "status": "pending", "finished": None},
            _make_context(),
        )

        self.assertEqual(ansible.id, 86)
        self.assertEqual(ansible.status, "pending")
        self.assertEqual(ansible.inventory, "5")

    def test_get_endpoint_operations_target_update_and_inventory_updates_paths(self):
        ops = InventorySourceUpdateTransformMixin_v1.get_endpoint_operations()
        self.assertEqual(ops["create"].path, "/api/controller/v2/inventory_sources/{inventory_source_id}/update/")
        self.assertEqual(ops["get"].path, "/api/controller/v2/inventory_updates/{id}/")
        self.assertNotIn("list", ops)


if __name__ == "__main__":
    unittest.main()
