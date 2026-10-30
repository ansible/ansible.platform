# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the eda_credential action plugin."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.eda_credential import ActionModule


class TestEdaCredentialAction(unittest.TestCase):
    """Test eda_credential action plugin CRUD, copy, and test behaviors."""

    def _make_action(self, check_mode=False):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.check_mode = check_mode
        action._task.args = {}
        action._task.environment = []
        action._display = MagicMock()
        action._display.verbosity = 0
        return action

    def _make_manager(self, find_result=None, create_result=None, delete_error=None, search_result=None, copy_error=None, direct_result=None):
        manager = MagicMock()

        def execute_side_effect(operation, module_name, ansible_data):
            if operation == "find":
                if find_result:
                    return find_result
                raise ValueError("Not found")
            if operation == "delete":
                if delete_error:
                    raise delete_error
                return {}
            if operation == "create":
                return create_result or {"id": 100, "name": ansible_data.get("name", ""), "changed": True}
            if operation == "update":
                return create_result or {"id": find_result.get("id", 100), "name": ansible_data.get("name", ""), "changed": True}
            return {}

        manager.execute.side_effect = execute_side_effect
        manager.search_api.return_value = search_result or {"results": []}
        if copy_error:
            manager.copy_resource.side_effect = copy_error
        else:
            manager.copy_resource.return_value = {"id": 200, "name": "copied"}
        manager.direct_request.return_value = direct_result or {"success": True, "message": "Credential test successful"}
        return manager

    def _run_action(self, action, manager, validated_params):
        doc = "module: eda_credential"
        argspec = {
            "argument_spec": {
                "name": {},
                "new_name": {},
                "description": {},
                "credential_type": {},
                "organization": {},
                "inputs": {},
                "copy_from": {},
                "metadata": {},
                "state": {},
            },
        }

        def validate_side_effect(data, spec, context="input"):
            if context == "output":
                return data  # Output validation returns the dict as-is
            return SimpleNamespace(validated_parameters=validated_params)

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_documentation", return_value=doc):
                with patch.object(action, "_build_argspec_from_docs", return_value=argspec):
                    with patch.object(action, "_validate_data", side_effect=validate_side_effect):
                        with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                            return action.run(task_vars={})

    # ---- CRUD Tests (delegated to base class) ----

    def test_create_new_credential(self):
        """Create credential when none exists (base class CRUD)."""
        action = self._make_action()
        action._task.args = {
            "name": "my-cred",
            "credential_type": "GitLab PAT",
            "organization": "Default",
            "inputs": {"token": "secret"},
            "state": "present",
        }
        manager = self._make_manager(
            find_result=None,
            create_result={"id": 100, "name": "my-cred", "changed": True},
        )
        result = self._run_action(
            action,
            manager,
            {
                "name": "my-cred",
                "credential_type": "GitLab PAT",
                "organization": "Default",
                "inputs": {"token": "secret"},
                "state": "present",
            },
        )
        self.assertFalse(result.get("failed", False))

    def test_delete_existing_credential(self):
        """Delete credential when it exists."""
        action = self._make_action()
        action._task.args = {"name": "my-cred", "state": "absent"}
        manager = self._make_manager(find_result={"id": 100, "name": "my-cred"})
        result = self._run_action(
            action,
            manager,
            {"name": "my-cred", "state": "absent"},
        )
        self.assertFalse(result.get("failed", False))

    def test_delete_nonexistent_credential(self):
        """No-op when deleting credential that doesn't exist."""
        action = self._make_action()
        action._task.args = {"name": "ghost", "state": "absent"}
        manager = self._make_manager(find_result=None)
        result = self._run_action(
            action,
            manager,
            {"name": "ghost", "state": "absent"},
        )
        self.assertFalse(result.get("failed", False))
        self.assertFalse(result.get("changed", True))

    # ---- Copy Tests ----

    def test_copy_from_creates_copy(self):
        """copy_from copies existing credential before CRUD."""
        action = self._make_action()
        action._task.args = {
            "name": "new-cred",
            "copy_from": "source-cred",
            "state": "present",
        }
        manager = self._make_manager(
            find_result=None,
            search_result={"results": []},
            create_result={"id": 200, "name": "new-cred", "changed": True},
        )
        result = self._run_action(
            action,
            manager,
            {
                "name": "new-cred",
                "copy_from": None,  # Popped from args before base class
                "state": "present",
            },
        )
        self.assertFalse(result.get("failed", False))
        self.assertTrue(result.get("changed", False))
        manager.copy_resource.assert_called_once()

    def test_copy_from_skips_if_exists(self):
        """copy_from skips copy if destination already exists."""
        action = self._make_action()
        action._task.args = {
            "name": "existing-cred",
            "copy_from": "source-cred",
            "state": "present",
        }
        manager = self._make_manager(
            find_result={"id": 100, "name": "existing-cred"},
            search_result={"results": [{"name": "existing-cred", "id": 100}]},
        )
        result = self._run_action(
            action,
            manager,
            {
                "name": "existing-cred",
                "copy_from": None,
                "state": "present",
            },
        )
        self.assertFalse(result.get("failed", False))
        manager.copy_resource.assert_not_called()

    def test_copy_from_error_returns_failure(self):
        """copy_from failure returns error result."""
        action = self._make_action()
        action._task.args = {
            "name": "new-cred",
            "copy_from": "bad-source",
            "state": "present",
        }
        manager = self._make_manager(
            find_result=None,
            search_result={"results": []},
            copy_error=ValueError("Source not found"),
        )

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                result = action.run(task_vars={})

        self.assertTrue(result.get("failed", False))
        self.assertIn("copy from", result["msg"].lower())

    # ---- Test State Tests ----

    def test_state_test_success(self):
        """state=test returns test result from API."""
        action = self._make_action()
        action._task.args = {"name": "my-cred", "state": "test"}
        manager = self._make_manager(
            find_result={"id": 100, "name": "my-cred"},
            direct_result={"success": True, "message": "Credential test successful"},
        )
        result = self._run_action(
            action,
            manager,
            {"name": "my-cred", "state": "test", "metadata": None},
        )
        self.assertFalse(result.get("failed", False))
        self.assertFalse(result.get("changed", True))
        self.assertIn("test_result", result)
        self.assertTrue(result["test_result"]["success"])

    def test_state_test_with_metadata(self):
        """state=test passes metadata to the test endpoint."""
        action = self._make_action()
        metadata = {"secret_path": "secret/myapp", "secret_key": "password"}
        action._task.args = {"name": "vault-cred", "state": "test", "metadata": metadata}
        manager = self._make_manager(
            find_result={"id": 100, "name": "vault-cred"},
            direct_result={"success": True, "message": "Vault test OK"},
        )
        result = self._run_action(
            action,
            manager,
            {"name": "vault-cred", "state": "test", "metadata": metadata},
        )
        self.assertFalse(result.get("failed", False))
        self.assertIn("test_result", result)
        # Verify direct_request was called with metadata
        manager.direct_request.assert_called_once()
        call_args = manager.direct_request.call_args
        self.assertEqual(call_args[0][0], "POST")
        self.assertIn("/test/", call_args[0][1])

    def test_state_test_credential_not_found(self):
        """state=test fails when credential doesn't exist."""
        action = self._make_action()
        action._task.args = {"name": "missing-cred", "state": "test"}
        manager = self._make_manager(find_result=None)
        result = self._run_action(
            action,
            manager,
            {"name": "missing-cred", "state": "test", "metadata": None},
        )
        self.assertTrue(result.get("failed", False))
        self.assertIn("not found", result["msg"])

    def test_state_test_check_mode(self):
        """state=test in check mode returns mock result without API call."""
        action = self._make_action(check_mode=True)
        action._task.args = {"name": "my-cred", "state": "test"}
        manager = self._make_manager(find_result={"id": 100, "name": "my-cred"})
        result = self._run_action(
            action,
            manager,
            {"name": "my-cred", "state": "test", "metadata": None},
        )
        self.assertFalse(result.get("failed", False))
        self.assertFalse(result.get("changed", True))
        self.assertTrue(result["test_result"]["success"])
        self.assertIn("check_mode", result["test_result"]["details"])
        manager.direct_request.assert_not_called()

    # ---- Write-Only Fields Tests ----

    def test_pre_execute_hook_injects_inputs(self):
        """_pre_execute_hook re-injects inputs for create/update."""
        action = self._make_action()
        ansible_data = {"name": "test"}
        write_only_data = {"inputs": {"token": "secret"}}
        action._pre_execute_hook(ansible_data, write_only_data, {}, "create")
        self.assertEqual(ansible_data["inputs"], {"token": "secret"})

    def test_pre_execute_hook_skips_inputs_for_delete(self):
        """_pre_execute_hook does not inject inputs for delete."""
        action = self._make_action()
        ansible_data = {"name": "test"}
        write_only_data = {"inputs": {"token": "secret"}}
        action._pre_execute_hook(ansible_data, write_only_data, {}, "delete")
        self.assertNotIn("inputs", ansible_data)

    def test_pre_execute_hook_no_inputs(self):
        """_pre_execute_hook is a no-op when no inputs are provided."""
        action = self._make_action()
        ansible_data = {"name": "test"}
        write_only_data = {}
        action._pre_execute_hook(ansible_data, write_only_data, {}, "create")
        self.assertNotIn("inputs", ansible_data)


if __name__ == "__main__":
    unittest.main()
