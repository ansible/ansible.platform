"""Unit tests for the project_update action plugin."""

import unittest
from unittest.mock import MagicMock, patch

from ansible.errors import AnsibleError
from ansible.playbook.task import Task
from ansible_collections.ansible.platform.plugins.action.project_update import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError


def _make_module(check_mode=False):
    task = MagicMock(spec=Task)
    task.args = {}
    task.check_mode = check_mode
    task.async_val = 0
    task.environment = {}
    module = ActionModule(
        task=task,
        connection=MagicMock(),
        play_context=MagicMock(),
        loader=MagicMock(),
        templar=MagicMock(),
        shared_loader_obj=MagicMock(),
    )
    module._display = MagicMock()
    module._display.verbosity = 0
    return module


class TestProjectResolution(unittest.TestCase):
    def test_numeric_project_id_does_not_search(self):
        manager = MagicMock()

        project_id = _make_module()._resolve_project(manager, "42", "Engineering")

        self.assertEqual(project_id, 42)
        manager.search_api.assert_not_called()
        manager.lookup_resource_id.assert_not_called()

    def test_scoped_lookup_filters_exact_name_and_organization(self):
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = [7, 42]

        project_id = _make_module()._resolve_project(manager, "Demo Project", "Engineering")

        self.assertEqual(project_id, 42)
        self.assertEqual(
            manager.lookup_resource_id.call_args_list,
            [
                unittest.mock.call("organizations", "name", "Engineering", service="controller"),
                unittest.mock.call(
                    "projects",
                    "name",
                    "Demo Project",
                    service="controller",
                    require_unique=True,
                    extra_query_params={"organization": 7},
                ),
            ],
        )

    def test_ambiguous_unscoped_name_is_rejected(self):
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = ValueError("Resource 'projects' with name=Demo Project matched multiple resources")

        with self.assertRaisesRegex(AnsibleError, "matched multiple resources"):
            _make_module()._resolve_project(manager, "Demo Project", None)

        manager.lookup_resource_id.assert_called_once_with("projects", "name", "Demo Project", service="controller", require_unique=True)

    def test_ambiguous_scoped_name_is_rejected(self):
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = [7, ValueError("Resource 'projects' with name=Demo Project matched multiple resources")]

        with self.assertRaisesRegex(AnsibleError, "matched multiple resources"):
            _make_module()._resolve_project(manager, "Demo Project", "Engineering")


