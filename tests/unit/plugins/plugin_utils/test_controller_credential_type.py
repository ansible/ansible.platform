# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for controller_credential_type v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_credential_type import (  # noqa: E402
    AnsibleControllerCredentialType,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_credential_type import (  # noqa: E402
    ControllerCredentialTypeTransformMixin_v2,
)


class TestControllerCredentialTypeTransform(unittest.TestCase):
    """Ansible <-> API round-trip tests for controller_credential_type."""

    def test_create_includes_all_fields_and_managed_false(self):
        ansible = AnsibleControllerCredentialType(
            name="Nexus",
            kind="cloud",
            description="Nexus creds",
            inputs={"fields": [{"id": "user", "type": "string", "label": "User"}]},
            injectors={"extra_vars": {"nexus_user": "{{ user }}"}},
        )
        api = ControllerCredentialTypeTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "Nexus")
        self.assertEqual(api.kind, "cloud")
        self.assertEqual(api.description, "Nexus creds")
        self.assertEqual(api.inputs, {"fields": [{"id": "user", "type": "string", "label": "User"}]})
        self.assertEqual(api.injectors, {"extra_vars": {"nexus_user": "{{ user }}"}})
        self.assertIs(api.managed, False)

    def test_create_omits_unset_optional_fields(self):
        ansible = AnsibleControllerCredentialType(name="Minimal", kind="net")
        api = ControllerCredentialTypeTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "Minimal")
        self.assertEqual(api.kind, "net")
        self.assertIsNone(api.description)
        self.assertIsNone(api.inputs)
        self.assertIsNone(api.injectors)
        self.assertIs(api.managed, False)

    def test_update_with_new_name_sends_new_name_as_name(self):
        ansible = AnsibleControllerCredentialType(name="OldName", new_name="NewName", kind="cloud")
        api = ControllerCredentialTypeTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "NewName")

    def test_update_without_new_name_echoes_name(self):
        ansible = AnsibleControllerCredentialType(name="KeepName", kind="cloud")
        api = ControllerCredentialTypeTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "KeepName")

    def test_update_with_numeric_name_does_not_echo(self):
        ansible = AnsibleControllerCredentialType(name="42", kind="cloud")
        api = ControllerCredentialTypeTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertIsNone(api.name)

    def test_create_does_not_set_managed_on_update(self):
        ansible = AnsibleControllerCredentialType(name="Test", kind="cloud")
        api = ControllerCredentialTypeTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertIsNone(api.managed)

    def test_from_api_returns_ansible_instance(self):
        api_data = {
            "id": 42,
            "name": "Nexus",
            "description": "Nexus creds",
            "kind": "cloud",
            "inputs": {"fields": []},
            "injectors": {"extra_vars": {}},
        }
        ansible = ControllerCredentialTypeTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleControllerCredentialType)
        self.assertEqual(ansible.id, 42)
        self.assertEqual(ansible.name, "Nexus")
        self.assertEqual(ansible.kind, "cloud")
        self.assertEqual(ansible.description, "Nexus creds")
        self.assertEqual(ansible.inputs, {"fields": []})
        self.assertEqual(ansible.injectors, {"extra_vars": {}})

    def test_from_api_handles_missing_optional_fields(self):
        ansible = ControllerCredentialTypeTransformMixin_v2.from_api({"name": "Bare", "kind": "net"}, {})
        self.assertEqual(ansible.name, "Bare")
        self.assertEqual(ansible.kind, "net")
        self.assertIsNone(ansible.description)
        self.assertIsNone(ansible.inputs)
        self.assertIsNone(ansible.injectors)
        self.assertIsNone(ansible.id)

    def test_endpoint_operations_use_controller_paths(self):
        ops = ControllerCredentialTypeTransformMixin_v2.get_endpoint_operations()
        for op_name, op in ops.items():
            self.assertTrue(
                op.path.startswith("/api/controller/v2/credential_types"),
                f"{op_name} path should start with /api/controller/v2/credential_types, got {op.path}",
            )

    def test_lookup_field_is_name(self):
        self.assertEqual(ControllerCredentialTypeTransformMixin_v2.get_lookup_field(), "name")

    def test_id_passthrough_for_update(self):
        ansible = AnsibleControllerCredentialType(name="Test", kind="cloud", id=99)
        api = ControllerCredentialTypeTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 99)


if __name__ == "__main__":
    unittest.main()
