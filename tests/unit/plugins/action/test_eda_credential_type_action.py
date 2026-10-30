# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the eda_credential_type action plugin."""

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.action.eda_credential_type import ActionModule


class TestEdaCredentialTypeTestState(unittest.TestCase):
    """Test eda_credential_type action plugin state=test behavior.

    CRUD states (present/absent) are delegated to BaseResourceActionPlugin and
    covered by the base class tests.  These tests cover the custom _run_test()
    path for state=test.
    """

    def _make_action(self, check_mode=False):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.check_mode = check_mode
        action._task.args = {}
        action._display = MagicMock()
        action._display.verbosity = 0
        return action

    def _make_manager(self, find_result=None, launch_result=None):
        manager = MagicMock()

        def execute_side_effect(operation, module_name, ansible_data):
            if operation == "find":
                if find_result:
                    return find_result
                raise ValueError("Not found")
            return {}

        manager.execute.side_effect = execute_side_effect
        manager.launch_resource.return_value = launch_result or {
            "success": True,
            "message": "Test passed",
        }
        return manager

    def _run_test_action(self, action, manager, validated_params):
        """Run the action plugin with _prepare_action patched for test state."""
        action._task.args = {"state": "test"}

        resource_data = {k: v for k, v in validated_params.items() if v is not None}
        write_only_data = {}
        for f in ("test_inputs", "test_metadata"):
            if f in resource_data:
                write_only_data[f] = resource_data.pop(f)

        prepared = {
            "result": {},
            "argspec": {"argument_spec": {}},
            "validated_params": validated_params,
            "resource_data": resource_data,
            "write_only_data": write_only_data,
            "manager": manager,
        }

        with patch.object(action, "_prepare_action", return_value=prepared):
            return action.run(task_vars={})

    def test_test_credential_type(self):
        """Test state finds credential type and POSTs to test endpoint."""
        action = self._make_action()
        manager = self._make_manager(
            find_result={"id": 100, "name": "My Cred Type"},
            launch_result={"success": True, "message": "Test passed", "details": {}},
        )

        result = self._run_test_action(
            action,
            manager,
            {
                "name": "My Cred Type",
                "state": "test",
                "test_inputs": {"username": "test_user"},
                "test_metadata": {"secret_path": "secret/myapp"},
                "new_name": None,
                "description": None,
                "inputs": None,
                "injectors": None,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])
        self.assertIn("test_result", result)
        self.assertTrue(result["test_result"]["success"])

        # Verify find was called
        manager.execute.assert_called_once()
        find_call = manager.execute.call_args
        self.assertEqual(find_call.kwargs["operation"], "find")

        # Verify launch_resource was called with correct URL and payload
        manager.launch_resource.assert_called_once()
        launch_call = manager.launch_resource.call_args
        self.assertEqual(launch_call.kwargs["launch_url"], "/api/eda/v1/credential-types/100/test/")
        self.assertEqual(launch_call.kwargs["service"], "eda")
        self.assertEqual(launch_call.kwargs["payload"]["inputs"], {"username": "test_user"})
        self.assertEqual(launch_call.kwargs["payload"]["metadata"], {"secret_path": "secret/myapp"})

    def test_test_nonexistent_credential_type_fails(self):
        """Test state fails when credential type does not exist."""
        action = self._make_action()
        manager = self._make_manager(find_result=None)

        result = self._run_test_action(
            action,
            manager,
            {
                "name": "Ghost Type",
                "state": "test",
                "test_inputs": {},
                "test_metadata": {},
                "new_name": None,
                "description": None,
                "inputs": None,
                "injectors": None,
            },
        )

        self.assertTrue(result["failed"])
        self.assertIn("not found", result["msg"].lower())
        manager.launch_resource.assert_not_called()

    def test_test_check_mode(self):
        """Check mode for test state returns without calling test endpoint."""
        action = self._make_action(check_mode=True)
        manager = self._make_manager(
            find_result={"id": 100, "name": "My Cred Type"},
        )

        result = self._run_test_action(
            action,
            manager,
            {
                "name": "My Cred Type",
                "state": "test",
                "test_inputs": {"username": "test_user"},
                "test_metadata": {},
                "new_name": None,
                "description": None,
                "inputs": None,
                "injectors": None,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])
        self.assertIn("test_result", result)
        self.assertIn("check mode", result["test_result"]["msg"])
        manager.launch_resource.assert_not_called()

    def test_test_with_no_inputs_or_metadata(self):
        """Test state works with no test_inputs or test_metadata provided."""
        action = self._make_action()
        manager = self._make_manager(
            find_result={"id": 200, "name": "Another Type"},
            launch_result={"success": True, "message": "OK"},
        )

        result = self._run_test_action(
            action,
            manager,
            {
                "name": "Another Type",
                "state": "test",
                "test_inputs": None,
                "test_metadata": None,
                "new_name": None,
                "description": None,
                "inputs": None,
                "injectors": None,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])

        # Verify launch_resource was called with empty payload
        manager.launch_resource.assert_called_once()
        launch_call = manager.launch_resource.call_args
        self.assertEqual(launch_call.kwargs["payload"], {})

    def test_find_reraises_non_not_found_errors(self):
        """ValueError not related to 'not found' is re-raised."""
        action = self._make_action()
        manager = MagicMock()
        manager.execute.side_effect = ValueError("Authentication failed")

        result = self._run_test_action(
            action,
            manager,
            {
                "name": "My Type",
                "state": "test",
                "test_inputs": {},
                "test_metadata": {},
                "new_name": None,
                "description": None,
                "inputs": None,
                "injectors": None,
            },
        )

        self.assertTrue(result["failed"])
        self.assertIn("Authentication failed", result["msg"])


