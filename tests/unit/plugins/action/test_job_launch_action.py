# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the job_launch action plugin (Shape 2)."""

import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.action.job_launch import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError


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
        action._client.search_api.return_value = {"results": [{"id": 1, "name": "Demo"}]}
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
        self.assertNotIn("finished_at", result)
        self.assertEqual(
            action._client.launch_resource.call_args.args,
            ("/api/controller/v2/job_templates/1/launch/", {}),
        )
        self.assertEqual(action._client.launch_resource.call_args.kwargs, {"service": "controller", "retry": False})
        action._client.search_api.assert_called_once_with("/api/controller/v2/job_templates/1/")
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
            "elapsed": 3.0,
            "started": "2026-11-11T10:00:00Z",
            "finished": "2026-11-11T10:00:03Z",
        }

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertFalse(result["failed"])
        self.assertEqual(result["status"], "successful")
        self.assertEqual(result["elapsed"], 3.0)
        self.assertEqual(result["started"], "2026-11-11T10:00:00Z")
        self.assertIs(result["finished"], True)
        self.assertEqual(result["finished_at"], "2026-11-11T10:00:03Z")

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
        self.assertEqual(result["job_data"], action._client.wait_for_completion.return_value)

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
        self.assertIs(result["finished"], False)
        self.assertIsNone(result["finished_at"])

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

        action._client.launch_resource.assert_called_once_with(
            "/api/controller/v2/job_templates/1/launch/",
            {"extra_vars": '{"key": "val"}'},
            service="controller",
            retry=False,
        )

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
        action._client.search_api.return_value = {"organization": None}
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

    def test_execution_environment_lookup_prefers_organization_then_falls_back_to_global(self):
        scenarios = (
            (
                [
                    {"id": 20, "name": "Shared EE", "organization": None},
                    {"id": 21, "name": "Shared EE", "organization": {"id": 9}},
                ],
                21,
            ),
            ([{"id": 20, "name": "Shared EE", "organization": None}], 20),
        )

        for environments, expected_id in scenarios:
            with self.subTest(expected_id=expected_id):
                action = self._make_action(
                    {
                        "name": "Demo",
                        "execution_environment": "Shared EE",
                        "wait": False,
                    }
                )
                self._patch_prepare(action)
                action._client.lookup_resource_id.return_value = 42
                action._client.search_api.side_effect = [{"organization": 9}, {"results": environments}]
                action._client.launch_resource.return_value = {"id": 77, "status": "pending"}

                result = action.run(task_vars={})

                self.assertFalse(result.get("failed", False))
                self.assertEqual(action._client.launch_resource.call_args.args[1]["execution_environment"], expected_id)
                self.assertEqual(
                    action._client.search_api.call_args_list[1].kwargs,
                    {
                        "query_params": {"name": "Shared EE"},
                        "return_all": True,
                        "service": "controller",
                    },
                )
                self.assertEqual(action._client.search_api.call_args_list[1].args, ("execution_environments",))
                action._client.lookup_resource_id.assert_called_once_with("job_templates", "name", "Demo", service="controller", require_unique=True)

    def test_ambiguous_scoped_execution_environments_fail_before_launch(self):
        action = self._make_action(
            {
                "name": "Demo",
                "execution_environment": "Shared EE",
                "wait": False,
            }
        )
        self._patch_prepare(action)
        action._client.lookup_resource_id.return_value = 42
        action._client.search_api.side_effect = [
            {"organization": 9},
            {
                "results": [
                    {"id": 21, "name": "Shared EE", "organization": 9},
                    {"id": 22, "name": "Shared EE", "organization": 9},
                    {"id": 20, "name": "Shared EE", "organization": None},
                ]
            },
        ]

        result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("matched multiple resources in organization 9", result["msg"])
        action._client.launch_resource.assert_not_called()

    def test_numeric_job_template_id_keeps_organization_scope_for_named_fks(self):
        action = self._make_action(
            {
                "name": "42",
                "organization": "Default",
                "inventory": "Prod",
                "credentials": ["Deploy"],
                "wait": False,
            }
        )
        self._patch_prepare(action)

        action._client.lookup_resource_id.side_effect = lambda endpoint, field, value, **kwargs: {
            ("organizations", "name", "Default"): 9,
            ("inventories", "name", "Prod"): 10,
            ("credentials", "name", "Deploy"): 20,
        }[(endpoint, field, value)]
        action._client.launch_resource.return_value = {"id": 100, "status": "pending"}

        result = action.run(task_vars={})

        self.assertFalse(result.get("failed", False))
        self.assertEqual(
            action._client.lookup_resource_id.call_args_list[1].kwargs,
            {"service": "controller", "extra_query_params": {"organization": 9}, "require_unique": True},
        )
        self.assertEqual(
            action._client.lookup_resource_id.call_args_list[2].kwargs,
            {"service": "controller", "extra_query_params": {"organization": 9}, "require_unique": True},
        )

    def test_ambiguous_credential_name_raises(self):
        """Duplicate credential names should raise instead of silently picking the first."""
        action = self._make_action(
            {
                "name": "Demo",
                "credentials": ["Ambiguous Cred"],
                "wait": False,
            }
        )
        self._patch_prepare(action)

        def _lookup(ep, field, val, **kw):
            if ep == "job_templates":
                return 1
            if ep == "credentials" and kw.get("require_unique"):
                raise ValueError("Resource 'credentials' with name=Ambiguous Cred matched multiple resources; provide additional filters")
            return 999

        action._client.lookup_resource_id.side_effect = _lookup

        result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("matched multiple", result["msg"])

    def test_ambiguous_inventory_name_raises(self):
        """Duplicate inventory names should raise instead of silently picking the first."""
        action = self._make_action(
            {
                "name": "Demo",
                "inventory": "Ambiguous Inv",
                "wait": False,
            }
        )
        self._patch_prepare(action)

        def _lookup(ep, field, val, **kw):
            if ep == "job_templates":
                return 1
            if ep == "inventories" and kw.get("require_unique"):
                raise ValueError("Resource 'inventories' with name=Ambiguous Inv matched multiple resources; provide additional filters")
            return 999

        action._client.lookup_resource_id.side_effect = _lookup

        result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("matched multiple", result["msg"])

    def test_no_http_in_action_plugin(self):
        import inspect

        source = inspect.getsource(ActionModule)
        for forbidden in ("session.", "import requests", "_make_request", "_build_url"):
            self.assertNotIn(forbidden, source, f"Found '{forbidden}' in action plugin source")


if __name__ == "__main__":
    unittest.main()
