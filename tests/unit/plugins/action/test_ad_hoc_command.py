# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the ad_hoc_command action plugin (check_mode, wait-timeout handling)."""

from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.ad_hoc_command import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import WaitTimeoutError


def _make_action(check_mode=False):
    """ActionModule with __init__ bypassed; only the attributes run() touches are set."""
    action = ActionModule.__new__(ActionModule)
    action._task = MagicMock()
    action._task.check_mode = check_mode
    action._task.args = {
        "inventory": "Demo Inventory",
        "credential": "Demo Credential",
        "module_name": "ping",
    }
    action._display = MagicMock()
    action._display.verbosity = 0
    return action


DOC = """
---
module: ad_hoc_command
options:
  inventory: {type: str, required: true}
  credential: {type: str, required: true}
  module_name: {type: str, required: true}
  wait: {type: bool, default: false}
  interval: {type: float, default: 2.0}
  timeout: {type: int}
"""


class TestCheckMode(unittest.TestCase):
    """#9: check_mode must not call manager.execute()."""

    def test_check_mode_does_not_launch(self):
        action = _make_action(check_mode=True)
        mock_manager = MagicMock()

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_documentation", return_value=DOC):
                with patch.object(action, "_get_or_spawn_manager", return_value=(mock_manager, None)):
                    result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertFalse(result.get("failed", False))
        self.assertIsNone(result["id"])
        mock_manager.execute.assert_not_called()

    def test_normal_mode_still_launches(self):
        action = _make_action(check_mode=False)
        mock_manager = MagicMock()
        mock_manager.execute.return_value = {"id": 5, "status": "pending"}

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_documentation", return_value=DOC):
                with patch.object(action, "_get_or_spawn_manager", return_value=(mock_manager, None)):
                    result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertEqual(result["id"], 5)
        mock_manager.execute.assert_called_once()


class TestWaitTimeoutHandling(unittest.TestCase):
    """#2: a wait-timeout must not drop the launched command's id."""

    def test_timeout_preserves_id_and_status(self):
        action = _make_action(check_mode=False)
        mock_manager = MagicMock()
        mock_manager.execute.side_effect = WaitTimeoutError(
            "Timed out waiting for ad_hoc_command 9 to complete after 5 seconds (status: pending)",
            last_result={"id": 9, "status": "pending"},
        )

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_documentation", return_value=DOC):
                with patch.object(action, "_get_or_spawn_manager", return_value=(mock_manager, None)):
                    result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertEqual(result["id"], 9)
        self.assertEqual(result["status"], "pending")

    def test_terminal_failed_status_sets_failed_and_keeps_id(self):
        action = _make_action(check_mode=False)
        mock_manager = MagicMock()
        mock_manager.execute.return_value = {"id": 3, "status": "failed"}

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_documentation", return_value=DOC):
                with patch.object(action, "_get_or_spawn_manager", return_value=(mock_manager, None)):
                    result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertEqual(result["id"], 3)
        self.assertEqual(result["status"], "failed")


if __name__ == "__main__":
    unittest.main()
