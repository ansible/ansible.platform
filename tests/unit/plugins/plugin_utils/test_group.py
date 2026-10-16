# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for group v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.group import AnsibleGroup  # noqa: E402
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.group import GroupTransformMixin_v2  # noqa: E402


class TestGroupTransform(unittest.TestCase):
    """Ansible <-> API round-trip tests for group."""

    def test_post_init_normalizes_variables_dict(self):
        ansible = AnsibleGroup(name="g", inventory="1", variables={"foo": "bar"})
        self.assertIsInstance(ansible.variables, str)
        self.assertEqual(json.loads(ansible.variables), {"foo": "bar"})

    def test_post_init_preserves_variables_string(self):
        ansible = AnsibleGroup(name="g", inventory="1", variables='{"foo": "bar"}')
        self.assertEqual(ansible.variables, '{"foo": "bar"}')

    def test_create_includes_all_fields(self):
        ansible = AnsibleGroup(name="webservers", inventory="5", description="Web servers", variables={"http_port": 80})
        api = GroupTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "webservers")
        self.assertEqual(api.inventory, 5)
        self.assertEqual(api.description, "Web servers")
        self.assertEqual(json.loads(api.variables), {"http_port": 80})

    def test_create_omits_unset_fields(self):
        ansible = AnsibleGroup(name="minimal", inventory="1")
        api = GroupTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "minimal")
        self.assertEqual(api.inventory, 1)
        self.assertIsNone(api.description)
        self.assertIsNone(api.variables)

    def test_create_with_inventory_name_resolves_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 42
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleGroup(name="g", inventory="Production")
        api = GroupTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_called_once_with("inventories", "name", "Production", service="controller")
        self.assertEqual(api.inventory, 42)

    def test_create_with_inventory_id_skips_lookup(self):
        ansible = AnsibleGroup(name="g", inventory="42")
        api = GroupTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.inventory, 42)

    def test_update_with_new_name(self):
        ansible = AnsibleGroup(name="old", inventory="1", new_name="new")
        api = GroupTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "new")

    def test_update_without_new_name_echoes(self):
        ansible = AnsibleGroup(name="keep", inventory="1")
        api = GroupTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "keep")

    def test_from_api_returns_ansible_instance(self):
        api_data = {"id": 99, "name": "webservers", "description": "Web servers", "inventory": 5, "variables": '{"http_port": 80}'}
        ansible = GroupTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleGroup)
        self.assertEqual(ansible.id, 99)
        self.assertEqual(ansible.name, "webservers")
        self.assertEqual(ansible.inventory, "5")
        self.assertEqual(ansible.variables, '{"http_port": 80}')

    def test_from_api_handles_missing_fields(self):
        ansible = GroupTransformMixin_v2.from_api({"name": "bare", "inventory": 1}, {})
        self.assertEqual(ansible.name, "bare")
        self.assertIsNone(ansible.description)
        self.assertIsNone(ansible.variables)
        self.assertIsNone(ansible.id)

    def test_endpoint_operations_use_controller_paths(self):
        ops = GroupTransformMixin_v2.get_endpoint_operations()
        for op_name, op in ops.items():
            self.assertTrue(op.path.startswith("/api/controller/v2/groups"), f"{op_name} path wrong: {op.path}")

    def test_lookup_field_is_name(self):
        self.assertEqual(GroupTransformMixin_v2.get_lookup_field(), "name")

    def test_id_passthrough_for_update(self):
        ansible = AnsibleGroup(name="g", inventory="1", id=99)
        api = GroupTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 99)


if __name__ == "__main__":
    unittest.main()
