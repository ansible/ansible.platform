# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the group action plugin (Pattern C associations with preserve_existing)."""

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.action.group import ActionModule


class TestGroupAssociations(unittest.TestCase):
    def _make_action(self, args):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.args = dict(args)
        action._task.check_mode = False
        action._display = MagicMock()
        action._client = MagicMock()
        return action

    @patch.object(BaseResourceActionPlugin, "run")
    def test_hosts_association_called(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "id": 10,
            "group": {"id": 10, "name": "webservers"},
        }
        action = self._make_action(
            {
                "name": "webservers",
                "inventory": "Prod",
                "state": "present",
                "hosts": ["web1", "web2"],
            }
        )
        action._client.manage_associations.return_value = True

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.manage_associations.assert_called_once_with(
            "groups",
            10,
            "hosts",
            ["web1", "web2"],
            "hosts",
            "name",
            service="controller",
        )

    @patch.object(BaseResourceActionPlugin, "run")
    def test_children_association_called(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "id": 10,
            "group": {"id": 10, "name": "all"},
        }
        action = self._make_action(
            {
                "name": "all",
                "inventory": "Prod",
                "state": "present",
                "children": ["east", "west"],
            }
        )
        action._client.manage_associations.return_value = True

        action.run(task_vars={})

        action._client.manage_associations.assert_called_once_with(
            "groups",
            10,
            "children",
            ["east", "west"],
            "groups",
            "name",
            service="controller",
        )

    @patch.object(BaseResourceActionPlugin, "run")
    def test_preserve_existing_hosts_unions_with_current(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": False,
            "id": 10,
            "group": {"id": 10},
        }
        action = self._make_action(
            {
                "name": "webservers",
                "inventory": "Prod",
                "state": "present",
                "hosts": ["web3"],
                "preserve_existing_hosts": True,
            }
        )
        action._client.search_api.return_value = {
            "results": [{"id": 1, "name": "web1"}, {"id": 2, "name": "web2"}],
        }
        action._client.manage_associations.return_value = True

        action.run(task_vars={})

        action._client.search_api.assert_called_once_with(
            "/api/controller/v2/groups/10/hosts/",
            return_all=True,
        )
        call_args = action._client.manage_associations.call_args
        desired = call_args.args[3]
        self.assertIn("web3", desired)
        self.assertIn("1", desired)
        self.assertIn("2", desired)

    @patch.object(BaseResourceActionPlugin, "run")
    def test_preserve_false_does_full_sync(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": False,
            "id": 10,
            "group": {"id": 10},
        }
        action = self._make_action(
            {
                "name": "webservers",
                "inventory": "Prod",
                "state": "present",
                "hosts": ["web3"],
                "preserve_existing_hosts": False,
            }
        )
        action._client.manage_associations.return_value = True

        action.run(task_vars={})

        action._client.search_api.assert_not_called()
        action._client.manage_associations.assert_called_once_with(
            "groups",
            10,
            "hosts",
            ["web3"],
            "hosts",
            "name",
            service="controller",
        )

    @patch.object(BaseResourceActionPlugin, "run")
    def test_associations_skipped_on_absent(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "group": {"state": "absent"},
        }
        action = self._make_action(
            {
                "name": "webservers",
                "inventory": "Prod",
                "state": "absent",
                "hosts": ["web1"],
            }
        )

        action.run(task_vars={})

        action._client.manage_associations.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_fields_popped_before_super(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "id": 10,
            "group": {"id": 10},
        }
        action = self._make_action(
            {
                "name": "webservers",
                "inventory": "Prod",
                "state": "present",
                "hosts": ["web1"],
                "children": ["east"],
                "preserve_existing_hosts": True,
                "preserve_existing_children": False,
            }
        )
        action._client.search_api.return_value = {"results": []}
        action._client.manage_associations.return_value = False

        action.run(task_vars={})

        self.assertNotIn("hosts", action._task.args)
        self.assertNotIn("children", action._task.args)
        self.assertNotIn("preserve_existing_hosts", action._task.args)
        self.assertNotIn("preserve_existing_children", action._task.args)

    @patch.object(BaseResourceActionPlugin, "run")
    def test_failed_crud_skips_associations(self, mock_super_run):
        mock_super_run.return_value = {"changed": False, "failed": True, "msg": "error"}
        action = self._make_action(
            {
                "name": "webservers",
                "inventory": "Prod",
                "state": "present",
                "hosts": ["web1"],
            }
        )

        result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        action._client.manage_associations.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_changed_false_when_no_association_changes(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": False,
            "id": 10,
            "group": {"id": 10},
        }
        action = self._make_action(
            {
                "name": "webservers",
                "inventory": "Prod",
                "state": "present",
                "hosts": ["web1"],
            }
        )
        action._client.manage_associations.return_value = False

        result = action.run(task_vars={})

        self.assertFalse(result["changed"])


if __name__ == "__main__":
    unittest.main()
