# (c) 2025 Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the workflow_approval action plugin."""

import unittest
from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.workflow_approval import ActionModule


class TestWorkflowApprovalAction(unittest.TestCase):
    def _make_action(self, args, check_mode=False):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.args = dict(args)
        action._task.check_mode = check_mode
        action._task.environment = []
        action._task_vars = {}
        action._display = MagicMock()
        action._display.verbosity = 0
        action._connection = MagicMock()
        action._templar = MagicMock()
        return action

    def test_approve_success(self):
        action = self._make_action(
            {
                "workflow_job_id": 42,
                "name": "approval_node_1",
                "action": "approve",
                "timeout": 10,
                "interval": 1,
            }
        )
        manager = MagicMock()
        manager.approve_workflow_node.return_value = {
            "changed": True,
            "workflow_job_id": 42,
            "node_name": "approval_node_1",
            "action": "approve",
            "approval_node_id": 99,
        }

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_documentation", return_value="module: workflow_approval"):
                with patch.object(action, "_build_argspec_from_docs") as mock_argspec:
                    mock_argspec.return_value = {
                        "argument_spec": {
                            "workflow_job_id": {"type": "int", "required": True},
                            "name": {"type": "str", "required": True},
                            "action": {"type": "str", "choices": ["approve", "deny"], "default": "approve"},
                            "timeout": {"type": "int", "default": 10},
                            "interval": {"type": "float", "default": 1},
                        },
                    }
                    with patch.object(action, "_validate_data") as mock_validate:
                        from types import SimpleNamespace

                        mock_validate.return_value = SimpleNamespace(
                            validated_parameters=dict(action._task.args),
                            error_messages=[],
                        )
                        with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                            result = action.run(task_vars={})

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        self.assertEqual(result["workflow_job_id"], 42)
        self.assertEqual(result["action"], "approve")
        manager.approve_workflow_node.assert_called_once_with(
            workflow_job_id=42,
            node_name="approval_node_1",
            action="approve",
            timeout=10,
            interval=1,
        )

    def test_deny_success(self):
        action = self._make_action(
            {
                "workflow_job_id": 42,
                "name": "approval_node_1",
                "action": "deny",
                "timeout": 10,
                "interval": 1,
            }
        )
        manager = MagicMock()
        manager.approve_workflow_node.return_value = {
            "changed": True,
            "workflow_job_id": 42,
            "node_name": "approval_node_1",
            "action": "deny",
            "approval_node_id": 99,
        }

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_documentation", return_value="module: workflow_approval"):
                with patch.object(action, "_build_argspec_from_docs") as mock_argspec:
                    mock_argspec.return_value = {
                        "argument_spec": {
                            "workflow_job_id": {"type": "int", "required": True},
                            "name": {"type": "str", "required": True},
                            "action": {"type": "str", "choices": ["approve", "deny"], "default": "approve"},
                            "timeout": {"type": "int", "default": 10},
                            "interval": {"type": "float", "default": 1},
                        },
                    }
                    with patch.object(action, "_validate_data") as mock_validate:
                        from types import SimpleNamespace

                        mock_validate.return_value = SimpleNamespace(
                            validated_parameters=dict(action._task.args),
                            error_messages=[],
                        )
                        with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                            result = action.run(task_vars={})

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        self.assertEqual(result["action"], "deny")

    def test_check_mode_no_api_call(self):
        action = self._make_action(
            {
                "workflow_job_id": 42,
                "name": "approval_node_1",
                "action": "approve",
                "timeout": 10,
                "interval": 1,
            },
            check_mode=True,
        )

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_documentation", return_value="module: workflow_approval"):
                with patch.object(action, "_build_argspec_from_docs") as mock_argspec:
                    mock_argspec.return_value = {
                        "argument_spec": {
                            "workflow_job_id": {"type": "int", "required": True},
                            "name": {"type": "str", "required": True},
                            "action": {"type": "str", "choices": ["approve", "deny"], "default": "approve"},
                            "timeout": {"type": "int", "default": 10},
                            "interval": {"type": "float", "default": 1},
                        },
                    }
                    with patch.object(action, "_validate_data") as mock_validate:
                        from types import SimpleNamespace

                        mock_validate.return_value = SimpleNamespace(
                            validated_parameters=dict(action._task.args),
                            error_messages=[],
                        )
                        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertFalse(result.get("failed", False))
        self.assertIn("Would approve", result["msg"])

    def test_timeout_reports_failure(self):
        action = self._make_action(
            {
                "workflow_job_id": 42,
                "name": "missing_node",
                "action": "approve",
                "timeout": 10,
                "interval": 1,
            }
        )
        manager = MagicMock()
        manager.approve_workflow_node.side_effect = ValueError("Timed out waiting for workflow approval node 'missing_node' in workflow job 42 (timeout=10s)")

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_documentation", return_value="module: workflow_approval"):
                with patch.object(action, "_build_argspec_from_docs") as mock_argspec:
                    mock_argspec.return_value = {
                        "argument_spec": {
                            "workflow_job_id": {"type": "int", "required": True},
                            "name": {"type": "str", "required": True},
                            "action": {"type": "str", "choices": ["approve", "deny"], "default": "approve"},
                            "timeout": {"type": "int", "default": 10},
                            "interval": {"type": "float", "default": 1},
                        },
                    }
                    with patch.object(action, "_validate_data") as mock_validate:
                        from types import SimpleNamespace

                        mock_validate.return_value = SimpleNamespace(
                            validated_parameters=dict(action._task.args),
                            error_messages=[],
                        )
                        with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                            result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertFalse(result["changed"])
        self.assertIn("Timed out", result["msg"])


if __name__ == "__main__":
    unittest.main()