class TestEdaCredentialTypeTransform(unittest.TestCase):
    """Test EDA credential type transform mixin round-trips."""

    def _make_context(self, operation="create"):
        """Create a TransformContext with required fields mocked."""
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext

        return TransformContext(
            manager=MagicMock(),
            session=MagicMock(),
            cache={},
            api_version="1",
            service="eda",
            operation=operation,
        )

    def test_from_ansible_data_create(self):
        """from_ansible_data for create includes name and fields."""
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.eda_credential_type import AnsibleEdaCredentialType
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_credential_type import EdaCredentialTypeTransformMixin_v1

        ansible_obj = AnsibleEdaCredentialType(
            name="Test Type",
            description="A test type",
            inputs={"fields": [{"id": "user", "type": "string", "label": "User"}]},
            injectors={"extra_vars": {"user": "{{ user }}"}},
        )
        context = self._make_context("create")
        api_obj = EdaCredentialTypeTransformMixin_v1.from_ansible_data(ansible_obj, context)

        self.assertEqual(api_obj.name, "Test Type")
        self.assertEqual(api_obj.description, "A test type")
        self.assertEqual(api_obj.inputs, {"fields": [{"id": "user", "type": "string", "label": "User"}]})
        self.assertEqual(api_obj.injectors, {"extra_vars": {"user": "{{ user }}"}})

    def test_from_ansible_data_update_with_new_name(self):
        """from_ansible_data for update uses new_name when set."""
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.eda_credential_type import AnsibleEdaCredentialType
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_credential_type import EdaCredentialTypeTransformMixin_v1

        ansible_obj = AnsibleEdaCredentialType(
            name="Old Name",
            new_name="New Name",
            inputs={"fields": []},
            injectors={},
            id=42,
        )
        context = self._make_context("update")
        api_obj = EdaCredentialTypeTransformMixin_v1.from_ansible_data(ansible_obj, context)

        self.assertEqual(api_obj.name, "New Name")
        self.assertEqual(api_obj.id, 42)

    def test_from_ansible_data_update_without_new_name(self):
        """from_ansible_data for update uses name when new_name is not set."""
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.eda_credential_type import AnsibleEdaCredentialType
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_credential_type import EdaCredentialTypeTransformMixin_v1

        ansible_obj = AnsibleEdaCredentialType(
            name="Same Name",
            description="Updated desc",
            inputs={"fields": []},
            injectors={},
            id=42,
        )
        context = self._make_context("update")
        api_obj = EdaCredentialTypeTransformMixin_v1.from_ansible_data(ansible_obj, context)

        self.assertEqual(api_obj.name, "Same Name")
        self.assertEqual(api_obj.description, "Updated desc")

    def test_from_api_round_trip(self):
        """from_api creates an AnsibleEdaCredentialType from API data."""
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_credential_type import EdaCredentialTypeTransformMixin_v1

        api_data = {
            "id": 10,
            "name": "My Type",
            "description": "desc",
            "inputs": {"fields": []},
            "injectors": {"extra_vars": {}},
        }
        context = self._make_context("find")
        ansible_obj = EdaCredentialTypeTransformMixin_v1.from_api(api_data, context)

        self.assertEqual(ansible_obj.name, "My Type")
        self.assertEqual(ansible_obj.description, "desc")
        self.assertEqual(ansible_obj.inputs, {"fields": []})
        self.assertEqual(ansible_obj.injectors, {"extra_vars": {}})
        self.assertEqual(ansible_obj.id, 10)

    def test_get_endpoint_operations_has_eda_paths(self):
        """Endpoint operations use EDA API v1 paths with hyphenated names."""
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_credential_type import EdaCredentialTypeTransformMixin_v1

        ops = EdaCredentialTypeTransformMixin_v1.get_endpoint_operations()

        self.assertIn("create", ops)
        self.assertIn("update", ops)
        self.assertIn("delete", ops)
        self.assertIn("get", ops)
        self.assertIn("list", ops)

        self.assertEqual(ops["create"].path, "/api/eda/v1/credential-types/")
        self.assertEqual(ops["update"].path, "/api/eda/v1/credential-types/{id}/")
        self.assertEqual(ops["create"].method, "POST")
        self.assertEqual(ops["update"].method, "PATCH")

    def test_get_lookup_field(self):
        """Lookup field is name."""
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_credential_type import EdaCredentialTypeTransformMixin_v1

        self.assertEqual(EdaCredentialTypeTransformMixin_v1.get_lookup_field(), "name")


if __name__ == "__main__":
    unittest.main()
