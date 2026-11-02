# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the eda_credential action plugin."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

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

    def _make_manager(self, find_result=None, create_result=None, delete_error=None, copy_error=None, direct_result=None, lookup_result_by_name=None):
        manager = MagicMock()
        current_result = [find_result]
        copied_ids = {}
        lookup_result_by_name = lookup_result_by_name or {}

        def execute_side_effect(operation, module_name, ansible_data):
            if operation == "find":
                if current_result[0]:
                    return current_result[0]
                raise ValueError("Not found")
            if operation == "delete":
                if delete_error:
                    raise delete_error
                return {}
            if operation == "create":
                return create_result or {"id": 100, "name": ansible_data.get("name", ""), "changed": True}
            if operation == "update":
                return create_result or {"id": (current_result[0] or {}).get("id", 100), "name": ansible_data.get("name", ""), "changed": True}
            return {}

        def lookup_side_effect(endpoint, lookup_field, lookup_value, service="gateway", extra_query_params=None, require_unique=False):
            if endpoint == "organizations":
                ids = {"Default": 1, "Engineering": 2, "1": 1, "2": 2}
                if str(lookup_value) in ids:
                    return ids[str(lookup_value)]
            elif endpoint == "credential-types":
                ids = {"GitLab PAT": 11, "Source Control": 12, "11": 11, "12": 12}
                if str(lookup_value) in ids:
                    return ids[str(lookup_value)]
            elif endpoint == "eda-credentials":
                if str(lookup_value) in copied_ids:
                    return copied_ids[str(lookup_value)]
                if current_result[0] and current_result[0].get("name") == lookup_value:
                    return current_result[0]["id"]
                if str(lookup_value) in lookup_result_by_name:
                    return lookup_result_by_name[str(lookup_value)]
                raise ValueError("Resource 'eda-credentials' with name=%s not found" % lookup_value)
            raise ValueError("Resource '%s' with name=%s not found" % (endpoint, lookup_value))

        def copy_side_effect(module_name, source_id, name, endpoint, service="eda"):
            if copy_error:
                raise copy_error
            copied_ids[name] = 200
            current_result[0] = {"id": 200, "name": name, "credential_type": "12", "organization": "1"}
            return {"id": 200, "name": name}

        manager.execute.side_effect = execute_side_effect
        manager.lookup_resource_id.side_effect = lookup_side_effect
        manager.copy_resource.side_effect = copy_side_effect
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
            create_result={"id": 200, "name": "new-cred", "changed": True},
            lookup_result_by_name={"source-cred": 99},
        )
        result = self._run_action(
            action,
            manager,
            {
                "name": "new-cred",
                "copy_from": "source-cred",
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
        )
        result = self._run_action(
            action,
            manager,
            {
                "name": "existing-cred",
                "copy_from": "source-cred",
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
            copy_error=ValueError("Source not found"),
            lookup_result_by_name={"bad-source": 99},
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
        manager.direct_request.assert_called_once_with("POST", "/api/eda/v1/eda-credentials/100/test/", data={"metadata": metadata})

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

    def test_update_secrets_forces_inputs_only_patch(self):
        """Explicit secret updates send an inputs-only PATCH."""
        action = self._make_action()
        action._task.args = {
            "name": "my-cred",
            "inputs": {"token": "rotated"},
            "update_secrets": True,
            "state": "present",
        }
        manager = self._make_manager(find_result={"id": 100, "name": "my-cred"})

        result = self._run_action(
            action,
            manager,
            {"name": "my-cred", "inputs": {"token": "rotated"}, "update_secrets": True, "state": "present"},
        )

        self.assertFalse(result.get("failed", False))
        update_call = next(item for item in manager.execute.call_args_list if item.kwargs.get("operation") == "update")
        self.assertEqual(update_call.kwargs["ansible_data"]["inputs"], {"token": "rotated"})

    def test_copy_with_inputs_forces_update_after_copy(self):
        """Inputs explicitly supplied with copy_from override copied values."""
        action = self._make_action()
        action._task.args = {
            "name": "new-cred",
            "copy_from": "source-cred",
            "inputs": {"token": "override"},
            "state": "present",
        }
        manager = self._make_manager(find_result=None, lookup_result_by_name={"source-cred": 99})

        result = self._run_action(
            action,
            manager,
            {"name": "new-cred", "copy_from": "source-cred", "inputs": {"token": "override"}, "state": "present"},
        )

        self.assertFalse(result.get("failed", False))
        manager.copy_resource.assert_called_once_with("eda_credential", 99, "new-cred", "/api/eda/v1/eda-credentials", service="eda")
        update_call = next(item for item in manager.execute.call_args_list if item.kwargs.get("operation") == "update")
        self.assertEqual(update_call.kwargs["ansible_data"]["inputs"], {"token": "override"})

    def test_named_foreign_keys_are_normalized_before_comparison(self):
        """Same FK IDs supplied by name are idempotent; changed IDs trigger update."""
        action = self._make_action()
        action._client = self._make_manager()

        self.assertFalse(
            action._should_update(
                {"credential_type": "GitLab PAT", "organization": "Default"},
                {"credential_type": "11", "organization": "1"},
            )
        )
        self.assertTrue(
            action._should_update(
                {"credential_type": "Source Control", "organization": "Default"},
                {"credential_type": "11", "organization": "1"},
            )
        )

    def test_name_lookup_is_scoped_and_requires_unique_match(self):
        """An organization filter is passed into a unique credential lookup."""
        action = self._make_action()
        manager = self._make_manager(lookup_result_by_name={"same-name": 99})

        self.assertEqual(action._lookup_credential_id(manager, "same-name", "Default"), 99)
        manager.lookup_resource_id.assert_has_calls(
            [
                call("organizations", "name", "Default", service="eda", require_unique=True),
                call(
                    "eda-credentials",
                    "name",
                    "same-name",
                    service="eda",
                    extra_query_params={"organization_id": 1},
                    require_unique=True,
                ),
            ]
        )

    def test_ambiguous_name_lookup_is_not_treated_as_missing(self):
        """Ambiguous names fail instead of falling through to a create."""
        action = self._make_action()
        action._task.args = {"name": "same-name", "state": "present"}
        manager = self._make_manager()
        manager.lookup_resource_id.side_effect = ValueError("Resource 'eda-credentials' matched multiple resources")

        result = self._run_action(action, manager, {"name": "same-name", "state": "present"})

        self.assertTrue(result["failed"])
        self.assertIn("multiple resources", result["msg"])
        manager.execute.assert_not_called()

    def test_inputs_only_change_is_idempotent_without_update_secrets(self):
        """Write-only inputs remain a no-op unless the force option is enabled."""
        action = self._make_action()
        action._inputs_provided = True
        action._update_secrets = False
        action._copied_credential = False

        self.assertFalse(action._should_update({"name": "my-cred"}, {"name": "my-cred"}))

    def test_real_documentation_validation_applies_defaults_and_no_log(self):
        """The real docs path validates argument defaults and secret redaction."""
        action = self._make_action()
        action._task.args = {"name": "my-cred", "state": "test"}
        manager = self._make_manager(find_result={"id": 100, "name": "my-cred"})

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                prepared = action._prepare_action(task_vars={})

        self.assertIs(prepared["validated_params"]["update_secrets"], False)
        self.assertTrue(prepared["argspec"]["argument_spec"]["inputs"]["no_log"])

    def test_state_test_rejects_invalid_metadata_before_lookup(self):
        """state=test uses the documented metadata type validation."""
        action = self._make_action()
        action._task.args = {"name": "my-cred", "state": "test", "metadata": "not-a-dict"}
        manager = self._make_manager(find_result={"id": 100, "name": "my-cred"})

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)) as get_manager:
                result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        get_manager.assert_not_called()


if __name__ == "__main__":
    unittest.main()
