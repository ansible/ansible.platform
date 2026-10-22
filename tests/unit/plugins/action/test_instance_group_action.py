# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the instance_group action plugin (Pattern C associations)."""

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.action.instance_group import ActionModule


class TestInstanceGroupAssociations(unittest.TestCase):
    def _make_action(self, args):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.args = dict(args)
        action._task.check_mode = False
        action._display = MagicMock()
        action._client = MagicMock()
        return action

    @patch.object(BaseResourceActionPlugin, "run")
    def test_instances_association_called(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "id": 10,
            "instance_group": {"id": 10, "name": "prod-group"},
        }
        action = self._make_action(
            {
                "name": "prod-group",
                "state": "present",
                "instances": ["node1.example.com", "node2.example.com"],
            }
        )
        action._client.manage_associations.return_value = True

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.manage_associations.assert_called_once_with(
            "instance_groups",
            10,
            "instances",
            ["node1.example.com", "node2.example.com"],
            "instances",
            "hostname",
            service="controller",
        )

    @patch.object(BaseResourceActionPlugin, "run")
    def test_instances_skipped_on_absent(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "instance_group": {"state": "absent"},
        }
        action = self._make_action(
            {
                "name": "prod-group",
                "state": "absent",
                "instances": ["node1.example.com"],
            }
        )

        action.run(task_vars={})

        action._client.manage_associations.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_instances_skipped_on_exists(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": False,
            "exists": True,
            "id": 10,
            "instance_group": {"id": 10},
        }
        action = self._make_action(
            {
                "name": "prod-group",
                "state": "exists",
                "instances": ["node1.example.com"],
            }
        )

        action.run(task_vars={})

        action._client.manage_associations.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_no_instances_when_not_provided(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "id": 10,
            "instance_group": {"id": 10, "name": "prod-group"},
        }
        action = self._make_action(
            {
                "name": "prod-group",
                "state": "present",
            }
        )

        action.run(task_vars={})

        action._client.manage_associations.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_instances_field_popped_before_super(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "id": 10,
            "instance_group": {"id": 10},
        }
        action = self._make_action(
            {
                "name": "prod-group",
                "state": "present",
                "instances": ["node1.example.com"],
            }
        )
        action._client.manage_associations.return_value = False

        action.run(task_vars={})

        self.assertNotIn("instances", action._task.args)

    @patch.object(BaseResourceActionPlugin, "run")
    def test_failed_crud_skips_instances(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": True,
            "msg": "Not found",
        }
        action = self._make_action(
            {
                "name": "prod-group",
                "state": "present",
                "instances": ["node1.example.com"],
            }
        )

        result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        action._client.manage_associations.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_changed_false_when_instances_unchanged(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": False,
            "id": 10,
            "instance_group": {"id": 10},
        }
        action = self._make_action(
            {
                "name": "prod-group",
                "state": "present",
                "instances": ["node1.example.com"],
            }
        )
        action._client.manage_associations.return_value = False

        result = action.run(task_vars={})

        self.assertFalse(result["changed"])

    @patch.object(BaseResourceActionPlugin, "run")
    def test_id_from_nested_result(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "instance_group": {"id": 55, "name": "group"},
        }
        action = self._make_action(
            {
                "name": "group",
                "state": "present",
                "instances": ["node1.example.com"],
            }
        )
        action._client.manage_associations.return_value = True

        action.run(task_vars={})

        call = action._client.manage_associations.call_args
        self.assertEqual(call.args[1], 55)


if __name__ == "__main__":
    unittest.main()
