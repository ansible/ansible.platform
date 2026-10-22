# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for instance v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.instance import AnsibleInstance  # noqa: E402
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.instance import InstanceTransformMixin_v2  # noqa: E402


class TestInstanceTransform(unittest.TestCase):
    """Ansible <-> API round-trip tests for instance."""

    def test_create_includes_all_fields(self):
        ansible = AnsibleInstance(
            hostname="exec01.example.com",
            capacity_adjustment=0.5,
            enabled=True,
            managed_by_policy=True,
            node_type="execution",
            node_state="installed",
            listener_port=27199,
            peers_from_control_nodes=True,
        )
        api = InstanceTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.hostname, "exec01.example.com")
        self.assertEqual(api.capacity_adjustment, 0.5)
        self.assertIs(api.enabled, True)
        self.assertIs(api.managed_by_policy, True)
        self.assertEqual(api.node_type, "execution")
        self.assertEqual(api.node_state, "installed")
        self.assertEqual(api.listener_port, 27199)
        self.assertIs(api.peers_from_control_nodes, True)

    def test_create_omits_unset_fields(self):
        ansible = AnsibleInstance(hostname="minimal.example.com")
        api = InstanceTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.hostname, "minimal.example.com")
        self.assertIsNone(api.capacity_adjustment)
        self.assertIsNone(api.enabled)
        self.assertIsNone(api.node_type)

    def test_update_echoes_hostname(self):
        ansible = AnsibleInstance(hostname="exec01.example.com")
        api = InstanceTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.hostname, "exec01.example.com")

    def test_from_api_normalizes_capacity_adjustment_string_to_float(self):
        ansible = InstanceTransformMixin_v2.from_api({"hostname": "h", "capacity_adjustment": "0.90"}, {})
        self.assertIsInstance(ansible.capacity_adjustment, float)
        self.assertAlmostEqual(ansible.capacity_adjustment, 0.9)

    def test_from_api_returns_ansible_instance(self):
        api_data = {
            "id": 42,
            "hostname": "exec01.example.com",
            "capacity_adjustment": 0.75,
            "enabled": True,
            "managed_by_policy": False,
            "node_type": "execution",
            "node_state": "installed",
            "listener_port": 27199,
            "peers_from_control_nodes": True,
        }
        ansible = InstanceTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleInstance)
        self.assertEqual(ansible.id, 42)
        self.assertEqual(ansible.hostname, "exec01.example.com")
        self.assertEqual(ansible.capacity_adjustment, 0.75)
        self.assertIs(ansible.enabled, True)
        self.assertEqual(ansible.node_type, "execution")

    def test_from_api_handles_missing_fields(self):
        ansible = InstanceTransformMixin_v2.from_api({"hostname": "bare.example.com"}, {})
        self.assertEqual(ansible.hostname, "bare.example.com")
        self.assertIsNone(ansible.capacity_adjustment)
        self.assertIsNone(ansible.id)

    def test_endpoint_operations_use_controller_paths(self):
        ops = InstanceTransformMixin_v2.get_endpoint_operations()
        for op_name, op in ops.items():
            self.assertTrue(
                op.path.startswith("/api/controller/v2/instances"),
                f"{op_name} path should start with /api/controller/v2/instances, got {op.path}",
            )

    def test_no_delete_endpoint(self):
        ops = InstanceTransformMixin_v2.get_endpoint_operations()
        self.assertNotIn("delete", ops)

    def test_lookup_field_is_hostname(self):
        self.assertEqual(InstanceTransformMixin_v2.get_lookup_field(), "hostname")

    def test_id_passthrough_for_update(self):
        ansible = AnsibleInstance(hostname="exec01.example.com", id=42)
        api = InstanceTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 42)

    def test_deprovisioning_node_state(self):
        ansible = AnsibleInstance(hostname="exec01.example.com", node_state="deprovisioning")
        api = InstanceTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.node_state, "deprovisioning")


if __name__ == "__main__":
    unittest.main()
