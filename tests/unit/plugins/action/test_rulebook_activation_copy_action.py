# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the rulebook_activation_copy action plugin."""

import unittest
from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.rulebook_activation_copy import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError


class TestRulebookActivationCopyAction(unittest.TestCase):
    """Test rulebook_activation_copy action plugin."""

    def _make_action(self, check_mode=False):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.check_mode = check_mode
        action._task.args = {}
        action._display = MagicMock()
        action._display.verbosity = 0
        return action

    def _make_manager(self, find_result=None, copy_result=None):
        manager = MagicMock()

        def execute_side_effect(operation, module_name, ansible_data):
            if operation == "find":
                if find_result:
                    return find_result
                raise ValueError("Not found")
            return {}

        manager.execute.side_effect = execute_side_effect
        manager.direct_request.return_value = copy_result or {"id": 200, "name": "copied-activation"}
        return manager

    def _run_action(self, action, manager, validated_params):
        action._task.args = validated_params.copy()

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                return action.run(task_vars={})

    def test_copy_existing_activation(self):
        """Copy an activation when the source exists."""
        action = self._make_action()
        manager = self._make_manager(
            find_result={"id": 42, "name": "source-activation"},
            copy_result={"id": 200, "name": "new-activation"},
        )
        result = self._run_action(
            action,
            manager,
            {"name": "new-activation", "copy_from": "source-activation"},
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        self.assertEqual(result["id"], 200)
        manager.direct_request.assert_called_once()
        call_args = manager.direct_request.call_args
        self.assertEqual(
            {"method": call_args.args[0], "path": call_args.args[1], "body": call_args.kwargs["data"]},
            {
                "method": "POST",
                "path": "/api/eda/v1/activations/42/copy/",
                "body": {"name": "new-activation"},
            },
        )
        self.assertEqual(call_args.kwargs["retry_config"].max_attempts, 1)

    def test_copy_nonexistent_activation_fails(self):
        """Fail when source activation does not exist."""
        action = self._make_action()
        manager = self._make_manager(find_result=None)
        result = self._run_action(
            action,
            manager,
            {"name": "new-activation", "copy_from": "ghost-activation"},
        )

        self.assertTrue(result.get("failed", False))
        self.assertIn("not found", result["msg"].lower())

    def test_check_mode_copy(self):
        """Check mode reports changed without calling API."""
        action = self._make_action(check_mode=True)
        manager = self._make_manager(find_result={"id": 42, "name": "source-activation"})
        result = self._run_action(
            action,
            manager,
            {"name": "new-activation", "copy_from": "source-activation"},
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        manager.direct_request.assert_not_called()

    def test_copy_without_copy_from_fails(self):
        """Fail when copy_from is not provided."""
        action = self._make_action()
        manager = self._make_manager()
        result = self._run_action(
            action,
            manager,
            {"name": "new-activation", "copy_from": None},
        )

        self.assertTrue(result.get("failed", False))
        self.assertIn("copy_from", result["msg"])

    def test_copy_duplicate_name_preserves_api_error_message(self):
        """Return the API's duplicate-name message to callers."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 42, "name": "source-activation"})
        manager.direct_request.side_effect = APIError(
            "API request failed: HTTP 400",
            operation="http_request",
            resource="unknown",
            details={
                "status_code": 400,
                "response_body": '{"__all__": ["Activation with name new-activation already exists"]}',
            },
            status_code=400,
        )

        result = self._run_action(
            action,
            manager,
            {"name": "new-activation", "copy_from": "source-activation"},
        )

        self.assertTrue(result.get("failed", False))
        self.assertIn("API request failed: HTTP 400", result["msg"])
        self.assertIn("Operation: http_request", result["msg"])
        self.assertIn("Activation with name new-activation already exists", result["msg"])


if __name__ == "__main__":
    unittest.main()
