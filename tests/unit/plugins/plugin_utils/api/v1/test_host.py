# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the host v1 transform mixin (AAP-91390)."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.host import (  # noqa: E402
    AnsibleHost,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.host import (  # noqa: E402
    APIHost_v1,
    HostTransformMixin_v1,
)


def _make_context(lookup_return=1):
    manager = MagicMock()
    manager.lookup_resource_id.return_value = lookup_return
    context = MagicMock()
    context.manager = manager
    return context


class TestHostTransform(unittest.TestCase):
    def test_from_ansible_data_resolves_inventory_via_controller_endpoint(self):
        ansible = AnsibleHost(name="localhost", inventory="Local Inventory")
        context = _make_context(lookup_return=7)

        api = HostTransformMixin_v1.from_ansible_data(ansible, context)

        context.manager.lookup_resource_id.assert_called_once_with("/api/controller/v2/inventories/", "name", "Local Inventory")
        self.assertEqual(api.inventory, 7)
        self.assertEqual(api.name, "localhost")

    def test_from_ansible_data_uses_new_name_when_set(self):
        ansible = AnsibleHost(name="old", new_name="new", inventory="Local Inventory")
        context = _make_context()

        api = HostTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.name, "new")

    def test_from_ansible_data_serializes_variables_dict_to_json(self):
        ansible = AnsibleHost(name="localhost", inventory="Local Inventory", variables={"key": "value"})
        context = _make_context()

        api = HostTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.variables, '{"key": "value"}')

    def test_from_ansible_data_includes_id_for_update_url(self):
        ansible = AnsibleHost(name="localhost", inventory="Local Inventory", id=42)
        context = _make_context()

        api = HostTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.id, 42)

    def test_from_api_round_trips_variables_json_string(self):
        ansible = HostTransformMixin_v1.from_api(
            {"id": 10, "name": "localhost", "inventory": 7, "variables": '{"key": "value"}'},
            _make_context(),
        )

        self.assertEqual(ansible.id, 10)
        self.assertEqual(ansible.inventory, "7")
        self.assertEqual(ansible.variables, {"key": "value"})

    def test_get_endpoint_operations_use_controller_paths(self):
        ops = HostTransformMixin_v1.get_endpoint_operations()
        for op_name in ("create", "list"):
            self.assertTrue(ops[op_name].path.startswith("/api/controller/v2/hosts"))
        self.assertEqual(ops["get"].path, "/api/controller/v2/hosts/{id}/")

    def test_get_lookup_field_is_name(self):
        self.assertEqual(HostTransformMixin_v1.get_lookup_field(), "name")

    def test_get_find_list_query_params_scopes_by_inventory(self):
        api_data = APIHost_v1(name="localhost", inventory=7)
        params = HostTransformMixin_v1.get_find_list_query_params(api_data)
        self.assertEqual(params, {"inventory": 7})

    def test_get_find_list_query_params_empty_without_inventory(self):
        api_data = APIHost_v1(name="localhost", inventory=None)
        params = HostTransformMixin_v1.get_find_list_query_params(api_data)
        self.assertEqual(params, {})


if __name__ == "__main__":
    unittest.main()
