# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for controller_project v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_project import AnsibleControllerProject  # noqa: E402
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_project import ControllerProjectTransformMixin_v2  # noqa: E402


class TestControllerProjectTransform(unittest.TestCase):
    """Ansible <-> API round-trip tests for controller_project."""

    def test_create_includes_all_fields(self):
        ansible = AnsibleControllerProject(
            name="My Project",
            organization="1",
            description="Test project",
            scm_type="git",
            scm_url="https://github.com/test/repo.git",
            scm_branch="main",
            credential="5",
            scm_clean=True,
            allow_override=False,
            timeout=300,
        )
        api = ControllerProjectTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "My Project")
        self.assertEqual(api.organization, 1)
        self.assertEqual(api.scm_type, "git")
        self.assertEqual(api.scm_url, "https://github.com/test/repo.git")
        self.assertEqual(api.scm_branch, "main")
        self.assertEqual(api.credential, 5)
        self.assertIs(api.scm_clean, True)
        self.assertIs(api.allow_override, False)
        self.assertEqual(api.timeout, 300)

    def test_create_omits_unset_fields(self):
        ansible = AnsibleControllerProject(name="minimal")
        api = ControllerProjectTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "minimal")
        self.assertIsNone(api.organization)
        self.assertIsNone(api.scm_type)
        self.assertIsNone(api.credential)

    def test_org_lookup_uses_default_service(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 42
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleControllerProject(name="proj", organization="Default")
        ControllerProjectTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("organizations", "name", "Default")

    def test_credential_lookup_uses_controller_service(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 10
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleControllerProject(name="proj", credential="My Cred")
        ControllerProjectTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("credentials", "name", "My Cred", service="controller")

    def test_default_environment_lookup_uses_controller_service(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 20
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleControllerProject(name="proj", default_environment="My EE")
        ControllerProjectTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("execution_environments", "name", "My EE", service="controller")

    def test_signature_validation_credential_lookup(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 30
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleControllerProject(name="proj", signature_validation_credential="Sig Cred")
        ControllerProjectTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("credentials", "name", "Sig Cred", service="controller")

    def test_update_with_new_name(self):
        ansible = AnsibleControllerProject(name="old", new_name="new")
        api = ControllerProjectTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "new")

    def test_update_without_new_name_echoes(self):
        ansible = AnsibleControllerProject(name="keep")
        api = ControllerProjectTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "keep")

    def test_from_api_returns_ansible_instance(self):
        api_data = {
            "id": 99,
            "name": "My Project",
            "description": "Test",
            "scm_type": "git",
            "scm_url": "https://github.com/test/repo.git",
            "scm_branch": "main",
            "credential": 5,
            "organization": 1,
            "default_environment": 10,
            "signature_validation_credential": None,
            "scm_clean": True,
            "allow_override": False,
            "timeout": 300,
        }
        ansible = ControllerProjectTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleControllerProject)
        self.assertEqual(ansible.id, 99)
        self.assertEqual(ansible.name, "My Project")
        self.assertEqual(ansible.organization, "1")
        self.assertEqual(ansible.credential, "5")
        self.assertEqual(ansible.default_environment, "10")
        self.assertIsNone(ansible.signature_validation_credential)

    def test_from_api_handles_missing_fields(self):
        ansible = ControllerProjectTransformMixin_v2.from_api({"name": "bare"}, {})
        self.assertEqual(ansible.name, "bare")
        self.assertIsNone(ansible.scm_type)
        self.assertIsNone(ansible.credential)
        self.assertIsNone(ansible.id)

    def test_endpoint_operations_use_controller_paths(self):
        ops = ControllerProjectTransformMixin_v2.get_endpoint_operations()
        for op_name, op in ops.items():
            self.assertTrue(
                op.path.startswith("/api/controller/v2/projects"),
                f"{op_name} path should start with /api/controller/v2/projects, got {op.path}",
            )

    def test_lookup_field_is_name(self):
        self.assertEqual(ControllerProjectTransformMixin_v2.get_lookup_field(), "name")

    def test_id_passthrough_for_update(self):
        ansible = AnsibleControllerProject(name="proj", id=99)
        api = ControllerProjectTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 99)

    def test_fk_id_skips_lookup(self):
        ansible = AnsibleControllerProject(name="proj", organization="42", credential="10")
        api = ControllerProjectTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.organization, 42)
        self.assertEqual(api.credential, 10)


if __name__ == "__main__":
    unittest.main()
