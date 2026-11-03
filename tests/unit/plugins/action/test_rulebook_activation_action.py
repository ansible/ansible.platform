# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the rulebook_activation action plugin."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.rulebook_activation import ActionModule


class TestRulebookActivationAction(unittest.TestCase):
    """Test rulebook_activation action plugin state machine."""

    def _make_action(self, check_mode=False):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.check_mode = check_mode
        action._task.args = {}
        action._display = MagicMock()
        action._display.verbosity = 0
        return action

    def _make_manager(self, find_result=None, update_changed=True, create_result=None):
        manager = MagicMock()

        def execute_side_effect(operation, module_name, ansible_data):
            if operation == "find":
                if find_result:
                    return find_result
                raise ValueError("Not found")
            if operation == "create":
                result = dict(create_result or {"id": 100, "name": ansible_data.get("name")})
                result["changed"] = True
                return result
            if operation == "update":
                result = dict(find_result or {})
                result["changed"] = update_changed
                return result
            if operation == "delete":
                return {"changed": True, "id": ansible_data.get("id")}
            return {}

        manager.execute.side_effect = execute_side_effect
        manager.direct_request.return_value = find_result or {"id": 100}
        manager.search_api.return_value = {"results": []}
        manager.lookup_resource_id.return_value = 1
        return manager

    def _run_action(self, action, manager, validated_params, provided_args=None):
        doc = "module: rulebook_activation"
        argspec = {
            "argument_spec": {
                "name": {},
                "new_name": {},
                "description": {},
                "project_name": {},
                "rulebook_name": {},
                "extra_vars": {},
                "restart": {"type": "bool", "default": False},
                "restart_policy": {"default": "on-failure"},
                "decision_environment_name": {},
                "awx_token_name": {},
                "organization_name": {},
                "eda_credentials": {},
                "k8s_service_name": {},
                "event_streams": {},
                "log_level": {"default": "error"},
                "enable_persistence": {"type": "bool", "default": False},
                "rule_engine_credential_id": {},
                "restart_on_project_update": {"type": "bool", "default": False},
                "state": {"default": "present"},
            }
        }
        validation = SimpleNamespace(validated_parameters=validated_params)
        action._task.args = provided_args or {}

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_documentation", return_value=doc):
                with patch.object(action, "_build_argspec_from_docs", return_value=argspec):
                    with patch.object(action, "_validate_data", return_value=validation):
                        with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                            return action.run(task_vars={})

    def test_delete_existing_activation(self):
        """Delete activation when it exists."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 42, "name": "test-activation", "is_enabled": True})
        result = self._run_action(action, manager, {"name": "test-activation", "state": "absent", "restart": False})

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        # Delete goes through the generic execute() dispatch, not direct_request
        manager.execute.assert_any_call(
            operation="delete",
            module_name="rulebook_activation",
            ansible_data={"id": 42, "name": "test-activation"},
        )
        manager.direct_request.assert_not_called()

    def test_delete_nonexistent_activation(self):
        """No-op when deleting activation that doesn't exist."""
        action = self._make_action()
        manager = self._make_manager(find_result=None)
        result = self._run_action(action, manager, {"name": "ghost-activation", "state": "absent", "restart": False})

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])
        self.assertIn("already absent", result["msg"])

    def test_restart_existing_activation(self):
        """Restart activation when it exists."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 42, "name": "test-activation", "is_enabled": True})
        result = self._run_action(action, manager, {"name": "test-activation", "state": "present", "restart": True})

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        self.assertEqual(result["id"], 42)
        # Should call direct_request with POST to restart endpoint
        manager.direct_request.assert_called_once()
        call_args = manager.direct_request.call_args
        self.assertEqual(call_args[0][0], "POST")
        self.assertIn("restart", call_args[0][1])

    def test_restart_nonexistent_activation_fails(self):
        """Cannot restart activation that doesn't exist."""
        action = self._make_action()
        manager = self._make_manager(find_result=None)
        result = self._run_action(action, manager, {"name": "ghost-activation", "state": "present", "restart": True})

        self.assertTrue(result.get("failed", False))
        self.assertIn("does not exist", result["msg"])

    def test_enable_disabled_activation(self):
        """Enable a disabled activation."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 42, "name": "test-activation", "is_enabled": False})
        result = self._run_action(action, manager, {"name": "test-activation", "state": "enabled", "restart": False})

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        # Should call direct_request with POST to enable endpoint
        manager.direct_request.assert_called_once()
        call_args = manager.direct_request.call_args
        self.assertEqual(call_args[0][0], "POST")
        self.assertIn("enable", call_args[0][1])

    def test_enable_already_enabled_activation(self):
        """No-op when enabling an already enabled activation."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 42, "name": "test-activation", "is_enabled": True})
        result = self._run_action(action, manager, {"name": "test-activation", "state": "enabled", "restart": False})

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])
        manager.direct_request.assert_not_called()

    def test_disable_enabled_activation(self):
        """Disable an enabled activation."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 42, "name": "test-activation", "is_enabled": True})
        result = self._run_action(action, manager, {"name": "test-activation", "state": "disabled", "restart": False})

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        # Should call direct_request with POST to disable endpoint
        manager.direct_request.assert_called_once()
        call_args = manager.direct_request.call_args
        self.assertEqual(call_args[0][0], "POST")
        self.assertIn("disable", call_args[0][1])

    def test_disable_already_disabled_activation(self):
        """No-op when disabling an already disabled activation."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 42, "name": "test-activation", "is_enabled": False})
        result = self._run_action(action, manager, {"name": "test-activation", "state": "disabled", "restart": False})

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])
        manager.direct_request.assert_not_called()

    def test_check_mode_absent_existing(self):
        """Check mode for absent with existing activation."""
        action = self._make_action(check_mode=True)
        manager = self._make_manager(find_result={"id": 42, "name": "test-activation", "is_enabled": True})
        result = self._run_action(action, manager, {"name": "test-activation", "state": "absent", "restart": False})

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        manager.direct_request.assert_not_called()

    def test_check_mode_restart(self):
        """Check mode for restart."""
        action = self._make_action(check_mode=True)
        manager = self._make_manager(find_result={"id": 42, "name": "test-activation", "is_enabled": True})
        result = self._run_action(action, manager, {"name": "test-activation", "state": "present", "restart": True})

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        manager.direct_request.assert_not_called()

    def test_check_mode_enable(self):
        """Check mode for enabling a disabled activation."""
        action = self._make_action(check_mode=True)
        manager = self._make_manager(find_result={"id": 42, "name": "test-activation", "is_enabled": False})
        result = self._run_action(action, manager, {"name": "test-activation", "state": "enabled", "restart": False})

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        manager.direct_request.assert_not_called()

    def test_create_new_activation(self):
        """Create a new activation when none exists."""
        action = self._make_action()
        manager = self._make_manager(find_result=None, create_result={"id": 100, "name": "new-activation"})
        result = self._run_action(
            action,
            manager,
            {
                "name": "new-activation",
                "state": "present",
                "restart": False,
                "project_name": "my-project",
                "rulebook_name": "my-rulebook.yml",
                "decision_environment_name": "my-de",
                "organization_name": "Default",
                "restart_policy": "on-failure",
                "log_level": "error",
                "enable_persistence": False,
                "restart_on_project_update": False,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        self.assertEqual(result["id"], 100)
        # Create goes through execute(), not direct_request.
        create_call = next(c for c in manager.execute.call_args_list if c.kwargs.get("operation") == "create")
        self.assertEqual(create_call.kwargs["ansible_data"]["is_enabled"], True)
        for field, value in {
            "restart_policy": "on-failure",
            "log_level": "error",
            "enable_persistence": False,
            "restart_on_project_update": False,
        }.items():
            self.assertEqual(create_call.kwargs["ansible_data"][field], value)
        self.assertNotIn("id", create_call.kwargs["ansible_data"])
        manager.direct_request.assert_not_called()

    def test_update_existing_activation_no_changes_is_idempotent(self):
        """An unchanged activation is not PATCHed or reported as changed."""
        action = self._make_action()
        manager = self._make_manager(
            find_result={"id": 42, "name": "test-activation", "is_enabled": True},
            update_changed=False,
        )
        result = self._run_action(action, manager, {"name": "test-activation", "state": "present", "restart": False})

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])
        self.assertFalse(any(c.kwargs.get("operation") == "update" for c in manager.execute.call_args_list))
        manager.direct_request.assert_not_called()

    def test_check_mode_existing_activation_no_changes(self):
        """Check mode reports no change for an unchanged activation."""
        action = self._make_action(check_mode=True)
        manager = self._make_manager(find_result={"id": 42, "name": "test-activation", "is_enabled": True})

        result = self._run_action(action, manager, {"name": "test-activation", "state": "present", "restart": False})

        self.assertFalse(result["failed"])
        self.assertFalse(result["changed"])
        self.assertFalse(any(c.kwargs.get("operation") == "update" for c in manager.execute.call_args_list))

    def test_check_mode_existing_activation_with_changes(self):
        """Check mode reports a change without submitting an update."""
        action = self._make_action(check_mode=True)
        manager = self._make_manager(find_result={"id": 42, "name": "test-activation", "is_enabled": True})

        result = self._run_action(
            action,
            manager,
            {"name": "test-activation", "state": "present", "restart": False, "description": "updated"},
        )

        self.assertFalse(result["failed"])
        self.assertTrue(result["changed"])
        self.assertFalse(any(c.kwargs.get("operation") == "update" for c in manager.execute.call_args_list))

    def test_update_existing_activation_with_changes(self):
        """state=present with an actual field change must report changed."""
        action = self._make_action()
        manager = self._make_manager(
            find_result={"id": 42, "name": "test-activation", "is_enabled": True},
            update_changed=True,
        )
        result = self._run_action(
            action,
            manager,
            {"name": "test-activation", "state": "present", "restart": False, "description": "updated"},
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        manager.direct_request.assert_not_called()

    def test_update_omits_defaulted_fields_not_explicitly_supplied(self):
        """Validation defaults do not overwrite fields omitted from an update."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 42, "name": "test-activation", "is_enabled": True})
        result = self._run_action(
            action,
            manager,
            {
                "name": "test-activation",
                "state": "present",
                "restart": False,
                "restart_policy": "on-failure",
                "log_level": "error",
                "enable_persistence": False,
                "restart_on_project_update": False,
            },
        )

        self.assertFalse(result["failed"])
        self.assertFalse(result["changed"])
        self.assertFalse(any(c.kwargs.get("operation") == "update" for c in manager.execute.call_args_list))

    def test_update_includes_defaulted_fields_explicitly_supplied(self):
        """Explicit values, including values equal to defaults, should be PATCHed."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 42, "name": "test-activation", "is_enabled": True})
        explicit_values = {
            "restart_policy": "on-failure",
            "log_level": "error",
            "enable_persistence": False,
            "restart_on_project_update": False,
        }
        params = {"name": "test-activation", "state": "present", "restart": False, **explicit_values}

        result = self._run_action(action, manager, params, provided_args=explicit_values)

        self.assertFalse(result["failed"])
        update_call = next(c for c in manager.execute.call_args_list if c.kwargs.get("operation") == "update")
        for field, value in explicit_values.items():
            self.assertEqual(update_call.kwargs["ansible_data"][field], value)

    def test_update_preserves_awx_token_and_event_stream_changes(self):
        """Pass supported token and event-stream changes through to the transform."""
        action = self._make_action()
        event_streams = [{"event_stream": "stream", "source_name": "source"}]
        manager = self._make_manager(
            find_result={"id": 42, "name": "test-activation", "is_enabled": True, "rulebook_id": 7},
            update_changed=True,
        )
        manager.search_api.return_value = {"results": [{"name": "source", "rulebook_hash": "hash"}]}

        self._run_action(
            action,
            manager,
            {
                "name": "test-activation",
                "state": "present",
                "restart": False,
                "awx_token_name": "controller-token",
                "event_streams": event_streams,
            },
        )

        update_call = next(c for c in manager.execute.call_args_list if c.kwargs.get("operation") == "update")
        ansible_data = update_call.kwargs["ansible_data"]
        self.assertEqual(ansible_data["awx_token_name"], "controller-token")
        self.assertEqual(ansible_data["event_streams"], event_streams)
        self.assertEqual(ansible_data["rulebook_id"], 7)

    def test_update_event_streams_fails_if_existing_rulebook_is_unavailable(self):
        """Do not silently skip an event-stream update without its rulebook context."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 42, "name": "test-activation", "is_enabled": True})

        result = self._run_action(
            action,
            manager,
            {
                "name": "test-activation",
                "state": "present",
                "restart": False,
                "event_streams": [{"event_stream": "stream", "source_name": "source"}],
            },
        )

        self.assertTrue(result["failed"])
        self.assertIn("existing activation has no rulebook ID", result["msg"])
        self.assertFalse(any(call.kwargs.get("operation") == "update" for call in manager.execute.call_args_list))

    def test_check_mode_create(self):
        """Check mode for creating a new activation."""
        action = self._make_action(check_mode=True)
        manager = self._make_manager(find_result=None)
        result = self._run_action(
            action,
            manager,
            {
                "name": "new-activation",
                "state": "present",
                "restart": False,
                "project_name": "my-project",
                "rulebook_name": "my-rulebook.yml",
                "decision_environment_name": "my-de",
                "organization_name": "Default",
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        manager.direct_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
