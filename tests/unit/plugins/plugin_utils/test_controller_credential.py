# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for controller_credential v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_credential import (  # noqa: E402
    AnsibleControllerCredential,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_credential import (  # noqa: E402
    ControllerCredentialTransformMixin_v2,
)


class TestControllerCredentialTransform(unittest.TestCase):
    def test_create_includes_all_fields(self):
        ansible = AnsibleControllerCredential(name="Cred", credential_type="1", description="Test", organization="1", inputs={"username": "admin"})
        api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "Cred")
        self.assertEqual(api.credential_type, 1)
        self.assertEqual(api.organization, 1)
        self.assertEqual(api.inputs, {"username": "admin"})

    def test_create_omits_unset_fields(self):
        ansible = AnsibleControllerCredential(name="minimal", credential_type="1")
        api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertIsNone(api.organization)
        self.assertIsNone(api.inputs)

    def test_update_secrets_false_omits_inputs_on_update(self):
        ansible = AnsibleControllerCredential(
            name="Cred",
            credential_type="1",
            inputs={"username": "admin"},
            update_secrets=False,
        )
        api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertIsNone(api.inputs)

    def test_update_secrets_true_includes_inputs_on_update(self):
        ansible = AnsibleControllerCredential(
            name="Cred",
            credential_type="1",
            inputs={"username": "admin"},
            update_secrets=True,
        )
        api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.inputs, {"username": "admin"})

    def test_credential_type_fk_resolves(self):
        m = MagicMock()
        m.lookup_resource_id.return_value = 42
        ansible = AnsibleControllerCredential(name="c", credential_type="Machine")
        api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "create", "manager": m})
        m.lookup_resource_id.assert_any_call("credential_types", "name", "Machine", service="controller")
        self.assertEqual(api.credential_type, 42)

    def test_org_fk_uses_controller_service(self):
        m = MagicMock()
        m.lookup_resource_id.return_value = 1
        ansible = AnsibleControllerCredential(name="c", credential_type="1", organization="Default")
        ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "create", "manager": m})
        org_call = [c for c in m.lookup_resource_id.call_args_list if c[0][0] == "organizations"][0]
        self.assertEqual(org_call.kwargs.get("service"), "controller")

    def test_user_fk_by_username(self):
        m = MagicMock()
        m.lookup_resource_id.return_value = 5
        ansible = AnsibleControllerCredential(name="c", credential_type="1", user="admin")
        api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "create", "manager": m})
        m.lookup_resource_id.assert_any_call("users", "username", "admin", service="controller")
        self.assertEqual(api.user, 5)

    def test_team_fk_uses_controller_service_and_organization_scope(self):
        m = MagicMock()
        m.lookup_resource_id.side_effect = [900, 31]
        ansible = AnsibleControllerCredential(name="c", credential_type="1", organization="Default", team="Ops")

        api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "create", "manager": m})

        self.assertEqual(api.organization, 900)
        self.assertEqual(api.team, 31)
        m.lookup_resource_id.assert_any_call("teams", "name", "Ops", service="controller", extra_query_params={"organization": 900})

    def test_update_with_new_name(self):
        ansible = AnsibleControllerCredential(name="old", credential_type="1", new_name="new")
        api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "new")

    def test_update_secrets_false_omits_inputs(self):
        ansible = AnsibleControllerCredential(
            name="Cred",
            credential_type="1",
            inputs={"username": "admin", "password": "secret"},
            update_secrets=False,
        )
        api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertIsNone(api.inputs)

    def test_create_includes_inputs_when_update_secrets_false(self):
        ansible = AnsibleControllerCredential(
            name="Cred",
            credential_type="1",
            inputs={"username": "admin", "password": "secret"},
            update_secrets=False,
        )
        api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.inputs, {"username": "admin", "password": "secret"})

    def test_from_api_returns_ansible_instance(self):
        api_data = {"id": 99, "name": "Cred", "credential_type": 5, "organization": 1, "user": None, "team": None}
        ansible = ControllerCredentialTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleControllerCredential)
        self.assertEqual(ansible.id, 99)
        self.assertEqual(ansible.credential_type, "5")
        self.assertIsNone(ansible.inputs)

    def test_endpoint_paths(self):
        ops = ControllerCredentialTransformMixin_v2.get_endpoint_operations()
        for op_name, op in ops.items():
            self.assertTrue(op.path.startswith("/api/controller/v2/credentials"), f"{op_name}: {op.path}")

    def test_lookup_field(self):
        self.assertEqual(ControllerCredentialTransformMixin_v2.get_lookup_field(), "name")

    def test_find_query_params_include_credential_type_and_owner_scope(self):
        cases = (
            ("organization", "20", {"credential_type": 2, "organization": 20}),
            ("user", "30", {"credential_type": 2, "user": 30}),
            ("team", "40", {"credential_type": 2, "team": 40}),
        )

        for owner_field, owner_value, expected in cases:
            with self.subTest(owner=owner_field):
                ansible = AnsibleControllerCredential(name="Shared", credential_type="2", **{owner_field: owner_value})
                api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "find"})

                self.assertEqual(ControllerCredentialTransformMixin_v2.get_find_list_query_params(api), expected)

    def test_find_requires_a_unique_match_within_scope(self):
        self.assertTrue(ControllerCredentialTransformMixin_v2.require_unique_lookup)

    def test_id_passthrough(self):
        ansible = AnsibleControllerCredential(name="c", credential_type="1", id=99)
        api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 99)


if __name__ == "__main__":
    unittest.main()
