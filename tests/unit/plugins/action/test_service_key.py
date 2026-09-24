# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the service_key action plugin."""

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.action.service_key import ActionModule


class TestServiceKeyAction(unittest.TestCase):
    def test_present_fails_when_service_key_is_missing(self):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.check_mode = False
        action._display = MagicMock()
        action._display.verbosity = 0
        manager = MagicMock()
        manager.execute.return_value = None
        prepared = {
            "result": {},
            "argspec": {"argument_spec": {"name": {}, "is_active": {}}},
            "validated_params": {"name": "missing-key", "is_active": True, "state": "present"},
            "resource_data": {"name": "missing-key", "is_active": True},
            "write_only_data": {},
            "manager": manager,
        }

        with patch.object(action, "_prepare_action", return_value=prepared):
            with patch.object(action, "_resolve_lookup"):
                result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("service_key 'missing-key' does not exist", result["msg"])
        self.assertIn("only supports editing existing resources", result["msg"])
        manager.execute.assert_called_once_with(
            operation="find",
            module_name="service_key",
            ansible_data={"name": "missing-key", "is_active": True},
        )


if __name__ == "__main__":
    unittest.main()
