# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for job_wait polling and return behavior."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests
from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action import job_wait
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError, WaitTimeoutError


class TestJobWaitAction(unittest.TestCase):
    def _make_action(self, params, manager):
        action = job_wait.ActionModule.__new__(job_wait.ActionModule)
        action._task = MagicMock()
        action._task.args = params
        action._display = MagicMock()
        action._display.verbosity = 0
        action._get_documentation = MagicMock(return_value="module: job_wait")
        action._build_argspec_from_docs = MagicMock(return_value={"argument_spec": {}})
        action._validate_data = MagicMock(return_value=SimpleNamespace(validated_parameters=params))
        action._get_or_spawn_manager = MagicMock(return_value=(manager, None))
        return action

    def test_timeout_uses_sdk_wait_and_reports_failure(self):
        params = {"job_id": 42, "job_type": "jobs", "interval": 5, "timeout": 2}
        manager = MagicMock()
        manager.execute.return_value = {"id": 42, "status": "running", "finished": None}
        manager.wait_for_completion.side_effect = WaitTimeoutError(
            "Timed out waiting after 2s",
            operation="wait_for_completion",
            resource="/api/controller/v2/jobs/42/",
            timeout_seconds=2,
            last_result={"id": 42, "status": "running", "finished": None},
        )
        action = self._make_action(params, manager)

        with patch.object(ActionBase, "run", return_value={}):
            result = action.run(task_vars={})

        manager.wait_for_completion.assert_called_once_with(
            resource_url="jobs/42/",
            timeout=2,
            interval=5,
            service="controller",
        )
        self.assertEqual(result["id"], 42)
        self.assertEqual(result["status"], "running")
        self.assertFalse(result["finished"])
        self.assertTrue(result["failed"])
        self.assertEqual(result["msg"], "Monitoring of job 42 aborted due to timeout.")
        self.assertFalse(result["changed"])

    def test_successful_wait_returns_finished_job(self):
        params = {"job_id": 42, "job_type": "jobs", "interval": 2, "timeout": 10}
        manager = MagicMock()
        manager.execute.return_value = {"id": 42, "status": "running", "finished": None}
        manager.wait_for_completion.return_value = {
            "id": 42,
            "status": "successful",
            "elapsed": 5.0,
            "started": "2026-10-14T12:00:00Z",
            "finished": "2026-10-14T12:00:05Z",
        }
        action = self._make_action(params, manager)

        with patch.object(ActionBase, "run", return_value={}):
            result = action.run(task_vars={})

        self.assertEqual(result["id"], 42)
        self.assertEqual(result["status"], "successful")
        self.assertTrue(result["finished"])
        self.assertEqual(result["finished_at"], "2026-10-14T12:00:05Z")
        self.assertFalse(result["failed"])
        self.assertFalse(result["changed"])

    def test_zero_timeout_passes_negative_one_to_sdk(self):
        params = {"job_id": 42, "job_type": "jobs", "interval": 0.1, "timeout": 0}
        manager = MagicMock()
        manager.execute.return_value = {"id": 42, "status": "running", "finished": None}
        manager.wait_for_completion.return_value = {
            "id": 42,
            "status": "successful",
            "finished": "2026-10-14T12:00:00Z",
        }
        action = self._make_action(params, manager)

        with patch.object(ActionBase, "run", return_value={}):
            result = action.run(task_vars={})

        manager.wait_for_completion.assert_called_once_with(
            resource_url="jobs/42/",
            timeout=-1,
            interval=0.1,
            service="controller",
        )
        self.assertFalse(result["failed"])

    def test_none_timeout_passes_negative_one_to_sdk(self):
        params = {"job_id": 42, "job_type": "jobs", "interval": 2}
        manager = MagicMock()
        manager.execute.return_value = {"id": 42, "status": "running", "finished": None}
        manager.wait_for_completion.return_value = {
            "id": 42,
            "status": "successful",
            "finished": "2026-10-14T12:00:00Z",
        }
        action = self._make_action(params, manager)

        with patch.object(ActionBase, "run", return_value={}):
            result = action.run(task_vars={})

        manager.wait_for_completion.assert_called_once_with(
            resource_url="jobs/42/",
            timeout=-1,
            interval=2,
            service="controller",
        )
        self.assertFalse(result["failed"])

    def test_canceled_job_reports_failure(self):
        params = {"job_id": 42, "job_type": "jobs", "interval": 2, "timeout": 10}
        manager = MagicMock()
        manager.execute.return_value = {"id": 42, "status": "pending", "finished": None}
        manager.wait_for_completion.return_value = {"id": 42, "status": "canceled", "finished": "2026-10-14T12:00:00Z"}
        action = self._make_action(params, manager)

        with patch.object(ActionBase, "run", return_value={}):
            result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertEqual(result["msg"], "Job 42 was canceled.")

    def test_failed_job_reports_status(self):
        params = {"job_id": 42, "job_type": "jobs", "interval": 2, "timeout": 10}
        manager = MagicMock()
        manager.execute.return_value = {"id": 42, "status": "pending", "finished": None}
        manager.wait_for_completion.return_value = {"id": 42, "status": "error", "finished": "2026-10-14T12:00:00Z"}
        action = self._make_action(params, manager)

        with patch.object(ActionBase, "run", return_value={}):
            result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertEqual(result["msg"], "Job 42 finished with status 'error'.")

    def test_http_404_reports_missing_job_for_structured_and_raw_errors(self):
        params = {"job_id": 404, "job_type": "jobs", "interval": 1, "timeout": 10}
        response = requests.Response()
        response.status_code = 404
        errors = (
            APIError("request failed", status_code=404),
            requests.exceptions.HTTPError("404 Client Error", response=response),
        )

        for error in errors:
            with self.subTest(error_type=type(error).__name__):
                manager = MagicMock()
                manager.execute.side_effect = error
                action = self._make_action(params, manager)

                with patch.object(ActionBase, "run", return_value={}):
                    result = action.run(task_vars={})

                self.assertEqual(
                    result,
                    {
                        "failed": True,
                        "changed": False,
                        "msg": "Unable to wait, no job 404 found: The requested object could not be found.",
                    },
                )

    def test_nonpositive_interval_is_rejected(self):
        params = {"job_id": 42, "job_type": "jobs", "interval": 0, "timeout": 10}
        action = self._make_action(params, MagicMock())

        with patch.object(ActionBase, "run", return_value={}):
            result = action.run(task_vars={})

        self.assertEqual(result, {"failed": True, "msg": "interval must be greater than 0"})

    def test_workflow_job_type_uses_correct_endpoint(self):
        params = {"job_id": 99, "job_type": "workflow_jobs", "interval": 2, "timeout": 10}
        manager = MagicMock()
        manager.execute.return_value = {"id": 99, "status": "running", "finished": None}
        manager.wait_for_completion.return_value = {"id": 99, "status": "successful", "finished": "2026-10-14T12:00:00Z"}
        action = self._make_action(params, manager)

        with patch.object(ActionBase, "run", return_value={}):
            result = action.run(task_vars={})

        manager.wait_for_completion.assert_called_once_with(
            resource_url="workflow_jobs/99/",
            timeout=10,
            interval=2,
            service="controller",
        )
        self.assertFalse(result["failed"])


if __name__ == "__main__":
    unittest.main()
