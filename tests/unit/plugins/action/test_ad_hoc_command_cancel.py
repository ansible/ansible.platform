# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the ad_hoc_command_cancel action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import unittest
from unittest.mock import MagicMock, create_autospec, patch

from ansible.playbook.task import Task
from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.ad_hoc_command_cancel import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient


def _make_module(args=None, check_mode=False):
    """Create an ActionModule instance with mocked dependencies."""
    task = MagicMock(spec=Task)
    task.args = args or {}
    task.check_mode = check_mode
    task.async_val = 0
    task.environment = []

    module = ActionModule(
        task=task,
        connection=MagicMock(),
        play_context=MagicMock(),
        loader=MagicMock(),
        templar=MagicMock(),
        shared_loader_obj=MagicMock(),
    )
    module._display = MagicMock()
    module._display.verbosity = 0
    return module


def _make_manager():
    """Create a manager mock constrained to the RPC client API and signatures."""
    return create_autospec(ManagerRPCClient, instance=True, spec_set=True)


class TestActionModuleAttributes(unittest.TestCase):
    """Test action metadata."""

    def test_module_name(self):
        module = _make_module()
        self.assertEqual(module.MODULE_NAME, "ad_hoc_command_cancel")


class TestCheckMode(unittest.TestCase):
    """Test check mode behavior."""

    @patch.object(ActionModule, "_prepare_action")
    def test_check_mode_skips_cancel(self, mock_prepare):
        module = _make_module(args={"command_id": 42}, check_mode=True)
        manager = _make_manager()
        manager.can_cancel_resource.return_value = True
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "fail_if_not_running": False, "interval": 1.0, "timeout": 0},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertEqual(result["id"], 42)
        self.assertIn("check mode", result["status"])
        manager.can_cancel_resource.assert_called_once_with(42, "ad_hoc_commands", service="controller")
        manager.cancel_resource.assert_not_called()

    @patch.object(ActionModule, "_prepare_action")
    def test_check_mode_reports_non_cancellable_command_without_change(self, mock_prepare):
        module = _make_module(args={"command_id": 42}, check_mode=True)
        manager = _make_manager()
        manager.can_cancel_resource.return_value = False
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "fail_if_not_running": False, "interval": 1.0, "timeout": 0},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertEqual(result, {"changed": False, "id": 42, "status": "already finished"})
        manager.cancel_resource.assert_not_called()

    @patch.object(ActionModule, "_prepare_action")
    def test_check_mode_fails_for_non_cancellable_command_when_requested(self, mock_prepare):
        module = _make_module(args={"command_id": 42}, check_mode=True)
        manager = _make_manager()
        manager.can_cancel_resource.return_value = False
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "fail_if_not_running": True, "interval": 1.0, "timeout": 0},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertEqual(result["msg"], "Ad Hoc Command is not running")
        manager.cancel_resource.assert_not_called()

    @patch.object(ActionModule, "_prepare_action")
    def test_check_mode_fails_when_command_does_not_exist(self, mock_prepare):
        module = _make_module(args={"command_id": 99999}, check_mode=True)
        manager = _make_manager()
        manager.can_cancel_resource.side_effect = ValueError("Resource not found")
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 99999, "fail_if_not_running": False, "interval": 1.0, "timeout": 0},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertEqual(result["msg"], "Resource not found")
        manager.cancel_resource.assert_not_called()

    @patch.object(ActionModule, "_prepare_action")
    def test_invalid_wait_options_fail_before_check_mode_return(self, mock_prepare):
        module = _make_module(args={"command_id": 42, "interval": 0}, check_mode=True)
        manager = _make_manager()
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "interval": 0, "timeout": 0},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("interval must be greater than 0", result["msg"])
        manager.cancel_resource.assert_not_called()


