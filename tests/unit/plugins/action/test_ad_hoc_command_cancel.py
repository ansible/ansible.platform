# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the ad_hoc_command_cancel action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import unittest
from unittest.mock import MagicMock, patch

from ansible.playbook.task import Task
from ansible_collections.ansible.platform.plugins.action.ad_hoc_command_cancel import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.ad_hoc_command_cancel import AnsibleAdHocCommandCancel


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


class TestActionModuleAttributes(unittest.TestCase):
    """Test basic class attributes."""

    def test_module_name(self):
        module = _make_module()
        self.assertEqual(module.MODULE_NAME, "ad_hoc_command_cancel")

    def test_model_class(self):
        module = _make_module()
        self.assertEqual(module.MODEL_CLASS, AnsibleAdHocCommandCancel)

    def test_lookup_field(self):
        module = _make_module()
        self.assertEqual(module.LOOKUP_FIELD, "command_id")


class TestCheckMode(unittest.TestCase):
    """Test check mode behavior."""

    @patch.object(ActionModule, "_prepare_action")
    def test_check_mode_skips_cancel(self, mock_prepare):
        module = _make_module(args={"command_id": 42}, check_mode=True)
        manager = MagicMock()
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "fail_if_not_running": False},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertEqual(result["id"], 42)
        self.assertIn("check mode", result["status"])
        manager.cancel_resource.assert_not_called()


class TestCancelCommand(unittest.TestCase):
    """Test cancel operations."""

    @patch.object(ActionModule, "_prepare_action")
    def test_cancel_running_command(self, mock_prepare):
        module = _make_module(args={"command_id": 42})
        manager = MagicMock()
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
            service="controller",
        )

    @patch.object(ActionModule, "_prepare_action")
    def test_cancel_already_finished(self, mock_prepare):
        module = _make_module(args={"command_id": 42})
        manager = MagicMock()
        manager.cancel_resource.return_value = {"changed": False, "id": 42, "status": "already finished"}
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "fail_if_not_running": False},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertFalse(result["changed"])

    @patch.object(ActionModule, "_prepare_action")
    def test_cancel_fail_if_not_running(self, mock_prepare):
        module = _make_module(args={"command_id": 42, "fail_if_not_running": True})
        manager = MagicMock()
        manager.cancel_resource.side_effect = Exception("Ad hoc command is not running")
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "fail_if_not_running": True},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("not running", result["msg"])
        manager.cancel_resource.assert_called_once_with(
            resource_id=42,
            cancel_endpoint_path="ad_hoc_commands",
            fail_if_not_running=True,
            service="controller",
        )

    @patch.object(ActionModule, "_prepare_action")
    def test_missing_command_id(self, mock_prepare):
        module = _make_module(args={})
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": None, "fail_if_not_running": False},
            "manager": MagicMock(),
        }

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("command_id is required", result["msg"])

    @patch.object(ActionModule, "_prepare_action")
    def test_command_not_found(self, mock_prepare):
        module = _make_module(args={"command_id": 99999})
        manager = MagicMock()
        manager.cancel_resource.side_effect = Exception("Resource not found")
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 99999, "fail_if_not_running": False},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("not found", result["msg"])


class TestAnsibleModel(unittest.TestCase):
    """Test the AnsibleAdHocCommandCancel dataclass."""

    def test_defaults(self):
        model = AnsibleAdHocCommandCancel()
        self.assertEqual(model.command_id, 0)
        self.assertFalse(model.fail_if_not_running)
        self.assertIsNone(model.id)

    def test_construction(self):
        model = AnsibleAdHocCommandCancel(command_id=42, fail_if_not_running=True)
        self.assertEqual(model.command_id, 42)
        self.assertTrue(model.fail_if_not_running)

    def test_round_trip(self):
        from dataclasses import asdict

        model = AnsibleAdHocCommandCancel(command_id=99, fail_if_not_running=False)
        d = asdict(model)
        self.assertEqual(d["command_id"], 99)
        reconstructed = AnsibleAdHocCommandCancel(**d)
        self.assertEqual(reconstructed, model)


class TestTransformMixin(unittest.TestCase):
    """Test the AdHocCommandCancelTransformMixin_v2."""

    def test_from_ansible_data(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.ad_hoc_command_cancel import (
            AdHocCommandCancelTransformMixin_v2,
            APIAdHocCommandCancel_v2,
        )

        ansible_data = AnsibleAdHocCommandCancel(command_id=42, fail_if_not_running=True)
        ctx = MagicMock()
        api_data = AdHocCommandCancelTransformMixin_v2.from_ansible_data(ansible_data, ctx)

        self.assertIsInstance(api_data, APIAdHocCommandCancel_v2)
        self.assertEqual(api_data.command_id, 42)
        self.assertTrue(api_data.fail_if_not_running)

    def test_from_api(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.ad_hoc_command_cancel import (
            AdHocCommandCancelTransformMixin_v2,
        )

        api_response = {"id": 42, "name": "some-command", "status": "running"}
        ctx = MagicMock()
        ansible_data = AdHocCommandCancelTransformMixin_v2.from_api(api_response, ctx)

        self.assertIsInstance(ansible_data, AnsibleAdHocCommandCancel)
        self.assertEqual(ansible_data.command_id, 42)

    def test_get_lookup_field(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.ad_hoc_command_cancel import (
            AdHocCommandCancelTransformMixin_v2,
        )

        self.assertEqual(AdHocCommandCancelTransformMixin_v2.get_lookup_field(), "command_id")

    def test_endpoint_operations(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.ad_hoc_command_cancel import (
            AdHocCommandCancelTransformMixin_v2,
        )

        ops = AdHocCommandCancelTransformMixin_v2.get_endpoint_operations()
        self.assertIn("list", ops)
        self.assertIn("get", ops)
        self.assertIn("ad_hoc_commands", ops["list"].path)
        self.assertIn("ad_hoc_commands", ops["get"].path)


if __name__ == "__main__":
    unittest.main()
