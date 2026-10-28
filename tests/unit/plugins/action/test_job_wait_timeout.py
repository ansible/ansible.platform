# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for job_wait polling and return behavior."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests
from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action import job_wait
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError


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

    def test_timeout_caps_sleep_and_does_not_poll_after_deadline(self):
        params = {"job_id": 42, "job_type": "jobs", "interval": 5, "timeout": 2}
        manager = MagicMock()
        manager.execute.return_value = {"id": 42, "status": "running", "finished": None}
        action = self._make_action(params, manager)

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(job_wait.time, "monotonic", side_effect=[0.0, 0.0, 2.0]):
                with patch.object(job_wait.time, "sleep") as sleep:
                    result = action.run(task_vars={})

        sleep.assert_called_once_with(2)
        manager.execute.assert_called_once_with(
            operation="find",
            module_name="job_wait",
            ansible_data={"job_id": 42, "job_type": "jobs"},
        )
        self.assertEqual(
            result,
            {
                "id": 42,
                "status": "running",
                "elapsed": None,
                "started": None,
                "finished": False,
                "finished_at": None,
                "changed": False,
                "failed": True,
                "msg": "Monitoring of job 42 aborted due to timeout.",
            },
        )

    def test_polls_again_before_timeout_and_keeps_finished_timestamp(self):
        params = {"job_id": 42, "job_type": "jobs", "interval": 2, "timeout": 10}
        manager = MagicMock()
        manager.execute.side_effect = [
            {"id": 42, "status": "running", "finished": None},
            {"id": 42, "status": "successful", "finished": "2026-10-14T12:00:00Z"},
        ]
        action = self._make_action(params, manager)

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(job_wait.time, "monotonic", side_effect=[0.0, 0.0, 2.0]):
                with patch.object(job_wait.time, "sleep") as sleep:
                    result = action.run(task_vars={})

        sleep.assert_called_once_with(2)
        self.assertEqual(manager.execute.call_count, 2)
        self.assertEqual(
            result,
            {
                "id": 42,
                "status": "successful",
                "elapsed": None,
                "started": None,
                "finished": True,
                "finished_at": "2026-10-14T12:00:00Z",
                "changed": False,
                "failed": False,
            },
        )

    def test_zero_timeout_waits_indefinitely(self):
        params = {"job_id": 42, "job_type": "jobs", "interval": 0.1, "timeout": 0}
        manager = MagicMock()
        manager.execute.side_effect = [
            {"id": 42, "status": "running", "finished": None},
            {"id": 42, "status": "successful", "finished": "2026-10-14T12:00:00Z"},
        ]
        action = self._make_action(params, manager)

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(job_wait.time, "monotonic", return_value=0.0):
                with patch.object(job_wait.time, "sleep") as sleep:
                    result = action.run(task_vars={})

        sleep.assert_called_once_with(0.1)
        self.assertEqual(manager.execute.call_count, 2)
        self.assertFalse(result["failed"])

    def test_initial_lookup_time_counts_toward_timeout(self):
        params = {"job_id": 42, "job_type": "jobs", "interval": 2, "timeout": 1}
        manager = MagicMock()
        manager.execute.return_value = {"id": 42, "status": "running", "finished": None}
        action = self._make_action(params, manager)

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(job_wait.time, "monotonic", side_effect=[0.0, 1.0]):
                with patch.object(job_wait.time, "sleep") as sleep:
                    result = action.run(task_vars={})

        sleep.assert_not_called()
        manager.execute.assert_called_once()
        self.assertTrue(result["failed"])

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


if __name__ == "__main__":
    unittest.main()
