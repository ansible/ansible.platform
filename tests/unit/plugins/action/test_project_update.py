"""Unit tests for the project_update action plugin."""

import unittest
from unittest.mock import MagicMock, patch

from ansible.errors import AnsibleError
from ansible.playbook.task import Task
from ansible_collections.ansible.platform.plugins.action.project_update import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.project_update import CONTROLLER_PROJECTS_ENDPOINT
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
        manager.lookup_resource_id.return_value = 7
        manager.search_api.return_value = {
            "count": 2,
            "results": [
                {"id": 12, "name": "Demo Project - archived"},
                {"id": 42, "name": "Demo Project"},
            ],
        }

        project_id = _make_module()._resolve_project(manager, "Demo Project", "Engineering")

        self.assertEqual(project_id, 42)
        manager.lookup_resource_id.assert_called_once_with("organizations", "name", "Engineering", service="controller")
        manager.search_api.assert_called_once_with(
            CONTROLLER_PROJECTS_ENDPOINT,
            query_params={"name": "Demo Project", "organization": 7},
            return_all=True,
        )

    def test_ambiguous_unscoped_name_is_rejected(self):
        manager = MagicMock()
        manager.search_api.return_value = {
            "count": 2,
            "results": [
                {"id": 42, "name": "Demo Project", "organization": 7},
                {"id": 43, "name": "Demo Project", "organization": 8},
            ],
        }

        with self.assertRaisesRegex(AnsibleError, "specify organization"):
            _make_module()._resolve_project(manager, "Demo Project", None)

        manager.search_api.assert_called_once_with(CONTROLLER_PROJECTS_ENDPOINT, query_params={"name": "Demo Project"}, return_all=True)

    def test_ambiguous_scoped_name_is_rejected(self):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 7
        manager.search_api.return_value = {
            "count": 2,
            "results": [
                {"id": 42, "name": "Demo Project"},
                {"id": 43, "name": "Demo Project"},
            ],
        }

        with self.assertRaisesRegex(AnsibleError, "Multiple projects named 'Demo Project'"):
            _make_module()._resolve_project(manager, "Demo Project", "Engineering")


class TestProjectUpdateAction(unittest.TestCase):
    def _prepared(self, manager, **params):
        return {"result": {}, "validated_params": params, "manager": manager}

    @patch.object(ActionModule, "_prepare_action")
    def test_check_mode_resolves_project_without_launching(self, mock_prepare):
        module = _make_module(check_mode=True)
        manager = MagicMock()
        manager.search_api.return_value = {"results": [{"id": 42, "name": "Demo Project"}]}
        mock_prepare.return_value = self._prepared(manager, name="Demo Project", wait=True)

        result = module.run(task_vars={})

        self.assertEqual(result, {"changed": True, "failed": False, "msg": "Project update skipped (check mode)"})
        manager.search_api.assert_called_once_with(CONTROLLER_PROJECTS_ENDPOINT, query_params={"name": "Demo Project"}, return_all=True)
        manager.launch_resource.assert_not_called()

    @patch.object(ActionModule, "_prepare_action")
    def test_invalid_interval_fails_before_launch(self, mock_prepare):
        module = _make_module()
        manager = MagicMock()
        manager.search_api.return_value = {"results": [{"id": 42, "name": "Demo Project"}]}
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
                manager.search_api.side_effect = [
                    {"results": [{"id": 42, "name": "Demo Project"}]},
                    {"scm_revision": "before"},
                ]
                manager.launch_resource.return_value = {"id": 86, "url": "project_updates/86/", "status": "pending"}
                manager.wait_for_completion.return_value = {"id": 86, "status": "successful", "scm_revision": revision}
                mock_prepare.return_value = self._prepared(manager, name="Demo Project", wait=True, interval=2.0)

                result = module.run(task_vars={})

                self.assertFalse(result["failed"])
                self.assertEqual(result["changed"], expected_changed)
                self.assertEqual(result["id"], 86)
                self.assertEqual(result["status"], "successful")

    @patch.object(ActionModule, "_prepare_action")
    def test_canceled_update_is_failed(self, mock_prepare):
        module = _make_module()
        manager = MagicMock()
        manager.search_api.side_effect = [
            {"results": [{"id": 42, "name": "Demo Project"}]},
            {"scm_revision": "before"},
        ]
        manager.launch_resource.return_value = {"id": 86, "url": "project_updates/86/"}
        manager.wait_for_completion.return_value = {"id": 86, "status": "canceled", "scm_revision": "before"}
        mock_prepare.return_value = self._prepared(manager, name="Demo Project", wait=True, interval=2.0)

        result = module.run(task_vars={})

        self.assertEqual(result["status"], "canceled")
        self.assertTrue(result["failed"])

    @patch.object(ActionModule, "_prepare_action")
    def test_timeout_returns_last_job_state(self, mock_prepare):
        module = _make_module()
        manager = MagicMock()
        manager.search_api.side_effect = [
            {"results": [{"id": 42, "name": "Demo Project"}]},
            {"scm_revision": "before"},
        ]
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


if __name__ == "__main__":
    unittest.main()
