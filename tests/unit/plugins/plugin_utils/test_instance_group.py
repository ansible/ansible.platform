# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for instance_group v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.instance_group import AnsibleInstanceGroup  # noqa: E402
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.instance_group import InstanceGroupTransformMixin_v2  # noqa: E402


class TestInstanceGroupTransform(unittest.TestCase):
    """Ansible <-> API round-trip tests for instance_group."""

    def test_create_includes_all_fields(self):
        ansible = AnsibleInstanceGroup(
            name="MyGroup",
            credential="5",
            is_container_group=True,
            policy_instance_percentage=50,
            policy_instance_minimum=2,
            max_concurrent_jobs=10,
            max_forks=100,
            policy_instance_list=["host1", "host2"],
            pod_spec_override="apiVersion: v1",
        )
        api = InstanceGroupTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "MyGroup")
        self.assertEqual(api.credential, 5)
        self.assertIs(api.is_container_group, True)
        self.assertEqual(api.policy_instance_percentage, 50)
        self.assertEqual(api.policy_instance_minimum, 2)
        self.assertEqual(api.max_concurrent_jobs, 10)
        self.assertEqual(api.max_forks, 100)
        self.assertEqual(api.policy_instance_list, ["host1", "host2"])
        self.assertEqual(api.pod_spec_override, "apiVersion: v1")

    def test_create_omits_unset_fields(self):
        ansible = AnsibleInstanceGroup(name="minimal")
        api = InstanceGroupTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "minimal")
        self.assertIsNone(api.credential)
        self.assertIsNone(api.is_container_group)
        self.assertIsNone(api.max_concurrent_jobs)

    def test_create_with_credential_name_resolves_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 42
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleInstanceGroup(name="grp", credential="K8s Cred")
        api = InstanceGroupTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_called_once_with("credentials", "name", "K8s Cred", service="controller")
        self.assertEqual(api.credential, 42)

    def test_create_with_credential_id_skips_lookup(self):
        ansible = AnsibleInstanceGroup(name="grp", credential="42")
        api = InstanceGroupTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.credential, 42)

    def test_update_with_new_name(self):
        ansible = AnsibleInstanceGroup(name="old", new_name="new")
        api = InstanceGroupTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "new")

    def test_update_without_new_name_echoes(self):
        ansible = AnsibleInstanceGroup(name="keep")
        api = InstanceGroupTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "keep")

    def test_update_numeric_name_not_echoed(self):
        ansible = AnsibleInstanceGroup(name="42")
        api = InstanceGroupTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertIsNone(api.name)

    def test_policy_instance_list_passed_through(self):
        ansible = AnsibleInstanceGroup(name="grp", policy_instance_list=["node1", "node2"])
        api = InstanceGroupTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.policy_instance_list, ["node1", "node2"])

    def test_from_api_returns_ansible_instance(self):
        api_data = {
            "id": 99,
            "name": "MyGroup",
            "credential": 5,
            "is_container_group": True,
            "policy_instance_percentage": 50,
            "policy_instance_minimum": 2,
            "max_concurrent_jobs": 10,
            "max_forks": 100,
            "policy_instance_list": ["host1"],
            "pod_spec_override": "spec",
        }
        ansible = InstanceGroupTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleInstanceGroup)
        self.assertEqual(ansible.id, 99)
        self.assertEqual(ansible.name, "MyGroup")
        self.assertEqual(ansible.credential, "5")
        self.assertIs(ansible.is_container_group, True)
        self.assertEqual(ansible.policy_instance_list, ["host1"])

    def test_from_api_handles_null_credential(self):
        ansible = InstanceGroupTransformMixin_v2.from_api({"name": "grp", "credential": None}, {})
        self.assertIsNone(ansible.credential)

    def test_from_api_handles_missing_fields(self):
        ansible = InstanceGroupTransformMixin_v2.from_api({"name": "bare"}, {})
        self.assertEqual(ansible.name, "bare")
        self.assertIsNone(ansible.credential)
        self.assertIsNone(ansible.is_container_group)
        self.assertIsNone(ansible.id)

    def test_endpoint_operations_use_controller_paths(self):
        ops = InstanceGroupTransformMixin_v2.get_endpoint_operations()
        for op_name, op in ops.items():
            self.assertTrue(
                op.path.startswith("/api/controller/v2/instance_groups"),
                f"{op_name} path should start with /api/controller/v2/instance_groups, got {op.path}",
            )

    def test_lookup_field_is_name(self):
        self.assertEqual(InstanceGroupTransformMixin_v2.get_lookup_field(), "name")

    def test_id_passthrough_for_update(self):
        ansible = AnsibleInstanceGroup(name="grp", id=99)
        api = InstanceGroupTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 99)


if __name__ == "__main__":
    unittest.main()
