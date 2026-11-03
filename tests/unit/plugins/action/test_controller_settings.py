# (c) 2026 Ansible Platform Collection Contributors

from __future__ import absolute_import, division, print_function

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock


class TestControllerSettingsAction(unittest.TestCase):
    def _action(self, current, updated=None, *, check_mode=False, diff=False):
        from ansible_collections.ansible.platform.plugins.action.controller_settings import ActionModule

        action = ActionModule.__new__(ActionModule)
        action._display = MagicMock()
        action._task = SimpleNamespace(check_mode=check_mode, diff=diff)
        manager = MagicMock()
        manager.execute.side_effect = [
            {"settings": current},
            {"settings": updated if updated is not None else current},
        ]
        action._prepare_action = MagicMock(
            return_value={
                "result": {},
                "validated_params": {"name": "DEFAULT_JOB_TIMEOUT", "value": "3600", "settings": None},
                "manager": manager,
            }
        )
        return action, manager

    def test_coerce_type(self):
        from ansible_collections.ansible.platform.plugins.action.controller_settings import ActionModule

        self.assertEqual(ActionModule._coerce_type("true"), True)
        self.assertEqual(ActionModule._coerce_type("42"), 42)
        self.assertEqual(ActionModule._coerce_type("[a, b]"), ["a", "b"])
        self.assertEqual(ActionModule._coerce_type("plain"), "plain")

    def test_name_value_update_and_idempotency(self):
        action, manager = self._action({"DEFAULT_JOB_TIMEOUT": 0}, {"DEFAULT_JOB_TIMEOUT": 3600})
        result = action.run(task_vars={})
        self.assertTrue(result["changed"])
        self.assertEqual(result["value"], 3600)
        self.assertEqual(manager.execute.call_count, 2)

        action, manager = self._action({"DEFAULT_JOB_TIMEOUT": 3600})
        result = action.run(task_vars={})
        self.assertFalse(result["changed"])
        self.assertEqual(manager.execute.call_count, 1)

    def test_check_mode_does_not_update(self):
        action, manager = self._action({"DEFAULT_JOB_TIMEOUT": 0}, check_mode=True, diff=True)
        result = action.run(task_vars={})
        self.assertTrue(result["changed"])
        self.assertIn("diff", result)
        self.assertEqual(manager.execute.call_count, 1)


if __name__ == "__main__":
    unittest.main()
