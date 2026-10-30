# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the eda_controller_token action plugin."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.eda_controller_token import ActionModule


class TestEdaControllerTokenAction(unittest.TestCase):
    """Test eda_controller_token action plugin delete-and-recreate behavior."""

    def _make_action(self, check_mode=False):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.check_mode = check_mode
        action._task.args = {}
        action._display = MagicMock()
        action._display.verbosity = 0
        return action

    def _make_manager(self, find_result=None, create_result=None, delete_error=None):
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
                return create_result or {"id": 6000, "name": ansible_data.get("name", "")}
            return {}

        manager.execute.side_effect = execute_side_effect
        return manager

    def _run_action(self, action, manager, validated_params):
        doc = "module: eda_controller_token"
        argspec = {"argument_spec": {"name": {}, "description": {}, "token": {}, "state": {}}}
        validation = SimpleNamespace(validated_parameters=validated_params)

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_documentation", return_value=doc):
                with patch.object(action, "_build_argspec_from_docs", return_value=argspec):
                    with patch.object(action, "_validate_data", return_value=validation):
                        with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                            return action.run(task_vars={})

    def test_create_new_token(self):
        """Create token when none exists."""
        action = self._make_action()
        manager = self._make_manager(
            find_result=None,
            create_result={"id": 6000, "name": "my-token", "description": "test"},
        )
        result = self._run_action(
            action,
            manager,
            {
                "name": "my-token",
                "description": "test",
                "token": "secret-value",
                "state": "present",
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        self.assertEqual(result["id"], 6000)
        # Should only call find + create, no delete
        calls = [c.kwargs["operation"] for c in manager.execute.call_args_list]
        self.assertEqual(calls, ["find", "create"])

    def test_recreate_existing_token(self):
        """Delete and recreate when token already exists (Shape 6)."""
        action = self._make_action()
        manager = self._make_manager(
            find_result={"id": 5999, "name": "my-token"},
            create_result={"id": 6000, "name": "my-token"},
        )
        result = self._run_action(
            action,
            manager,
            {
                "name": "my-token",
                "description": "updated",
                "token": "new-secret",
                "state": "present",
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        # Should call find, delete, then create
        calls = [c.kwargs["operation"] for c in manager.execute.call_args_list]
        self.assertEqual(calls, ["find", "delete", "create"])
        # Delete should use the existing id
        delete_call = manager.execute.call_args_list[1]
        self.assertEqual(delete_call.kwargs["ansible_data"]["id"], 5999)

    def test_delete_existing_token(self):
        """Delete token when it exists."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 5999, "name": "my-token"})
        result = self._run_action(
            action,
            manager,
            {
                "name": "my-token",
                "state": "absent",
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        calls = [c.kwargs["operation"] for c in manager.execute.call_args_list]
        self.assertEqual(calls, ["find", "delete"])

    def test_delete_nonexistent_token(self):
        """No-op when deleting token that doesn't exist."""
        action = self._make_action()
        manager = self._make_manager(find_result=None)
        result = self._run_action(
            action,
            manager,
            {
                "name": "ghost-token",
                "state": "absent",
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])
        self.assertIn("already absent", result["msg"])

    def test_check_mode_present(self):
        """Check mode reports changed without calling API."""
        action = self._make_action(check_mode=True)
        manager = self._make_manager()
        result = self._run_action(
            action,
            manager,
            {
                "name": "my-token",
                "token": "secret",
                "state": "present",
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        # In check mode, only find is called (no create/delete)
        calls = [c.kwargs["operation"] for c in manager.execute.call_args_list]
        self.assertNotIn("create", calls)
        self.assertNotIn("delete", calls)

    def test_check_mode_absent_existing(self):
        """Check mode for absent with existing token."""
        action = self._make_action(check_mode=True)
        manager = self._make_manager(find_result={"id": 5999, "name": "my-token"})
        result = self._run_action(
            action,
            manager,
            {
                "name": "my-token",
                "state": "absent",
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        calls = [c.kwargs["operation"] for c in manager.execute.call_args_list]
        self.assertNotIn("delete", calls)

    def test_present_without_token_fails(self):
        """State=present without token raises AnsibleError."""
        action = self._make_action()
        manager = self._make_manager(find_result=None)
        result = self._run_action(
            action,
            manager,
            {
                "name": "my-token",
                "description": "missing token value",
                "token": None,
                "state": "present",
            },
        )

        self.assertTrue(result["failed"])
        self.assertIn("token", result["msg"].lower())

    def test_find_reraises_non_not_found_errors(self):
        """ValueError not related to 'not found' is re-raised."""
        action = self._make_action()
        manager = MagicMock()
        manager.execute.side_effect = ValueError("Authentication failed")
        result = self._run_action(
            action,
            manager,
            {
                "name": "my-token",
                "token": "secret",
                "state": "present",
            },
        )

        self.assertTrue(result["failed"])
        self.assertIn("Authentication failed", result["msg"])


if __name__ == "__main__":
    unittest.main()
