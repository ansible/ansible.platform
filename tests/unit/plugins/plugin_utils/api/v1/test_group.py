# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the group v1 transform mixin (AAP-91391)."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.group import AnsibleGroup  # noqa: E402
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.group import (  # noqa: E402
    APIGroup_v1,
    GroupTransformMixin_v1,
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


class TestGroupTransform(unittest.TestCase):
    def test_from_ansible_data_resolves_inventory(self):
        ansible = AnsibleGroup(name="grp", inventory="Demo Inventory")
        context = _make_context(lookup_returns={("/api/controller/v2/inventories/", "Demo Inventory"): 20})

        api = GroupTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.inventory, 20)

    def test_from_ansible_data_uses_new_name_when_set(self):
        ansible = AnsibleGroup(name="old", inventory="Demo", new_name="new")
        context = _make_context()

        api = GroupTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.name, "new")

    def test_from_ansible_data_serializes_variables_dict_to_json(self):
        ansible = AnsibleGroup(name="grp", inventory="Demo", variables={"foo": "bar"})
        context = _make_context()

        api = GroupTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.variables, '{"foo": "bar"}')

    def test_from_api_maps_fields_and_parses_variables(self):
        ansible = GroupTransformMixin_v1.from_api(
            {"id": 1, "name": "grp", "inventory": 20, "variables": '{"foo": "bar"}'},
            _make_context(),
        )

        self.assertEqual(ansible.inventory, "20")
        self.assertEqual(ansible.variables, {"foo": "bar"})

    def test_get_endpoint_operations_use_controller_paths(self):
        ops = GroupTransformMixin_v1.get_endpoint_operations()
        for op_name in ("create", "list"):
            self.assertTrue(ops[op_name].path.startswith("/api/controller/v2/groups"))

    def test_get_find_list_query_params_scopes_by_inventory(self):
        api_data = APIGroup_v1(name="grp", inventory=20)
        params = GroupTransformMixin_v1.get_find_list_query_params(api_data)
        self.assertEqual(params, {"inventory": 20})


if __name__ == "__main__":
    unittest.main()
