# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the workflow_job_template action plugin (Pattern C)."""

import unittest
from unittest.mock import MagicMock, patch

import pytest
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.action.workflow_job_template import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import ResourceNotFoundError


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
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "labels": ["prod", "deploy"],
            }
        )
        action._client.manage_associations.return_value = True

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.manage_associations.assert_any_call(
            "/api/controller/v2/workflow_job_templates/",
            10,
            "labels",
            ["prod", "deploy"],
            "labels",
            "name",
            service="controller",
            extra_query_params=None,
            check_mode=False,
        )

    @patch.object(BaseResourceActionPlugin, "run")
    def test_labels_scoped_by_organization(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "id": 10,
            "organization": 42,
            "workflow_job_template": {"id": 10, "name": "wf1"},
        }
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "labels": ["prod"],
            }
        )
        action._client.manage_associations.return_value = True

        action.run(task_vars={})

        action._client.manage_associations.assert_any_call(
            "/api/controller/v2/workflow_job_templates/",
            10,
            "labels",
            ["prod"],
            "labels",
            "name",
            service="controller",
            extra_query_params={"organization": 42},
            check_mode=False,
        )

    @patch.object(BaseResourceActionPlugin, "run")
    def test_notification_templates_called(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": False,
            "id": 20,
            "workflow_job_template": {"id": 20, "name": "wf2"},
        }
        action = self._make_action(
            {
                "name": "wf2",
                "state": "present",
                "notification_templates_started": ["Notify1"],
                "notification_templates_approvals": ["ApprovalNotify"],
            }
        )
        action._client.manage_associations.return_value = True

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.manage_associations.assert_any_call(
            "/api/controller/v2/workflow_job_templates/",
            20,
            "notification_templates_started",
            ["Notify1"],
            "notification_templates",
            "name",
            service="controller",
            extra_query_params=None,
            check_mode=False,
        )
        action._client.manage_associations.assert_any_call(
            "/api/controller/v2/workflow_job_templates/",
            20,
            "notification_templates_approvals",
            ["ApprovalNotify"],
            "notification_templates",
            "name",
            service="controller",
            extra_query_params=None,
            check_mode=False,
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
        action = self._make_action(
            {
                "name": "wf3",
                "state": "present",
                "survey_spec": survey,
            }
        )
        action._client.manage_associations.return_value = False
        action._client.manage_sub_resource.return_value = True

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.manage_sub_resource.assert_called_once_with(
            "/api/controller/v2/workflow_job_templates/",
            30,
            "survey_spec",
            survey,
            check_mode=False,
        )

    @patch.object(BaseResourceActionPlugin, "run")
    def test_associations_skipped_on_absent(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "workflow_job_template": {"state": "absent"},
        }
        action = self._make_action(
            {
                "name": "wf1",
                "state": "absent",
                "labels": ["prod"],
                "survey_spec": {"name": "test"},
            }
        )

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
        action = self._make_action(
            {
                "name": "wf1",
                "state": "exists",
                "labels": ["prod"],
            }
        )

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
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
            }
        )

        action.run(task_vars={})

        action._client.manage_associations.assert_not_called()
        action._client.manage_sub_resource.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_control_and_association_arguments_are_preserved(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": True,
            "failed": False,
            "id": 10,
            "workflow_job_template": {"id": 10},
        }
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "labels": ["prod"],
                "survey_spec": {"name": "test"},
                "copy_from": "source",
                "notification_templates_started": ["N1"],
            }
        )
        action._client.manage_associations.return_value = False
        action._client.manage_sub_resource.return_value = False

        action.run(task_vars={})

        for field in ("labels", "survey_spec", "copy_from", "notification_templates_started"):
            self.assertIn(field, action._task.args)

    @patch.object(BaseResourceActionPlugin, "run")
    def test_failed_crud_skips_associations(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": True,
            "msg": "Not found",
        }
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "labels": ["prod"],
            }
        )

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
        action._client.manage_associations.assert_called_once()
        self.assertTrue(action._client.manage_associations.call_args.kwargs["check_mode"])

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
        action._client.manage_sub_resource.assert_called_once()
        self.assertTrue(action._client.manage_sub_resource.call_args.kwargs["check_mode"])

    @patch.object(BaseResourceActionPlugin, "run")
    def test_changed_false_when_associations_unchanged(self, mock_super_run):
        mock_super_run.return_value = {
            "changed": False,
            "failed": False,
            "id": 10,
            "workflow_job_template": {"id": 10},
        }
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "labels": ["prod"],
            }
        )
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
        action = self._make_action(
            {
                "name": "wf",
                "state": "present",
                "labels": ["prod"],
            }
        )
        action._client.manage_associations.return_value = True

        action.run(task_vars={})

        call = action._client.manage_associations.call_args
        self.assertEqual(call.args[1], 55)


@pytest.fixture
def action_module():
    """Create a workflow template action with real argument validation."""
    action = ActionModule.__new__(ActionModule)
    action._task = MagicMock(args={"name": "Resource"}, check_mode=False)
    action._display = MagicMock()
    action._display.verbosity = 0
    action._client = MagicMock()
    return action


@pytest.mark.parametrize("changed", [False, True])
@pytest.mark.parametrize("field,alias", [("labels", "labels"), ("survey_spec", "survey_spec"), ("survey_spec", "survey")])
def test_workflow_template_dry_run_compares_associations_and_survey(action_module, field, alias, changed):
    """Preserve survey aliases and compare current values instead of assuming change."""
    desired = ["Existing"] if field == "labels" else {"name": "Survey", "description": "", "spec": []}
    action = action_module
    action._task.args[alias] = desired
    action._task.check_mode = True
    action._client.manage_associations.return_value = changed
    action._client.manage_sub_resource.return_value = changed
    with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "id": 7}):
        result = action.run(task_vars={})
    assert result["changed"] is changed
    method = action._client.manage_associations if field == "labels" else action._client.manage_sub_resource
    assert method.call_args.kwargs["check_mode"] is True
    assert method.call_args.args[3] == desired


@pytest.mark.parametrize("missing,check_mode", [(True, True), (True, False), (False, True)])
def test_workflow_template_only_predicts_expected_missing_associations(action_module, missing, check_mode):
    """Predict a dependency created earlier in check mode while propagating real errors."""
    action = action_module
    action._task.args["labels"] = ["New Label"]
    action._task.check_mode = check_mode
    error = (
        ResourceNotFoundError("No matching label", endpoint="labels", lookup_field="name", lookup_value="New Label", service="controller")
        if missing
        else ValueError("Resource 'labels' with name=New Label not found")
    )
    action._client.manage_associations.side_effect = error
    with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "id": 7}):
        result = action.run(task_vars={})
    assert {"failed": result.get("failed", False), "changed": result["changed"]} == {
        "failed": not (missing and check_mode),
        "changed": missing and check_mode,
    }


if __name__ == "__main__":
    unittest.main()
