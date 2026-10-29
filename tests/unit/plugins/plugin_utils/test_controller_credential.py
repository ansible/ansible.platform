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

    def test_credential_type_fk_resolves(self):
        m = MagicMock()
        m.lookup_resource_id.return_value = 42
        ansible = AnsibleControllerCredential(name="c", credential_type="Machine")
        api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "create", "manager": m})
        m.lookup_resource_id.assert_any_call("credential_types", "name", "Machine", service="controller")
        self.assertEqual(api.credential_type, 42)

    def test_org_fk_default_service(self):
        m = MagicMock()
        m.lookup_resource_id.return_value = 1
        ansible = AnsibleControllerCredential(name="c", credential_type="1", organization="Default")
        ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "create", "manager": m})
        org_call = [c for c in m.lookup_resource_id.call_args_list if c[0][0] == "organizations"][0]
        self.assertNotIn("controller", str(org_call))

    def test_user_fk_by_username(self):
        m = MagicMock()
        m.lookup_resource_id.return_value = 5
        ansible = AnsibleControllerCredential(name="c", credential_type="1", user="admin")
        api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "create", "manager": m})
        m.lookup_resource_id.assert_any_call("users", "username", "admin")
        self.assertEqual(api.user, 5)

    def test_update_with_new_name(self):
        ansible = AnsibleControllerCredential(name="old", credential_type="1", new_name="new")
        api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "new")

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

    def test_id_passthrough(self):
        ansible = AnsibleControllerCredential(name="c", credential_type="1", id=99)
        api = ControllerCredentialTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 99)


if __name__ == "__main__":
    unittest.main()
