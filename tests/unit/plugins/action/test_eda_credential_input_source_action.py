# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the eda_credential_input_source action plugin and transform mixin."""

import unittest
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.action.eda_credential_input_source import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.eda_credential_input_source import (
    AnsibleEdaCredentialInputSource,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_credential_input_source import (
    APIEdaCredentialInputSource_v1,
    EdaCredentialInputSourceTransformMixin_v1,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext


class TestAnsibleEdaCredentialInputSourceModel(unittest.TestCase):
    """Test the Ansible-side dataclass."""

    def test_required_fields(self):
        """Composite key fields are required positional args."""
        obj = AnsibleEdaCredentialInputSource(
            input_field_name="password",
            target_credential="my_target",
            source_credential="my_source",
        )
        self.assertEqual(obj.input_field_name, "password")
        self.assertEqual(obj.target_credential, "my_target")
        self.assertEqual(obj.source_credential, "my_source")
        self.assertIsNone(obj.description)
        self.assertIsNone(obj.metadata)
        self.assertIsNone(obj.organization_name)
        self.assertEqual(obj.state, "present")
        self.assertIsNone(obj.id)

    def test_all_fields(self):
        """All fields can be set."""
        obj = AnsibleEdaCredentialInputSource(
            input_field_name="password",
            target_credential="my_target",
            source_credential="my_source",
            description="test desc",
            metadata={"secret_path": "/secret"},
            organization_name="Default",
            state="absent",
            id=42,
        )
        self.assertEqual(obj.description, "test desc")
        self.assertEqual(obj.metadata, {"secret_path": "/secret"})
        self.assertEqual(obj.organization_name, "Default")
        self.assertEqual(obj.state, "absent")
        self.assertEqual(obj.id, 42)


class TestEdaCredentialInputSourceTransform(unittest.TestCase):
    """Test the transform mixin for EDA credential input source."""

    def _make_context(self, lookup_map: Optional[Dict[str, Any]] = None) -> TransformContext:
        """Create a TransformContext with a mock manager.

        Args:
            lookup_map: Optional dict mapping (endpoint, value) -> ID
                for lookup_resource_id simulation.
        """
        manager = MagicMock()
        if lookup_map:

            def _lookup(endpoint, field, value, service="gateway"):
                key = (endpoint, value)
                if key in lookup_map:
                    return lookup_map[key]
                raise ValueError(f"Not found: {endpoint}/{value}")

            manager.lookup_resource_id.side_effect = _lookup
        context = MagicMock(spec=TransformContext)
        context.manager = manager
        return context

    def test_from_ansible_data_resolves_credentials_via_eda(self):
        """FK resolution for target and source credentials uses eda-credentials with service=eda."""
        lookup_map = {
            ("eda-credentials", "my_target"): 10,
            ("eda-credentials", "my_source"): 20,
        }
        context = self._make_context(lookup_map)

        ansible_obj = AnsibleEdaCredentialInputSource(
            input_field_name="password",
            target_credential="my_target",
            source_credential="my_source",
        )

        api_obj = EdaCredentialInputSourceTransformMixin_v1.from_ansible_data(ansible_obj, context)

        self.assertIsInstance(api_obj, APIEdaCredentialInputSource_v1)
        self.assertEqual(api_obj.target_credential, 10)
        self.assertEqual(api_obj.source_credential, 20)
        self.assertEqual(api_obj.input_field_name, "password")

        # Verify service="eda" was passed for both credential lookups
        calls = context.manager.lookup_resource_id.call_args_list
        for call in calls:
            self.assertEqual(call.args[0], "eda-credentials")
            self.assertEqual(call.kwargs.get("service", call.args[3] if len(call.args) > 3 else "gateway"), "eda")

    def test_from_ansible_data_numeric_ids_pass_through(self):
        """Numeric credential IDs bypass FK resolution."""
        context = self._make_context()

        ansible_obj = AnsibleEdaCredentialInputSource(
            input_field_name="password",
            target_credential="10",
            source_credential="20",
        )

        api_obj = EdaCredentialInputSourceTransformMixin_v1.from_ansible_data(ansible_obj, context)

        self.assertEqual(api_obj.target_credential, 10)
        self.assertEqual(api_obj.source_credential, 20)
        # No lookup calls should have been made
        context.manager.lookup_resource_id.assert_not_called()

    def test_from_ansible_data_resolves_organization(self):
        """Organization name resolves via organizations endpoint (gateway service)."""
        lookup_map = {
            ("eda-credentials", "my_target"): 10,
            ("eda-credentials", "my_source"): 20,
            ("organizations", "Default"): 1,
        }
        context = self._make_context(lookup_map)

        ansible_obj = AnsibleEdaCredentialInputSource(
            input_field_name="password",
            target_credential="my_target",
            source_credential="my_source",
            organization_name="Default",
        )

        api_obj = EdaCredentialInputSourceTransformMixin_v1.from_ansible_data(ansible_obj, context)

        self.assertEqual(api_obj.organization_id, 1)
        # Verify organization lookup uses default service (gateway)
        org_call = [c for c in context.manager.lookup_resource_id.call_args_list if c.args[0] == "organizations"]
        self.assertEqual(len(org_call), 1)

    def test_from_ansible_data_optional_fields(self):
        """Description and metadata are passed through when set."""
        context = self._make_context()

        ansible_obj = AnsibleEdaCredentialInputSource(
            input_field_name="password",
            target_credential="10",
            source_credential="20",
            description="test description",
            metadata={"secret_path": "secret/myapp", "secret_key": "password"},
        )

        api_obj = EdaCredentialInputSourceTransformMixin_v1.from_ansible_data(ansible_obj, context)

        self.assertEqual(api_obj.description, "test description")
        self.assertEqual(api_obj.metadata, {"secret_path": "secret/myapp", "secret_key": "password"})

    def test_from_api_round_trip(self):
        """from_api converts API response to Ansible dataclass."""
        context = self._make_context()

        api_response = {
            "id": 42,
            "input_field_name": "password",
            "target_credential": 10,
            "source_credential": 20,
            "description": "test desc",
            "metadata": {"secret_path": "/secret"},
        }

        ansible_obj = EdaCredentialInputSourceTransformMixin_v1.from_api(api_response, context)

        self.assertIsInstance(ansible_obj, AnsibleEdaCredentialInputSource)
        self.assertEqual(ansible_obj.id, 42)
        self.assertEqual(ansible_obj.input_field_name, "password")
        self.assertEqual(ansible_obj.target_credential, "10")
        self.assertEqual(ansible_obj.source_credential, "20")
        self.assertEqual(ansible_obj.description, "test desc")
        self.assertEqual(ansible_obj.metadata, {"secret_path": "/secret"})

    def test_from_api_missing_optional_fields(self):
        """from_api handles missing optional fields gracefully."""
        context = self._make_context()

        api_response = {
            "id": 1,
            "input_field_name": "token",
            "target_credential": 5,
            "source_credential": 8,
        }

        ansible_obj = EdaCredentialInputSourceTransformMixin_v1.from_api(api_response, context)

        self.assertIsNone(ansible_obj.description)
        self.assertIsNone(ansible_obj.metadata)

    def test_get_lookup_field(self):
        """Lookup field is input_field_name for composite key matching."""
        self.assertEqual(EdaCredentialInputSourceTransformMixin_v1.get_lookup_field(), "input_field_name")

    def test_get_find_list_query_params(self):
        """Query params include target_credential and source_credential for composite key lookup."""
        api_obj = APIEdaCredentialInputSource_v1(
            target_credential=10,
            source_credential=20,
            input_field_name="password",
        )

        params = EdaCredentialInputSourceTransformMixin_v1.get_find_list_query_params(api_obj)

        self.assertEqual(params, {"target_credential": 10, "source_credential": 20})

    def test_get_find_list_query_params_no_source(self):
        """Query params with only target_credential."""
        api_obj = APIEdaCredentialInputSource_v1(
            target_credential=10,
            input_field_name="password",
        )

        params = EdaCredentialInputSourceTransformMixin_v1.get_find_list_query_params(api_obj)

        self.assertEqual(params, {"target_credential": 10})

    def test_get_find_list_query_params_empty(self):
        """Query params are empty when no FK IDs are set."""
        api_obj = APIEdaCredentialInputSource_v1(
            input_field_name="password",
        )

        params = EdaCredentialInputSourceTransformMixin_v1.get_find_list_query_params(api_obj)

        self.assertEqual(params, {})

    def test_get_endpoint_operations_paths(self):
        """Endpoint operations use EDA hyphenated paths."""
        ops = EdaCredentialInputSourceTransformMixin_v1.get_endpoint_operations()

        self.assertIn("create", ops)
        self.assertIn("update", ops)
        self.assertIn("delete", ops)
        self.assertIn("get", ops)
        self.assertIn("list", ops)

        # All paths use /api/eda/v1/ prefix and hyphenated endpoint
        for op_name, op in ops.items():
            self.assertTrue(
                op.path.startswith("/api/eda/v1/credential-input-sources"),
                f"Operation '{op_name}' path '{op.path}' does not use EDA endpoint",
            )

    def test_update_operation_limited_fields(self):
        """Update operation only allows description and metadata changes."""
        ops = EdaCredentialInputSourceTransformMixin_v1.get_endpoint_operations()
        update_fields = ops["update"].fields

        self.assertIn("description", update_fields)
        self.assertIn("metadata", update_fields)
        # Identity fields should NOT be updatable
        self.assertNotIn("input_field_name", update_fields)
        self.assertNotIn("target_credential", update_fields)
        self.assertNotIn("source_credential", update_fields)


class TestEdaCredentialInputSourceActionPlugin(unittest.TestCase):
    """Test the action plugin configuration."""

    def test_module_name(self):
        """Module name is set correctly."""
        self.assertEqual(ActionModule.MODULE_NAME, "eda_credential_input_source")

    def test_model_class(self):
        """Model class is the correct Ansible dataclass."""
        self.assertEqual(ActionModule.MODEL_CLASS, AnsibleEdaCredentialInputSource)


if __name__ == "__main__":
    unittest.main()