class TestProjectUpdateAction(unittest.TestCase):
    def _prepared(self, manager, **params):
        return {"result": {}, "validated_params": params, "manager": manager}

    @patch.object(ActionModule, "_prepare_action")
    def test_check_mode_resolves_project_without_launching(self, mock_prepare):
        module = _make_module(check_mode=True)
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 42
        mock_prepare.return_value = self._prepared(manager, name="Demo Project", wait=True)

        result = module.run(task_vars={})

        self.assertEqual(result, {"changed": True, "failed": False, "msg": "Project update skipped (check mode)"})
        manager.lookup_resource_id.assert_called_once_with("projects", "name", "Demo Project", service="controller", require_unique=True)
        manager.search_api.assert_not_called()
        manager.launch_resource.assert_not_called()

    @patch.object(ActionModule, "_prepare_action")
    def test_invalid_interval_fails_before_launch(self, mock_prepare):
        module = _make_module()
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 42
        mock_prepare.return_value = self._prepared(manager, name="Demo Project", wait=True, interval=0)

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertFalse(result["changed"])
        self.assertIn("Polling interval must be positive", result["msg"])
        manager.launch_resource.assert_not_called()

    @patch.object(ActionModule, "_prepare_action")
    def test_changed_tracks_scm_revision(self, mock_prepare):
        for revision, expected_changed in (("before", False), ("after", True)):
            with self.subTest(revision=revision):
                module = _make_module()
                manager = MagicMock()
                manager.lookup_resource_id.return_value = 42
                manager.search_api.return_value = {"scm_revision": "before"}
                manager.launch_resource.return_value = {"id": 86, "url": "project_updates/86/", "status": "pending"}
                manager.wait_for_completion.return_value = {
                    "id": 86,
                    "status": "successful",
                    "scm_revision": revision,
                    "elapsed": 3.0,
                    "started": "2026-11-11T10:00:00Z",
                    "finished": "2026-11-11T10:00:03Z",
                }
                mock_prepare.return_value = self._prepared(manager, name="Demo Project", wait=True, interval=2.0)

                result = module.run(task_vars={})

                self.assertFalse(result["failed"])
                self.assertEqual(result["changed"], expected_changed)
                self.assertEqual(result["id"], 86)
                self.assertEqual(result["status"], "successful")
                self.assertEqual(result["elapsed"], 3.0)
                self.assertEqual(result["started"], "2026-11-11T10:00:00Z")
                self.assertIs(result["finished"], True)
                self.assertEqual(result["finished_at"], "2026-11-11T10:00:03Z")
                manager.search_api.assert_called_once_with("/api/controller/v2/projects/42/")
                manager.launch_resource.assert_called_once_with(
                    "/api/controller/v2/projects/42/update/",
                    {},
                    service="controller",
                )

    @patch.object(ActionModule, "_prepare_action")
    def test_negative_timeout_fails_before_api_calls(self, mock_prepare):
        for check_mode in (False, True):
            for wait in (False, True):
                for timeout in (-1, -5):
                    with self.subTest(check_mode=check_mode, wait=wait, timeout=timeout):
                        manager = MagicMock()
                        mock_prepare.return_value = self._prepared(manager, name="Demo Project", wait=wait, timeout=timeout)

                        result = _make_module(check_mode=check_mode).run(task_vars={})

                        self.assertEqual(result, {"changed": False, "failed": True, "msg": "timeout must be 0 or greater"})
                        manager.lookup_resource_id.assert_not_called()
                        manager.search_api.assert_not_called()
                        manager.launch_resource.assert_not_called()
                        manager.wait_for_completion.assert_not_called()

    @patch.object(ActionModule, "_prepare_action")
    def test_wait_maps_unlimited_and_explicit_timeouts(self, mock_prepare):
        for timeout, expected in ((None, -1.0), (0, -1.0), (30, 30.0)):
            with self.subTest(timeout=timeout):
                manager = MagicMock()
                manager.lookup_resource_id.return_value = 42
                manager.search_api.return_value = {"scm_revision": "before"}
                manager.launch_resource.return_value = {"id": 86}
                manager.wait_for_completion.return_value = {"id": 86, "status": "successful", "scm_revision": "before"}
                mock_prepare.return_value = self._prepared(manager, name="Demo Project", timeout=timeout)

                result = _make_module().run(task_vars={})

                self.assertFalse(result["failed"])
                self.assertEqual(manager.wait_for_completion.call_args.kwargs["timeout"], expected)
                self.assertIsInstance(manager.wait_for_completion.call_args.kwargs["timeout"], float)

    @patch.object(ActionModule, "_prepare_action")
    def test_canceled_update_is_failed(self, mock_prepare):
        module = _make_module()
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 42
        manager.search_api.return_value = {"scm_revision": "before"}
        manager.launch_resource.return_value = {"id": 86, "url": "project_updates/86/"}
        manager.wait_for_completion.return_value = {"id": 86, "status": "canceled", "scm_revision": "before"}
        mock_prepare.return_value = self._prepared(manager, name="Demo Project", wait=True, interval=2.0)

        result = module.run(task_vars={})

        self.assertEqual(result["status"], "canceled")
        self.assertTrue(result["failed"])
        self.assertEqual(result["job_data"], manager.wait_for_completion.return_value)

    @patch.object(ActionModule, "_prepare_action")
    def test_timeout_returns_last_job_state(self, mock_prepare):
        module = _make_module()
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 42
        manager.search_api.return_value = {"scm_revision": "before"}
        manager.launch_resource.return_value = {"id": 86, "url": "project_updates/86/"}
        manager.wait_for_completion.side_effect = WaitTimeoutError(
            "Timed out waiting for project update",
            last_result={"id": 86, "status": "running"},
        )
        mock_prepare.return_value = self._prepared(manager, name="Demo Project", wait=True, interval=2.0, timeout=1)

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertTrue(result["changed"])
        self.assertEqual(result["id"], 86)
        self.assertEqual(result["status"], "running")
        self.assertIs(result["finished"], False)


if __name__ == "__main__":
    unittest.main()
