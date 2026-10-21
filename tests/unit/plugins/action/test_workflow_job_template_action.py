# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the workflow_job_template action plugin (Pattern C)."""

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.action.workflow_job_template import ActionModule


class TestWorkflowJobTemplateAssociations(unittest.TestCase):
    def _make_action(self, args, check_mode=False):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.args = dict(args)
        action._task.check_mode = check_mode
        action._display = MagicMock()
        action._client = MagicMock()
        return action

    @patch.object(BaseResourceActionPlugin, "run")
    def test_labels_association_called(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "id": 10,
            "workflow_job_template": {"id": 10, "name": "wf1"},
        }
        action = self._make_action({
            "name": "wf1",
            "state": "present",
            "labels": ["prod", "deploy"],
        })
        action._client.manage_associations.return_value = True

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.manage_associations.assert_any_call(
            "/api/controller/v2/workflow_job_templates/",
            10, "labels", ["prod", "deploy"], "labels", "name", service="controller",
        )

    @patch.object(BaseResourceActionPlugin, "run")
    def test_notification_templates_called(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": False,
            "id": 20,
            "workflow_job_template": {"id": 20, "name": "wf2"},
        }
        action = self._make_action({
            "name": "wf2",
            "state": "present",
            "notification_templates_started": ["Notify1"],
            "notification_templates_approvals": ["ApprovalNotify"],
        })
        action._client.manage_associations.return_value = True

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.manage_associations.assert_any_call(
            "/api/controller/v2/workflow_job_templates/",
            20, "notification_templates_started", ["Notify1"], "notification_templates", "name", service="controller",
        )
        action._client.manage_associations.assert_any_call(
            "/api/controller/v2/workflow_job_templates/",
            20, "notification_templates_approvals", ["ApprovalNotify"], "notification_templates", "name", service="controller",
        )

    @patch.object(BaseResourceActionPlugin, "run")
    def test_survey_spec_called(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "id": 30,
            "workflow_job_template": {"id": 30, "name": "wf3"},
        }
        survey = {"name": "test", "description": "", "spec": []}
        action = self._make_action({
            "name": "wf3",
            "state": "present",
            "survey_spec": survey,
        })
        action._client.manage_associations.return_value = False
        action._client.manage_sub_resource.return_value = True

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.manage_sub_resource.assert_called_once_with(
            "/api/controller/v2/workflow_job_templates/",
            30, "survey_spec", survey,
        )

    @patch.object(BaseResourceActionPlugin, "run")
    def test_associations_skipped_on_absent(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "workflow_job_template": {"state": "absent"},
        }
        action = self._make_action({
            "name": "wf1",
            "state": "absent",
            "labels": ["prod"],
            "survey_spec": {"name": "test"},
        })

        action.run(task_vars={})

        action._client.manage_associations.assert_not_called()
        action._client.manage_sub_resource.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_associations_skipped_on_exists(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": False,
            "exists": True,
            "id": 10,
            "workflow_job_template": {"id": 10},
        }
        action = self._make_action({
            "name": "wf1",
            "state": "exists",
            "labels": ["prod"],
        })

        action.run(task_vars={})

        action._client.manage_associations.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_no_associations_when_not_provided(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "id": 10,
            "workflow_job_template": {"id": 10, "name": "wf1"},
        }
        action = self._make_action({
            "name": "wf1",
            "state": "present",
        })

        action.run(task_vars={})

        action._client.manage_associations.assert_not_called()
        action._client.manage_sub_resource.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_fields_popped_before_super(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "id": 10,
            "workflow_job_template": {"id": 10},
        }
        action = self._make_action({
            "name": "wf1",
            "state": "present",
            "labels": ["prod"],
            "survey_spec": {"name": "test"},
            "copy_from": "source",
            "notification_templates_started": ["N1"],
        })
        action._client.manage_associations.return_value = False
        action._client.manage_sub_resource.return_value = False

        action.run(task_vars={})

        for field in ("labels", "survey_spec", "copy_from", "notification_templates_started"):
            self.assertNotIn(field, action._task.args)

    @patch.object(BaseResourceActionPlugin, "run")
    def test_failed_crud_skips_associations(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": True,
            "msg": "Not found",
        }
        action = self._make_action({
            "name": "wf1",
            "state": "present",
            "labels": ["prod"],
        })

        result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        action._client.manage_associations.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_check_mode_reports_changed_for_associations(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": False,
            "id": 10,
            "workflow_job_template": {"id": 10},
        }
        action = self._make_action(
            {"name": "wf1", "state": "present", "labels": ["prod"]},
            check_mode=True,
        )

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.manage_associations.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_check_mode_reports_changed_for_survey(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": False,
            "id": 10,
            "workflow_job_template": {"id": 10},
        }
        action = self._make_action(
            {"name": "wf1", "state": "present", "survey_spec": {"name": "s"}},
            check_mode=True,
        )

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.manage_sub_resource.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_changed_false_when_associations_unchanged(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": False,
            "id": 10,
            "workflow_job_template": {"id": 10},
        }
        action = self._make_action({
            "name": "wf1",
            "state": "present",
            "labels": ["prod"],
        })
        action._client.manage_associations.return_value = False

        result = action.run(task_vars={})

        self.assertFalse(result["changed"])

    @patch.object(BaseResourceActionPlugin, "run")
    def test_id_from_nested_result(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "workflow_job_template": {"id": 55, "name": "wf"},
        }
        action = self._make_action({
            "name": "wf",
            "state": "present",
            "labels": ["prod"],
        })
        action._client.manage_associations.return_value = True

        action.run(task_vars={})

        call = action._client.manage_associations.call_args
        self.assertEqual(call.args[1], 55)


if __name__ == "__main__":
    unittest.main()
