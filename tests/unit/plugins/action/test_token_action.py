"""Tests for legacy token deletion constraints."""

import unittest
from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.token import ActionModule


class TestTokenDeleteValidation(unittest.TestCase):
    """Validate deletion arguments through the real action argument spec."""

    def test_invalid_delete_arguments_fail_before_manager_start(self):
        """Reject missing and conflicting deletion identifiers."""
        for identifiers in ({}, {"existing_token": {"id": 42}, "existing_token_id": "42"}):
            with self.subTest(identifiers=identifiers):
                action = ActionModule.__new__(ActionModule)
                action._task = MagicMock()
                action._task.args = {"state": "absent", **identifiers}
                action._task.check_mode = False
                action._display = MagicMock()
                action._display.verbosity = 0
                action._get_or_spawn_manager = MagicMock()

                with patch.object(ActionBase, "run", return_value={}):
                    result = action.run(task_vars={})

                self.assertTrue(result["failed"])
                self.assertIn("existing_token", result["msg"])
                action._get_or_spawn_manager.assert_not_called()

    def test_each_identifier_form_can_delete_in_check_mode(self):
        """Accept either supported identifier without performing deletion."""
        for identifiers in ({"existing_token": {"id": 42}}, {"existing_token_id": "42"}):
            with self.subTest(identifiers=identifiers):
                action = ActionModule.__new__(ActionModule)
                action._task = MagicMock()
                action._task.args = {"state": "absent", **identifiers}
                action._task.check_mode = True
                action._display = MagicMock()
                action._display.verbosity = 0
                manager = MagicMock()
                action._get_or_spawn_manager = MagicMock(return_value=(manager, None))

                with patch.object(ActionBase, "run", return_value={}):
                    result = action.run(task_vars={})

                self.assertFalse(result["failed"])
                self.assertTrue(result["changed"])
                self.assertEqual(result["token"]["id"], 42)
                manager.execute.assert_not_called()