class TestCancelCommand(unittest.TestCase):
    """Test cancel operations."""

    @patch.object(ActionModule, "_prepare_action")
    def test_cancel_running_command(self, mock_prepare):
        module = _make_module(args={"command_id": 42})
        manager = _make_manager()
        manager.cancel_resource.return_value = {"changed": True, "id": 42, "status": "canceled"}
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "fail_if_not_running": False},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertEqual(result["id"], 42)
        self.assertEqual(result["status"], "canceled")
        manager.cancel_resource.assert_called_once_with(
            resource_id=42,
            cancel_endpoint_path="ad_hoc_commands",
            fail_if_not_running=False,
            timeout=0,
            interval=1.0,
            service="controller",
            wait=True,
        )

    @patch.object(ActionModule, "_prepare_action")
    def test_forwards_wait_options(self, mock_prepare):
        module = _make_module(args={"command_id": 42, "interval": 0.5, "timeout": 30})
        manager = _make_manager()
        manager.cancel_resource.return_value = {"changed": True, "id": 42, "status": "canceled"}
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "interval": 0.5, "timeout": 30},
            "manager": manager,
        }

        module.run(task_vars={})

        manager.cancel_resource.assert_called_once_with(
            resource_id=42,
            cancel_endpoint_path="ad_hoc_commands",
            fail_if_not_running=False,
            timeout=30,
            interval=0.5,
            service="controller",
            wait=True,
        )

    @patch.object(ActionModule, "_prepare_action")
    def test_cancel_already_finished(self, mock_prepare):
        module = _make_module(args={"command_id": 42})
        manager = _make_manager()
        manager.cancel_resource.return_value = {"changed": False, "id": 42, "status": "already finished"}
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "fail_if_not_running": False, "interval": 1.0, "timeout": 0},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertFalse(result["changed"])

    @patch.object(ActionModule, "_prepare_action")
    def test_cancel_fail_if_not_running(self, mock_prepare):
        module = _make_module(args={"command_id": 42, "fail_if_not_running": True})
        manager = _make_manager()
        manager.cancel_resource.side_effect = Exception("Ad hoc command is not running")
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "fail_if_not_running": True, "interval": 1.0, "timeout": 0},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("not running", result["msg"])
        manager.cancel_resource.assert_called_once_with(
            resource_id=42,
            cancel_endpoint_path="ad_hoc_commands",
            fail_if_not_running=True,
            timeout=0,
            interval=1.0,
            service="controller",
            wait=True,
        )

    @patch.object(ActionModule, "_prepare_action")
    def test_missing_command_id(self, mock_prepare):
        module = _make_module(args={})
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": None, "fail_if_not_running": False},
            "manager": _make_manager(),
        }

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("command_id is required", result["msg"])

    @patch.object(ActionModule, "_prepare_action")
    def test_command_not_found(self, mock_prepare):
        module = _make_module(args={"command_id": 99999})
        manager = _make_manager()
        manager.cancel_resource.side_effect = Exception("Resource not found")
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 99999, "fail_if_not_running": False},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("not found", result["msg"])


class TestDocumentationValidation(unittest.TestCase):
    """Exercise the action's actual module-documentation argument validation."""

    @patch.object(ActionBase, "run", return_value={})
    def test_validated_options_reach_cancel_client_with_docs_types(self, _base_run):
        module = _make_module(args={"command_id": "42", "interval": "0.5", "timeout": "30"})
        manager = _make_manager()
        manager.cancel_resource.return_value = {"changed": True, "id": 42, "status": "canceled"}

        with patch.object(module, "_get_or_spawn_manager", return_value=(manager, None)):
            result = module.run(task_vars={})

        self.assertEqual(result["status"], "canceled")
        manager.cancel_resource.assert_called_once_with(
            resource_id=42,
            cancel_endpoint_path="ad_hoc_commands",
            fail_if_not_running=False,
            timeout=30,
            interval=0.5,
            service="controller",
            wait=True,
        )

    @patch.object(ActionBase, "run", return_value={})
    def test_invalid_documented_type_fails_before_manager_startup(self, _base_run):
        module = _make_module(args={"command_id": "42", "interval": "not-a-number"})
        manager_factory = MagicMock(return_value=(_make_manager(), None))

        with patch.object(module, "_get_or_spawn_manager", manager_factory):
            result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("interval", result["msg"])
        manager_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
