# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the service_key action plugin."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.service_key import ActionModule


class TestServiceKeyAction(unittest.TestCase):
    def test_present_returns_gateway_error_when_service_key_is_missing(self):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.check_mode = False
        action._display = MagicMock()
        action._display.verbosity = 0
        manager = MagicMock()
        manager.execute.side_effect = [
            None,
            ValueError("405 Client Error\nResponse body: {'detail': 'Service keys cannot be created through this endpoint.'}"),
        ]
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
        self.assertIn("405 Client Error", result["msg"])
        self.assertIn("Service keys cannot be created through this endpoint.", result["msg"])
        manager.execute.assert_any_call(
            operation="find",
            module_name="service_key",
            ansible_data={"name": "missing-key", "is_active": True},
        )
        create_call = manager.execute.call_args_list[1].kwargs
        self.assertEqual(create_call["operation"], "create")
        self.assertEqual(create_call["module_name"], "service_key")
        self.assertEqual(create_call["ansible_data"]["name"], "missing-key")
        self.assertIs(create_call["ansible_data"]["is_active"], True)

    def test_prepare_action_warns_and_ignores_deprecated_creation_fields(self):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.args = {
            "name": "existing-key",
            "is_active": True,
            "service_cluster": "gateway",
            "secret": "secret-value",
            "secret_length": 32,
            "mark_previous_inactive": True,
            "algorithm": "HS256",
        }
        action._display = MagicMock()
        manager = MagicMock()
        validation = SimpleNamespace(validated_parameters=dict(action._task.args))

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_documentation", return_value="module: service_key"):
                with patch.object(action, "_build_argspec_from_docs", return_value={"argument_spec": {}}):
                    with patch.object(action, "_validate_data", return_value=validation):
                        with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                            prepared = action._prepare_action()

        self.assertEqual(prepared["resource_data"], {"name": "existing-key", "is_active": True})
        self.assertEqual(len(prepared["result"]["deprecations"]), 5)


if __name__ == "__main__":
    unittest.main()
