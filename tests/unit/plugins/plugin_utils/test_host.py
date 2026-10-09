# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for host v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.host import (  # noqa: E402
    AnsibleHost,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.host import (  # noqa: E402
    HostTransformMixin_v2,
)


class TestHostTransform(unittest.TestCase):
    """Ansible <-> API round-trip tests for host."""

    def test_post_init_normalizes_dict_to_json(self):
        ansible = AnsibleHost(name="h", inventory="1", variables={"foo": "bar"})
        self.assertIsInstance(ansible.variables, str)
        self.assertEqual(json.loads(ansible.variables), {"foo": "bar"})

    def test_post_init_preserves_string(self):
        ansible = AnsibleHost(name="h", inventory="1", variables='{"foo": "bar"}')
        self.assertEqual(ansible.variables, '{"foo": "bar"}')

    def test_create_includes_all_fields(self):
        ansible = AnsibleHost(
            name="webserver01",
            inventory="5",
            description="Web server",
            enabled=True,
            instance_id="i-abc123",
            variables={"http_port": 8080},
        )
        api = HostTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "webserver01")
        self.assertEqual(api.inventory, 5)
        self.assertEqual(api.description, "Web server")
        self.assertIs(api.enabled, True)
        self.assertEqual(api.instance_id, "i-abc123")
        self.assertEqual(api.variables, json.dumps({"http_port": 8080}))

    def test_create_omits_unset_optional_fields(self):
        ansible = AnsibleHost(name="minimal", inventory="1")
        api = HostTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "minimal")
        self.assertEqual(api.inventory, 1)
        self.assertIsNone(api.description)
        self.assertIsNone(api.enabled)
        self.assertIsNone(api.instance_id)
        self.assertIsNone(api.variables)

    def test_create_with_inventory_name_resolves_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 42
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleHost(name="host1", inventory="Production")
        api = HostTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_called_once_with("inventories", "name", "Production", service="controller")
        self.assertEqual(api.inventory, 42)

    def test_create_with_inventory_id_skips_lookup(self):
        ansible = AnsibleHost(name="host1", inventory="42")
        api = HostTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.inventory, 42)

    def test_update_with_new_name(self):
        ansible = AnsibleHost(name="old", inventory="1", new_name="new")
        api = HostTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "new")

    def test_update_without_new_name_echoes(self):
        ansible = AnsibleHost(name="keep", inventory="1")
        api = HostTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "keep")

    def test_update_numeric_name_not_echoed(self):
        ansible = AnsibleHost(name="42", inventory="1")
        api = HostTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertIsNone(api.name)

    def test_variables_dict_normalized_then_serialized(self):
        ansible = AnsibleHost(name="h", inventory="1", variables={"foo": "bar", "num": 42})
        # __post_init__ already normalized dict to JSON string
        self.assertIsInstance(ansible.variables, str)
        api = HostTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        parsed = json.loads(api.variables)
        self.assertEqual(parsed, {"foo": "bar", "num": 42})

    def test_variables_string_passed_through(self):
        ansible = AnsibleHost(name="h", inventory="1", variables='{"already": "json"}')
        api = HostTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.variables, '{"already": "json"}')

    def test_from_api_returns_ansible_instance(self):
        api_data = {
            "id": 99,
            "name": "webserver01",
            "description": "Web server",
            "inventory": 5,
            "enabled": True,
            "instance_id": "i-abc123",
            "variables": '{"http_port": 8080}',
        }
        ansible = HostTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleHost)
        self.assertEqual(ansible.id, 99)
        self.assertEqual(ansible.name, "webserver01")
        self.assertEqual(ansible.inventory, "5")
        self.assertIs(ansible.enabled, True)
        self.assertEqual(ansible.variables, '{"http_port": 8080}')

    def test_from_api_preserves_json_string(self):
        ansible = HostTransformMixin_v2.from_api({"name": "h", "inventory": 1, "variables": '{"key": "val"}'}, {})
        self.assertEqual(ansible.variables, '{"key": "val"}')

    def test_from_api_handles_empty_variables(self):
        ansible = HostTransformMixin_v2.from_api({"name": "h", "inventory": 1, "variables": ""}, {})
        self.assertEqual(ansible.variables, "")

    def test_from_api_handles_missing_fields(self):
        ansible = HostTransformMixin_v2.from_api({"name": "bare", "inventory": 1}, {})
        self.assertEqual(ansible.name, "bare")
        self.assertIsNone(ansible.description)
        self.assertIsNone(ansible.enabled)
        self.assertIsNone(ansible.variables)
        self.assertIsNone(ansible.id)

    def test_endpoint_operations_use_controller_paths(self):
        ops = HostTransformMixin_v2.get_endpoint_operations()
        for op_name, op in ops.items():
            self.assertTrue(
                op.path.startswith("/api/controller/v2/hosts"),
                f"{op_name} path should start with /api/controller/v2/hosts, got {op.path}",
            )

    def test_lookup_field_is_name(self):
        self.assertEqual(HostTransformMixin_v2.get_lookup_field(), "name")

    def test_id_passthrough_for_update(self):
        ansible = AnsibleHost(name="h", inventory="1", id=99)
        api = HostTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 99)


if __name__ == "__main__":
    unittest.main()
