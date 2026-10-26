# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the ad_hoc_command_wait action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import unittest
from unittest.mock import MagicMock, patch

from ansible.playbook.task import Task
from ansible_collections.ansible.platform.plugins.action.ad_hoc_command_wait import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.ad_hoc_command_wait import AnsibleAdHocCommandWait
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError


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
        self.assertEqual(module.MODULE_NAME, "ad_hoc_command_wait")

    def test_model_class(self):
        module = _make_module()
        self.assertEqual(module.MODEL_CLASS, AnsibleAdHocCommandWait)

    def test_lookup_field(self):
        module = _make_module()
        self.assertEqual(module.LOOKUP_FIELD, "command_id")


class TestCheckMode(unittest.TestCase):
    """Test check mode behavior."""

    @patch.object(ActionModule, "_prepare_action")
    def test_check_mode_skips_wait(self, mock_prepare):
        module = _make_module(args={"command_id": 42}, check_mode=True)
        manager = MagicMock()
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "interval": 2.0, "timeout": None},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertFalse(result["changed"])
        self.assertEqual(result["id"], 42)
        self.assertIn("check mode", result["status"])
        manager.wait_for_completion.assert_not_called()


class TestWaitCommand(unittest.TestCase):
    """Test wait operations."""

    @patch.object(ActionModule, "_prepare_action")
    def test_wait_successful(self, mock_prepare):
        module = _make_module(args={"command_id": 42})
        manager = MagicMock()
        manager.wait_for_completion.return_value = {
            "id": 42,
            "status": "successful",
            "elapsed": 5.2,
            "started": "2026-01-01T00:00:00Z",
            "finished": "2026-01-01T00:00:05Z",
        }
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "interval": 2.0, "timeout": None},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])
        self.assertEqual(result["id"], 42)
        self.assertEqual(result["status"], "successful")
        self.assertEqual(result["elapsed"], 5.2)
        self.assertEqual(result["started"], "2026-01-01T00:00:00Z")
        self.assertEqual(result["finished"], "2026-01-01T00:00:05Z")
        manager.wait_for_completion.assert_called_once_with(
            resource_url="/api/controller/v2/ad_hoc_commands/42/",
            timeout=None,
            interval=2.0,
            service="controller",
        )

    @patch.object(ActionModule, "_prepare_action")
    def test_wait_failed_status(self, mock_prepare):
        module = _make_module(args={"command_id": 42})
        manager = MagicMock()
        manager.wait_for_completion.return_value = {
            "id": 42,
            "status": "failed",
            "elapsed": 3.0,
            "started": "2026-01-01T00:00:00Z",
            "finished": "2026-01-01T00:00:03Z",
        }
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "interval": 2.0, "timeout": None},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("failed", result["msg"])
        self.assertEqual(result["status"], "failed")

    @patch.object(ActionModule, "_prepare_action")
    def test_wait_error_status(self, mock_prepare):
        module = _make_module(args={"command_id": 42})
        manager = MagicMock()
        manager.wait_for_completion.return_value = {
            "id": 42,
            "status": "error",
            "elapsed": 1.0,
            "started": "2026-01-01T00:00:00Z",
            "finished": "2026-01-01T00:00:01Z",
        }
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "interval": 2.0, "timeout": None},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("error", result["msg"])

    @patch.object(ActionModule, "_prepare_action")
    def test_wait_canceled_status(self, mock_prepare):
        module = _make_module(args={"command_id": 42})
        manager = MagicMock()
        manager.wait_for_completion.return_value = {
            "id": 42,
            "status": "canceled",
            "elapsed": 2.0,
            "started": "2026-01-01T00:00:00Z",
            "finished": "2026-01-01T00:00:02Z",
        }
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "interval": 2.0, "timeout": None},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("canceled", result["msg"])

    @patch.object(ActionModule, "_prepare_action")
    def test_wait_timeout(self, mock_prepare):
        module = _make_module(args={"command_id": 42, "timeout": 10})
        manager = MagicMock()
        manager.wait_for_completion.side_effect = WaitTimeoutError(
            "Timed out waiting after 10s",
            last_result={"id": 42, "status": "running", "elapsed": 0.0},
        )
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "interval": 2.0, "timeout": 10},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("Timed out", result["msg"])
        self.assertEqual(result["id"], 42)
        self.assertEqual(result["status"], "running")

    @patch.object(ActionModule, "_prepare_action")
    def test_wait_with_custom_interval(self, mock_prepare):
        module = _make_module(args={"command_id": 42, "interval": 5.0, "timeout": 60})
        manager = MagicMock()
        manager.wait_for_completion.return_value = {
            "id": 42,
            "status": "successful",
            "elapsed": 10.0,
            "started": "2026-01-01T00:00:00Z",
            "finished": "2026-01-01T00:00:10Z",
        }
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "interval": 5.0, "timeout": 60},
            "manager": manager,
        }

        module.run(task_vars={})

        manager.wait_for_completion.assert_called_once_with(
            resource_url="/api/controller/v2/ad_hoc_commands/42/",
            timeout=60.0,
            interval=5.0,
            service="controller",
        )

    @patch.object(ActionModule, "_prepare_action")
    def test_missing_command_id(self, mock_prepare):
        module = _make_module(args={})
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": None, "interval": 2.0, "timeout": None},
            "manager": MagicMock(),
        }

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("command_id is required", result["msg"])

    @patch.object(ActionModule, "_prepare_action")
    def test_command_not_found(self, mock_prepare):
        module = _make_module(args={"command_id": 99999})
        manager = MagicMock()
        manager.wait_for_completion.side_effect = Exception("Resource not found")
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 99999, "interval": 2.0, "timeout": None},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("not found", result["msg"])

    @patch.object(ActionModule, "_prepare_action")
    def test_changed_always_false(self, mock_prepare):
        module = _make_module(args={"command_id": 42})
        manager = MagicMock()
        manager.wait_for_completion.return_value = {
            "id": 42,
            "status": "successful",
            "elapsed": 1.0,
            "started": "2026-01-01T00:00:00Z",
            "finished": "2026-01-01T00:00:01Z",
        }
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"command_id": 42, "interval": 2.0, "timeout": None},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertFalse(result["changed"])


