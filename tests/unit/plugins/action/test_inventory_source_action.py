# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the inventory_source action plugin (Pattern C associations)."""

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.action.inventory_source import ActionModule


class TestInventorySourceAssociations(unittest.TestCase):
    def _make_action(self, args, check_mode=False):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.args = dict(args)
        action._task.check_mode = check_mode
        action._display = MagicMock()
        action._client = MagicMock()
        return action

    @patch.object(BaseResourceActionPlugin, "run")
    def test_associations_called_after_crud(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "id": 42,
            "inventory_source": {"id": 42, "name": "ec2-src"},
        }
        action = self._make_action(
            {
                "name": "ec2-src",
                "inventory": "Prod",
                "state": "present",
                "notification_templates_started": ["Slack Start"],
                "notification_templates_success": ["Email OK"],
                "notification_templates_error": ["PagerDuty", "Slack Error"],
            }
        )
        action._client.manage_associations.return_value = True

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertEqual(action._client.manage_associations.call_count, 3)

        calls = {c.args[2]: c for c in action._client.manage_associations.call_args_list}

        started_call = calls["notification_templates_started"]
        self.assertEqual(started_call.args[0], "inventory_sources")
        self.assertEqual(started_call.args[1], 42)
        self.assertEqual(started_call.args[3], ["Slack Start"])
        self.assertEqual(started_call.args[4], "notification_templates")
        self.assertEqual(started_call.args[5], "name")
        self.assertEqual(started_call.kwargs["service"], "controller")

        error_call = calls["notification_templates_error"]
        self.assertEqual(error_call.args[3], ["PagerDuty", "Slack Error"])

    @patch.object(BaseResourceActionPlugin, "run")
    def test_associations_skipped_on_absent(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "inventory_source": {"state": "absent"},
        }
        action = self._make_action(
            {
                "name": "ec2-src",
                "inventory": "Prod",
                "state": "absent",
                "notification_templates_started": ["Slack Start"],
            }
        )

        action.run(task_vars={})

        action._client.manage_associations.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_associations_skipped_on_exists(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": False,
            "exists": True,
            "id": 42,
            "inventory_source": {"id": 42},
        }
        action = self._make_action(
            {
                "name": "ec2-src",
                "inventory": "Prod",
                "state": "exists",
                "notification_templates_started": ["Slack Start"],
            }
        )

        action.run(task_vars={})

        action._client.manage_associations.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_no_associations_when_not_provided(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "id": 42,
            "inventory_source": {"id": 42, "name": "ec2-src"},
        }
        action = self._make_action(
            {
                "name": "ec2-src",
                "inventory": "Prod",
                "state": "present",
            }
        )

        action.run(task_vars={})

        action._client.manage_associations.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_notification_fields_popped_before_super(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "id": 42,
            "inventory_source": {"id": 42},
        }
        action = self._make_action(
            {
                "name": "ec2-src",
                "inventory": "Prod",
                "state": "present",
                "notification_templates_started": ["Slack"],
            }
        )
        action._client.manage_associations.return_value = False

        action.run(task_vars={})

        self.assertNotIn("notification_templates_started", action._task.args)

    @patch.object(BaseResourceActionPlugin, "run")
    def test_failed_crud_skips_associations(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": True,
            "msg": "Not found",
        }
        action = self._make_action(
            {
                "name": "ec2-src",
                "inventory": "Prod",
                "state": "present",
                "notification_templates_started": ["Slack"],
            }
        )

        result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        action._client.manage_associations.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_changed_false_when_associations_unchanged(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": False,
            "id": 42,
            "inventory_source": {"id": 42},
        }
        action = self._make_action(
            {
                "name": "ec2-src",
                "inventory": "Prod",
                "state": "present",
                "notification_templates_started": ["Slack"],
            }
        )
        action._client.manage_associations.return_value = False

        result = action.run(task_vars={})

        self.assertFalse(result["changed"])

    @patch.object(BaseResourceActionPlugin, "run")
    def test_id_from_nested_result(self, mock_super_run):
        """Resource ID extracted from nested module_name dict when not top-level."""
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "inventory_source": {"id": 55, "name": "src"},
        }
        action = self._make_action(
            {
                "name": "src",
                "inventory": "Prod",
                "state": "present",
                "notification_templates_success": ["Email"],
            }
        )
        action._client.manage_associations.return_value = True

        action.run(task_vars={})

        call = action._client.manage_associations.call_args
        self.assertEqual(call.args[1], 55)


if __name__ == "__main__":
    unittest.main()
