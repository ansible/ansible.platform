# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for job_wait timeout and polling behavior."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action import job_wait


class TestJobWaitTimeout(unittest.TestCase):
    def _make_action(self, params, manager):
        action = job_wait.ActionModule.__new__(job_wait.ActionModule)
        action._task = MagicMock()
        action._task.args = params
        action._display = MagicMock()
        action._get_documentation = MagicMock(return_value="module: job_wait")
        action._build_argspec_from_docs = MagicMock(return_value={"argument_spec": {}})
        action._validate_data = MagicMock(return_value=SimpleNamespace(validated_parameters=params))
        action._get_or_spawn_manager = MagicMock(return_value=(manager, None))
        return action

    def test_sleep_is_capped_at_timeout_and_no_poll_occurs_after_expiry(self):
        params = {"job_id": 42, "job_type": "jobs", "interval": 5, "timeout": 2}
        manager = MagicMock()
        manager.execute.return_value = {"id": 42, "status": "running", "finished": None}
        action = self._make_action(params, manager)

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(job_wait.time, "monotonic", side_effect=[0.0, 0.0, 2.0]):
                with patch.object(job_wait.time, "sleep") as sleep:
                    result = action.run(task_vars={})

        sleep.assert_called_once_with(2)
        manager.execute.assert_called_once()
        self.assertTrue(result["failed"])
        self.assertEqual(result["status"], "running")
        self.assertEqual(result["msg"], "Monitoring of job 42 aborted due to timeout.")

    def test_polls_after_interval_when_timeout_has_not_expired(self):
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
        self.assertTrue(result["changed"])
        self.assertFalse(result["failed"])


if __name__ == "__main__":
    unittest.main()
