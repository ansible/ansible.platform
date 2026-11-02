"""Tests for EDA credential API transforms."""

import unittest
from unittest.mock import MagicMock, call

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.eda_credential import AnsibleEdaCredential
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_credential import EdaCredentialTransformMixin_v1


class TestEdaCredentialTransform(unittest.TestCase):
    """Cover reference resolution and API response normalization."""

    def test_from_ansible_data_resolves_eda_references_uniquely(self):
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = [11, 1]
        credential = AnsibleEdaCredential(
            name="deploy-key",
            credential_type="Source Control",
            organization="Default",
            inputs={"username": "robot"},
        )

        api_data = EdaCredentialTransformMixin_v1.from_ansible_data(credential, {"operation": "create", "manager": manager})

        self.assertEqual(api_data.credential_type_id, 11)
        self.assertEqual(api_data.organization_id, 1)
        manager.lookup_resource_id.assert_has_calls(
            [
                call("credential-types", "name", "Source Control", service="eda", require_unique=True),
                call("organizations", "name", "Default", service="eda", require_unique=True),
            ]
        )

    def test_find_query_is_scoped_by_organization_id(self):
        credential = AnsibleEdaCredential(name="deploy-key", organization="1")
        manager = MagicMock()
        api_data = EdaCredentialTransformMixin_v1.from_ansible_data(credential, {"operation": "find", "manager": manager})

        self.assertEqual(EdaCredentialTransformMixin_v1.get_find_list_query_params(api_data), {"organization_id": 1})
        manager.lookup_resource_id.assert_not_called()

    def test_from_api_accepts_nested_and_flat_foreign_keys(self):
        nested = EdaCredentialTransformMixin_v1.from_api(
            {
                "id": 7,
                "name": "nested",
                "credential_type": {"id": 11, "name": "Source Control"},
                "organization": {"id": 1, "name": "Default"},
            },
            {},
        )
        flat = EdaCredentialTransformMixin_v1.from_api(
            {"id": 8, "name": "flat", "credential_type_id": 11, "organization_id": 1},
            {},
        )

        self.assertEqual((nested.credential_type, nested.organization), ("11", "1"))
        self.assertEqual((flat.credential_type, flat.organization), ("11", "1"))

    def test_unresolved_named_reference_fails(self):
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = ValueError("not found")
        credential = AnsibleEdaCredential(name="deploy-key", credential_type="Missing type")

        with self.assertRaisesRegex(ValueError, "not found"):
            EdaCredentialTransformMixin_v1.from_ansible_data(credential, {"operation": "create", "manager": manager})


if __name__ == "__main__":
    unittest.main()
