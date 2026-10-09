# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for execution_environment v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.execution_environment import (  # noqa: E402
    AnsibleExecutionEnvironment,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.execution_environment import (  # noqa: E402
    ExecutionEnvironmentTransformMixin_v2,
)


class TestExecutionEnvironmentTransform(unittest.TestCase):
    """Ansible <-> API round-trip tests for execution_environment."""

    def test_create_includes_all_fields(self):
        ansible = AnsibleExecutionEnvironment(
            name="My EE",
            image="quay.io/ansible/awx-ee:latest",
            description="Test EE",
            organization="1",
            credential="2",
            pull="always",
        )
        api = ExecutionEnvironmentTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "My EE")
        self.assertEqual(api.image, "quay.io/ansible/awx-ee:latest")
        self.assertEqual(api.description, "Test EE")
        self.assertEqual(api.organization, 1)
        self.assertEqual(api.credential, 2)
        self.assertEqual(api.pull, "always")

    def test_create_omits_unset_fields(self):
        ansible = AnsibleExecutionEnvironment(name="minimal")
        api = ExecutionEnvironmentTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "minimal")
        self.assertIsNone(api.image)
        self.assertIsNone(api.description)
        self.assertIsNone(api.organization)
        self.assertIsNone(api.credential)

    def test_create_with_org_name_resolves_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 42
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleExecutionEnvironment(name="ee", organization="Default")
        api = ExecutionEnvironmentTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_called_once_with("organizations", "name", "Default")
        self.assertEqual(api.organization, 42)

    def test_create_with_credential_name_resolves_with_controller_service(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 99
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleExecutionEnvironment(name="ee", credential="Registry Cred")
        api = ExecutionEnvironmentTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_called_once_with("credentials", "name", "Registry Cred", service="controller")
        self.assertEqual(api.credential, 99)

    def test_update_with_new_name(self):
        ansible = AnsibleExecutionEnvironment(name="old", new_name="new")
        api = ExecutionEnvironmentTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "new")

    def test_update_without_new_name_echoes(self):
        ansible = AnsibleExecutionEnvironment(name="keep")
        api = ExecutionEnvironmentTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "keep")

    def test_update_numeric_name_not_echoed(self):
        ansible = AnsibleExecutionEnvironment(name="42")
        api = ExecutionEnvironmentTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertIsNone(api.name)

    def test_from_api_returns_ansible_instance(self):
        api_data = {
            "id": 10,
            "name": "My EE",
            "image": "quay.io/ansible/awx-ee:latest",
            "description": "Test",
            "organization": 5,
            "credential": 3,
            "pull": "missing",
        }
        ansible = ExecutionEnvironmentTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleExecutionEnvironment)
        self.assertEqual(ansible.id, 10)
        self.assertEqual(ansible.name, "My EE")
        self.assertEqual(ansible.image, "quay.io/ansible/awx-ee:latest")
        self.assertEqual(ansible.organization, "5")
        self.assertEqual(ansible.credential, "3")
        self.assertEqual(ansible.pull, "missing")

    def test_from_api_handles_null_fks(self):
        ansible = ExecutionEnvironmentTransformMixin_v2.from_api({"name": "bare", "image": "img"}, {})
        self.assertIsNone(ansible.organization)
        self.assertIsNone(ansible.credential)
        self.assertIsNone(ansible.id)

    def test_endpoint_operations_use_controller_paths(self):
        ops = ExecutionEnvironmentTransformMixin_v2.get_endpoint_operations()
        for op_name, op in ops.items():
            self.assertTrue(
                op.path.startswith("/api/controller/v2/execution_environments"),
                f"{op_name} path should start with /api/controller/v2/execution_environments, got {op.path}",
            )

    def test_lookup_field_is_name(self):
        self.assertEqual(ExecutionEnvironmentTransformMixin_v2.get_lookup_field(), "name")

    def test_id_passthrough_for_update(self):
        ansible = AnsibleExecutionEnvironment(name="ee", id=99)
        api = ExecutionEnvironmentTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 99)


if __name__ == "__main__":
    unittest.main()