class TestAnsibleModel(unittest.TestCase):
    """Test the AnsibleAdHocCommandWait dataclass."""

    def test_defaults(self):
        model = AnsibleAdHocCommandWait()
        self.assertEqual(model.command_id, 0)
        self.assertEqual(model.interval, 2.0)
        self.assertIsNone(model.timeout)
        self.assertIsNone(model.id)

    def test_construction(self):
        model = AnsibleAdHocCommandWait(command_id=42, interval=5.0, timeout=120)
        self.assertEqual(model.command_id, 42)
        self.assertEqual(model.interval, 5.0)
        self.assertEqual(model.timeout, 120)

    def test_round_trip(self):
        from dataclasses import asdict

        model = AnsibleAdHocCommandWait(command_id=99, interval=3.0, timeout=60)
        d = asdict(model)
        self.assertEqual(d["command_id"], 99)
        reconstructed = AnsibleAdHocCommandWait(**d)
        self.assertEqual(reconstructed, model)


class TestTransformMixin(unittest.TestCase):
    """Test the AdHocCommandWaitTransformMixin_v2."""

    def test_from_ansible_data(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.ad_hoc_command_wait import (
            AdHocCommandWaitTransformMixin_v2,
            APIAdHocCommandWait_v2,
        )

        ansible_data = AnsibleAdHocCommandWait(command_id=42, interval=5.0, timeout=120)
        ctx = MagicMock()
        api_data = AdHocCommandWaitTransformMixin_v2.from_ansible_data(ansible_data, ctx)

        self.assertIsInstance(api_data, APIAdHocCommandWait_v2)
        self.assertEqual(api_data.command_id, 42)
        self.assertEqual(api_data.interval, 5.0)
        self.assertEqual(api_data.timeout, 120)

    def test_from_api(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.ad_hoc_command_wait import (
            AdHocCommandWaitTransformMixin_v2,
        )

        api_response = {"id": 42, "name": "some-command", "status": "running"}
        ctx = MagicMock()
        ansible_data = AdHocCommandWaitTransformMixin_v2.from_api(api_response, ctx)

        self.assertIsInstance(ansible_data, AnsibleAdHocCommandWait)
        self.assertEqual(ansible_data.command_id, 42)

    def test_get_lookup_field(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.ad_hoc_command_wait import (
            AdHocCommandWaitTransformMixin_v2,
        )

        self.assertEqual(AdHocCommandWaitTransformMixin_v2.get_lookup_field(), "command_id")

    def test_endpoint_operations(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.ad_hoc_command_wait import (
            AdHocCommandWaitTransformMixin_v2,
        )

        ops = AdHocCommandWaitTransformMixin_v2.get_endpoint_operations()
        self.assertIn("list", ops)
        self.assertIn("get", ops)
        self.assertIn("ad_hoc_commands", ops["list"].path)
        self.assertIn("ad_hoc_commands", ops["get"].path)


if __name__ == "__main__":
    unittest.main()
