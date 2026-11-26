"""Tests for application action result formatting."""

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.action.application import ActionModule


class TestApplicationActionOutput(unittest.TestCase):
    def test_unchanged_results_split_both_redirect_uri_fields(self):
        for state in ("present", "enforced"):
            with self.subTest(state=state):
                action = ActionModule.__new__(ActionModule)
                action._task = MagicMock()
                action._task.check_mode = False
                action._display = MagicMock()
                action._display.verbosity = 0
                manager = MagicMock()
                manager.execute.return_value = {
                    "id": 7,
                    "name": "example",
                    "redirect_uris": "https://one.example/callback?scope=read,write https://two.example/callback",
                    "post_logout_redirect_uris": "https://one.example/logout?state=a,b https://two.example/logout",
                }
                prepared = {
                    "result": {},
                    "argspec": {
                        "argument_spec": {
                            "name": {},
                            "redirect_uris": {"type": "list", "elements": "str"},
                            "post_logout_redirect_uris": {"type": "list", "elements": "str"},
                        }
                    },
                    "validated_params": {"name": "example", "state": state},
                    "resource_data": {"name": "example"},
                    "write_only_data": {},
                    "manager": manager,
                }

                with patch.object(action, "_prepare_action", return_value=prepared):
                    with patch.object(action, "_should_update", return_value=False):
                        result = action.run(task_vars={})

                redirect_uris = ["https://one.example/callback?scope=read,write", "https://two.example/callback"]
                post_logout_uris = ["https://one.example/logout?state=a,b", "https://two.example/logout"]
                self.assertFalse(result["changed"])
                self.assertEqual(result["redirect_uris"], redirect_uris)
                self.assertEqual(result["post_logout_redirect_uris"], post_logout_uris)
                self.assertEqual(result["application"]["redirect_uris"], redirect_uris)
                self.assertEqual(result["application"]["post_logout_redirect_uris"], post_logout_uris)
                manager.execute.assert_called_once_with(operation="find", module_name="application", ansible_data={"name": "example"})


if __name__ == "__main__":
    unittest.main()
