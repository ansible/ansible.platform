# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for credential_input_source v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.credential_input_source import (  # noqa: E402
    AnsibleCredentialInputSource,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.credential_input_source import (  # noqa: E402
    CredentialInputSourceTransformMixin_v2,
)


class TestCredentialInputSourceTransform(unittest.TestCase):
    """Ansible <-> API round-trip tests for credential_input_source."""

    def test_create_includes_all_fields(self):
        ansible = AnsibleCredentialInputSource(
            input_field_name="password",
            target_credential="5",
            source_credential="10",
            description="CyberArk lookup",
            metadata={"object_query": "Safe=MY_SAFE;Object=awxuser"},
        )
        api = CredentialInputSourceTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.input_field_name, "password")
        self.assertEqual(api.target_credential, 5)
        self.assertEqual(api.source_credential, 10)
        self.assertEqual(api.description, "CyberArk lookup")
        self.assertEqual(api.metadata, {"object_query": "Safe=MY_SAFE;Object=awxuser"})

    def test_create_omits_unset_fields(self):
        ansible = AnsibleCredentialInputSource(input_field_name="password", target_credential="5")
        api = CredentialInputSourceTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.input_field_name, "password")
        self.assertEqual(api.target_credential, 5)
        self.assertIsNone(api.source_credential)
        self.assertIsNone(api.description)
        self.assertIsNone(api.metadata)

    def test_target_credential_name_resolves_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 42
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleCredentialInputSource(input_field_name="password", target_credential="Demo Credential")
        api = CredentialInputSourceTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("credentials", "name", "Demo Credential", service="controller")
        self.assertEqual(api.target_credential, 42)

    def test_source_credential_name_resolves_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 99
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleCredentialInputSource(input_field_name="password", target_credential="5", source_credential="Vault Lookup")
        api = CredentialInputSourceTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("credentials", "name", "Vault Lookup", service="controller")
        self.assertEqual(api.source_credential, 99)

    def test_credential_id_skips_lookup(self):
        ansible = AnsibleCredentialInputSource(input_field_name="password", target_credential="42", source_credential="99")
        api = CredentialInputSourceTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.target_credential, 42)
        self.assertEqual(api.source_credential, 99)

    def test_metadata_dict_passed_through(self):
        ansible = AnsibleCredentialInputSource(
            input_field_name="password",
            target_credential="5",
            metadata={"path": "secret/data/myapp", "secret_key": "password"},
        )
        api = CredentialInputSourceTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.metadata, {"path": "secret/data/myapp", "secret_key": "password"})

    def test_from_api_returns_ansible_instance(self):
        api_data = {
            "id": 77,
            "input_field_name": "password",
            "target_credential": 42,
            "source_credential": 99,
            "description": "Vault lookup",
            "metadata": {"path": "secret/data/myapp"},
        }
        ansible = CredentialInputSourceTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleCredentialInputSource)
        self.assertEqual(ansible.id, 77)
        self.assertEqual(ansible.input_field_name, "password")
        self.assertEqual(ansible.target_credential, "42")
        self.assertEqual(ansible.source_credential, "99")
        self.assertEqual(ansible.metadata, {"path": "secret/data/myapp"})

    def test_from_api_handles_missing_fields(self):
        ansible = CredentialInputSourceTransformMixin_v2.from_api({"input_field_name": "password", "target_credential": 1}, {})
        self.assertEqual(ansible.input_field_name, "password")
        self.assertEqual(ansible.target_credential, "1")
        self.assertIsNone(ansible.source_credential)
        self.assertIsNone(ansible.metadata)
        self.assertIsNone(ansible.id)

    def test_endpoint_operations_use_controller_paths(self):
        ops = CredentialInputSourceTransformMixin_v2.get_endpoint_operations()
        for op_name, op in ops.items():
            self.assertTrue(
                op.path.startswith("/api/controller/v2/credential_input_sources"),
                f"{op_name} path should start with /api/controller/v2/credential_input_sources, got {op.path}",
            )

    def test_lookup_field_is_input_field_name(self):
        self.assertEqual(CredentialInputSourceTransformMixin_v2.get_lookup_field(), "input_field_name")

    def test_id_passthrough_for_update(self):
        ansible = AnsibleCredentialInputSource(input_field_name="password", target_credential="5", id=77)
        api = CredentialInputSourceTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 77)


if __name__ == "__main__":
    unittest.main()
