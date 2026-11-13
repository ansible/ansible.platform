# (c) 2026 Ansible Platform Collection Contributors

from __future__ import absolute_import, division, print_function

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock


class TestControllerSettingsAction(unittest.TestCase):
    def _action(self, current, updated=None, *, check_mode=False, diff=False, validated_params=None):
        from ansible_collections.ansible.platform.plugins.action.controller_settings import ActionModule

        action = ActionModule.__new__(ActionModule)
        action._display = MagicMock()
        action._task = SimpleNamespace(check_mode=check_mode, diff=diff)
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.loader import DynamicClassLoader
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry import APIVersionRegistry

        # Exercise the action and real SDK together, mocking only HTTP and the
        # Ansible task setup. This keeps result/redaction tests independent of
        # where the update decisions are implemented.
        service = PlatformService.__new__(PlatformService)
        service.record_activity = MagicMock()
        service.session = MagicMock()
        service.cache = {}
        service.base_url = "https://gateway.example"
        service.api_versions = {"controller": "2", "gateway": "1"}
        service.registry = APIVersionRegistry()
        service.loader = DynamicClassLoader(service.registry)
        responses = []
        for settings in (current, updated if updated is not None else current):
            response = MagicMock()
            response.json.return_value = settings
            response.content = b"nonempty"
            responses.append(response)
        service._make_request = MagicMock(side_effect=responses)

        def execute(operation, module_name, ansible_data):
            return service.execute(operation, module_name, ansible_data_dict=ansible_data)

        manager = MagicMock()
        manager.execute.side_effect = execute
        manager.http = service._make_request
        action._prepare_action = MagicMock(
            return_value={
                "result": {},
                "validated_params": validated_params or {"name": "DEFAULT_JOB_TIMEOUT", "value": "3600", "settings": None},
                "manager": manager,
            }
        )
        return action, manager

    def test_requires_exactly_one_input_form(self):
        for params in (
            {"name": None, "value": None, "settings": None},
            {"name": "DEFAULT_JOB_TIMEOUT", "value": "1", "settings": {"DEFAULT_JOB_TIMEOUT": 1}},
        ):
            action = self._action({"DEFAULT_JOB_TIMEOUT": 0}, validated_params=params)[0]
            action._task.args = params
            with self.assertRaises(Exception):
                action._validate_action_input()

    def test_rejects_unknown_settings(self):
        action, manager = self._action(
            {"DEFAULT_JOB_TIMEOUT": 0},
            validated_params={"name": None, "value": None, "settings": {"UNKNOWN_SETTING": 1}},
        )

        result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("Unknown Controller setting(s): UNKNOWN_SETTING", result["msg"])
        self.assertEqual(manager.execute.call_count, 1)

    def test_sensitive_inputs_are_marked_no_log(self):
        from ansible_collections.ansible.platform.plugins.action.controller_settings import ActionModule

        action = ActionModule.__new__(ActionModule)
        action._display = MagicMock()
        argspec = action._build_argspec_from_docs(action._get_documentation())
        self.assertTrue(argspec["argument_spec"]["value"]["no_log"])
        self.assertTrue(argspec["argument_spec"]["settings"]["no_log"])

    def test_masked_secret_is_resent_and_redacted(self):
        action, manager = self._action(
            {"SUBSCRIPTIONS_PASSWORD": "$encrypted$"},
            {"SUBSCRIPTIONS_PASSWORD": "$encrypted$"},
            validated_params={"name": "SUBSCRIPTIONS_PASSWORD", "value": "new-secret", "settings": None},
        )

        result = action.run(task_vars={})

        # Preserve legacy behavior: a masked value is not comparable to the
        # supplied plaintext, so the secret is sent again on every run.
        self.assertTrue(result["changed"])
        self.assertEqual(manager.execute.call_count, 1)
        self.assertEqual(manager.http.call_count, 2)
        self.assertEqual(result["old_values"]["SUBSCRIPTIONS_PASSWORD"], "$encrypted$")
        self.assertEqual(result["new_values"]["SUBSCRIPTIONS_PASSWORD"], "$redacted$")
        self.assertEqual(result["value"], "$encrypted$")
        self.assertEqual(result["controller_settings"]["settings"]["SUBSCRIPTIONS_PASSWORD"], "$encrypted$")

    def test_name_value_update_and_idempotency(self):
        action, manager = self._action({"DEFAULT_JOB_TIMEOUT": 0}, {"DEFAULT_JOB_TIMEOUT": 3600})
        result = action.run(task_vars={})
        self.assertTrue(result["changed"])
        self.assertEqual(result["value"], 3600)
        self.assertEqual(manager.execute.call_count, 1)
        self.assertEqual(manager.http.call_count, 2)

        action, manager = self._action({"DEFAULT_JOB_TIMEOUT": 3600})
        result = action.run(task_vars={})
        self.assertFalse(result["changed"])
        self.assertEqual(manager.execute.call_count, 1)

    def test_check_mode_does_not_update(self):
        action, manager = self._action({"DEFAULT_JOB_TIMEOUT": 0}, check_mode=True, diff=True)
        result = action.run(task_vars={})
        self.assertTrue(result["changed"])
        self.assertIn("diff", result)
        manager.http.assert_called_once()
        self.assertEqual(manager.http.call_args.args[0].upper(), "GET")
        self.assertEqual(manager.execute.call_count, 1)


if __name__ == "__main__":
    unittest.main()
