# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the job_launch action plugin (Shape 2)."""

import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.action.job_launch import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import WaitTimeoutError


class TestJobLaunchAction(unittest.TestCase):
    def _make_action(self, args, check_mode=False):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.args = dict(args)
        action._task.check_mode = check_mode
        action._task.environment = []
        action._display = MagicMock()
        action._display.verbosity = 0
        action._connection = MagicMock()
        action._loader = MagicMock()
        action._templar = MagicMock()
        action._shared_loader_obj = MagicMock()
        action._client = MagicMock()
        return action

    def _patch_prepare(self, action, manager=None):
        if manager is None:
            manager = action._client
        action._get_documentation = MagicMock(return_value={"module": "job_launch", "options": {}})
        action._build_argspec_from_docs = MagicMock(return_value={"argument_spec": {}})
        validated = MagicMock()
        validated.validated_parameters = dict(action._task.args)
        action._validate_data = MagicMock(return_value=validated)
        action._get_or_spawn_manager = MagicMock(return_value=(manager, None))

    def test_launch_without_wait(self):
        action = self._make_action({"name": "Demo", "wait": False})
        self._patch_prepare(action)

        action._client.lookup_resource_id.return_value = 1
        action._client.launch_resource.return_value = {
            "id": 42,
            "status": "pending",
            "url": "/api/controller/v2/jobs/42/",
        }

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertFalse(result.get("failed", False))
        self.assertEqual(result["id"], 42)
        self.assertEqual(result["status"], "pending")
        action._client.wait_for_completion.assert_not_called()

    def test_launch_with_wait_successful(self):
        action = self._make_action({"name": "Demo", "wait": True, "interval": 1.0})
        self._patch_prepare(action)

        action._client.lookup_resource_id.return_value = 1
        action._client.launch_resource.return_value = {
            "id": 42,
            "status": "pending",
            "url": "/api/controller/v2/jobs/42/",
        }
        action._client.wait_for_completion.return_value = {
            "id": 42,
            "status": "successful",
        }

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertFalse(result["failed"])
        self.assertEqual(result["status"], "successful")

    def test_launch_with_wait_failed_job(self):
        action = self._make_action({"name": "Demo", "wait": True, "interval": 1.0})
        self._patch_prepare(action)

        action._client.lookup_resource_id.return_value = 1
        action._client.launch_resource.return_value = {
            "id": 42,
            "status": "pending",
            "url": "/api/controller/v2/jobs/42/",
        }
        action._client.wait_for_completion.return_value = {
            "id": 42,
            "status": "failed",
        }

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertTrue(result["failed"])
        self.assertEqual(result["status"], "failed")

    def test_launch_with_wait_timeout(self):
        action = self._make_action({"name": "Demo", "wait": True, "timeout": 10, "interval": 1.0})
        self._patch_prepare(action)

        action._client.lookup_resource_id.return_value = 1
        action._client.launch_resource.return_value = {
            "id": 42,
            "status": "pending",
            "url": "/api/controller/v2/jobs/42/",
        }
        action._client.wait_for_completion.side_effect = WaitTimeoutError("Timed out", last_result={"id": 42, "status": "running"})

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertTrue(result["failed"])
        self.assertEqual(result["id"], 42)
        self.assertEqual(result["status"], "running")
        self.assertIn("Timed out", result["msg"])

    def test_check_mode_skips_launch(self):
        action = self._make_action({"name": "Demo"}, check_mode=True)
        self._patch_prepare(action)

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertFalse(result.get("failed", False))
        action._client.launch_resource.assert_not_called()

    def test_extra_vars_serialized_to_json(self):
        action = self._make_action(
            {
                "name": "1",
                "extra_vars": {"key": "val"},
                "wait": False,
            }
        )
        self._patch_prepare(action)

        action._client.launch_resource.return_value = {
            "id": 1,
            "status": "pending",
            "url": "/api/controller/v2/jobs/1/",
        }

        action.run(task_vars={})

        call_payload = action._client.launch_resource.call_args.args[1]
        self.assertEqual(call_payload["extra_vars"], '{"key": "val"}')

    def test_tags_joined_as_comma_separated(self):
        action = self._make_action(
            {
                "name": "1",
                "tags": ["web", "deploy"],
                "skip_tags": ["cleanup"],
                "wait": False,
            }
        )
        self._patch_prepare(action)

        action._client.launch_resource.return_value = {
            "id": 1,
            "status": "pending",
            "url": "/api/controller/v2/jobs/1/",
        }

        action.run(task_vars={})

        call_payload = action._client.launch_resource.call_args.args[1]
        self.assertEqual(call_payload["job_tags"], "web,deploy")
        self.assertEqual(call_payload["skip_tags"], "cleanup")

    def test_fk_resolution_with_names(self):
        action = self._make_action(
            {
                "name": "Demo",
                "inventory": "Prod",
                "credentials": ["AWS"],
                "execution_environment": "My EE",
                "wait": False,
            }
        )
        self._patch_prepare(action)

        action._client.lookup_resource_id.side_effect = lambda ep, field, val, **kw: {
            ("job_templates", "name", "Demo"): 1,
            ("inventories", "name", "Prod"): 10,
            ("credentials", "name", "AWS"): 20,
            ("execution_environments", "name", "My EE"): 30,
        }.get((ep, field, val), 999)
        action._client.launch_resource.return_value = {
            "id": 42,
            "status": "pending",
            "url": "/api/controller/v2/jobs/42/",
        }

        action.run(task_vars={})

        call_payload = action._client.launch_resource.call_args.args[1]
        self.assertEqual(call_payload["inventory"], 10)
        self.assertEqual(call_payload["credentials"], [20])
        self.assertEqual(call_payload["execution_environment"], 30)

    def test_no_http_in_action_plugin(self):
        import inspect

        source = inspect.getsource(ActionModule)
        for forbidden in ("session.", "import requests", "_make_request", "_build_url"):
            self.assertNotIn(forbidden, source, f"Found '{forbidden}' in action plugin source")


if __name__ == "__main__":
    unittest.main()
