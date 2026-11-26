# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the workflow_job_template action plugin (Pattern C)."""

import unittest
from unittest.mock import MagicMock, patch
from unittest.mock import call as mock_call

import pytest
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.action.workflow_job_template import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import ResourceNotFoundError


@pytest.mark.parametrize(
    ("endpoint", "reference", "scope"),
    [
        ("inventories", {"name": "42", "organization": {"name": "Production"}}, {"organization": 8}),
        ("execution_environments", {"name": "Runner", "organization": {"name": "Production"}}, {"organization": 8}),
        ("execution_environments", {"name": "Global EE", "organization": None}, {"organization__isnull": True}),
    ],
)
def test_resolve_portable_workflow_prompt_uses_source_scope(endpoint, reference, scope):
    manager = MagicMock()
    manager.lookup_resource_id.side_effect = lambda resource, *args, **kwargs: 8 if resource == "organizations" else 90

    assert ActionModule._resolve_prompt_id(manager, endpoint, reference) == 90
    manager.lookup_resource_id.assert_called_with(endpoint, "name", reference["name"], service="controller", extra_query_params=scope, numeric_is_id=False)


def test_resolve_inventory_source_uses_parent_inventory():
    manager = MagicMock()
    manager.lookup_resource_id.side_effect = [8, 90, 123]
    target = {
        "type": "inventory_source",
        "name": "42",
        "inventory": {"name": "Hosts", "organization": {"name": "17"}},
    }

    assert ActionModule._resolve_ujt_id(manager, target) == 123
    assert manager.lookup_resource_id.call_args_list == [
        mock_call("organizations", "name", "17", service="controller", numeric_is_id=False),
        mock_call("inventories", "name", "Hosts", service="controller", extra_query_params={"organization": 8}, numeric_is_id=False),
        mock_call("inventory_sources", "name", "42", service="controller", extra_query_params={"inventory": 90}, numeric_is_id=False),
    ]


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


class TestWorkflowNodesGraph(unittest.TestCase):
    """Unit tests for workflow_nodes / destroy_current_nodes graph management."""

    def _make_action(self, args, check_mode=False):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.args = dict(args)
        action._task.check_mode = check_mode
        action._display = MagicMock()
        action._client = MagicMock()
        return action

    @patch.object(BaseResourceActionPlugin, "run")
    def test_destroy_current_nodes(self, mock_super_run):
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action({"name": "wf1", "state": "present", "destroy_current_nodes": True})
        action._client.search_api.return_value = {"results": [{"id": 100, "identifier": "n1"}, {"id": 101, "identifier": "n2"}]}
        action._client.manage_associations.return_value = False
        action._client.manage_sub_resource.return_value = False

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertEqual(action._client.direct_request.call_count, 2)
        action._client.direct_request.assert_any_call("DELETE", "/api/controller/v2/workflow_job_template_nodes/100/")
        action._client.direct_request.assert_any_call("DELETE", "/api/controller/v2/workflow_job_template_nodes/101/")

    @patch.object(BaseResourceActionPlugin, "run")
    def test_destroy_no_existing_nodes(self, mock_super_run):
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action({"name": "wf1", "state": "present", "destroy_current_nodes": True})
        action._client.search_api.return_value = {"results": []}

        result = action.run(task_vars={})

        self.assertFalse(result["changed"])
        action._client.direct_request.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_workflow_nodes_create(self, mock_super_run):
        mock_super_run.return_value = {"changed": True, "failed": False, "id": 10}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "workflow_nodes": [
                    {
                        "identifier": "node1",
                        "unified_job_template": {"name": "Demo JT", "type": "job_template", "organization": {"name": "Default"}},
                    },
                ],
            }
        )
        # _find_node_in_workflow returns None (node doesn't exist yet)
        action._client.search_api.return_value = {"results": []}
        action._client.lookup_resource_id.side_effect = lambda ep, field, val, **kw: {
            ("organizations", "name", "Default"): 1,
            ("unified_job_templates", "name", "Demo JT"): 42,
        }.get((ep, field, val), None)

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.post_resource.assert_called_once()
        call_args = action._client.post_resource.call_args
        self.assertEqual(call_args[0][0], "/api/controller/v2/workflow_job_template_nodes/")
        payload = call_args[0][1]
        self.assertEqual(payload["identifier"], "node1")
        self.assertEqual(payload["workflow_job_template"], 10)
        self.assertEqual(payload["unified_job_template"], 42)

    @patch.object(BaseResourceActionPlugin, "run")
    def test_workflow_nodes_absent_state(self, mock_super_run):
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "workflow_nodes": [
                    {"identifier": "old_node", "state": "absent"},
                ],
            }
        )
        action._client.search_api.return_value = {"results": [{"id": 99, "identifier": "old_node"}]}

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.direct_request.assert_called_once_with("DELETE", "/api/controller/v2/workflow_job_template_nodes/99/")

    @patch.object(BaseResourceActionPlugin, "run")
    def test_workflow_nodes_check_mode(self, mock_super_run):
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "workflow_nodes": [
                    {"identifier": "new_node", "unified_job_template": {"name": "JT", "type": "job_template"}},
                ],
            },
            check_mode=True,
        )
        action._client.search_api.return_value = {"results": []}
        action._client.lookup_resource_id.return_value = 42

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.post_resource.assert_not_called()
        action._client.direct_request.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_workflow_nodes_associations(self, mock_super_run):
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "workflow_nodes": [
                    {
                        "identifier": "node1",
                        "unified_job_template": {"name": "JT", "type": "job_template"},
                        "related": {
                            "success_nodes": [{"identifier": "node2"}],
                            "credentials": [{"name": "my_cred"}],
                        },
                    },
                    {
                        "identifier": "node2",
                        "unified_job_template": {"name": "JT2", "type": "job_template"},
                    },
                ],
            }
        )

        node1_data = {"id": 50, "identifier": "node1"}
        node2_data = {"id": 51, "identifier": "node2"}

        def search_side_effect(path, query_params=None, **kwargs):
            if query_params and query_params.get("identifier") == "node1":
                return {"results": [node1_data]}
            if query_params and query_params.get("identifier") == "node2":
                return {"results": [node2_data]}
            return {"results": []}

        action._client.search_api.side_effect = search_side_effect
        action._client.lookup_resource_id.return_value = 42
        action._client.manage_associations.return_value = True

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        # Verify success_nodes association was called with resolved IDs
        success_call = None
        for call in action._client.manage_associations.call_args_list:
            if call[0][2] == "success_nodes":
                success_call = call
                break
        self.assertIsNotNone(success_call)
        self.assertEqual(success_call[0][1], 50)  # node_id
        self.assertEqual(success_call[0][3], [51])  # target_ids

    @patch.object(BaseResourceActionPlugin, "run")
    def test_workflow_nodes_approval(self, mock_super_run):
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "workflow_nodes": [
                    {
                        "identifier": "approval1",
                        "unified_job_template": {
                            "name": "Approve Deploy",
                            "type": "workflow_approval",
                            "timeout": 900,
                        },
                    },
                ],
            }
        )
        approval_node = {"id": 70, "identifier": "approval1"}
        action._client.search_api.return_value = {"results": [approval_node]}
        action._client.manage_workflow_approval.return_value = True
        # post_resource for creating the node (first call returns empty, second returns node)
        call_count = {"n": 0}

        def search_side_effect(path, query_params=None, **kwargs):
            if query_params and query_params.get("identifier") == "approval1":
                call_count["n"] += 1
                if call_count["n"] == 1:
                    return {"results": []}  # First lookup: doesn't exist
                return {"results": [approval_node]}  # After creation
            return {"results": []}

        action._client.search_api.side_effect = search_side_effect

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.manage_workflow_approval.assert_called_once_with(70, {"name": "Approve Deploy", "timeout": 900}, check_mode=False)

    @patch.object(BaseResourceActionPlugin, "run")
    def test_workflow_nodes_skipped_on_absent(self, mock_super_run):
        mock_super_run.return_value = {"changed": True, "failed": False}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "absent",
                "workflow_nodes": [{"identifier": "n1"}],
                "destroy_current_nodes": True,
            }
        )

        action.run(task_vars={})

        action._client.search_api.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_schema_alias(self, mock_super_run):
        """The 'schema' alias resolves to workflow_nodes."""
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "schema": [{"identifier": "n1", "unified_job_template": {"name": "JT", "type": "job_template"}}],
            }
        )
        action._client.search_api.return_value = {"results": []}
        action._client.lookup_resource_id.return_value = 42

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.post_resource.assert_called_once()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_missing_ujt_raises(self, mock_super_run):
        """Nodes without unified_job_template are rejected."""
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "workflow_nodes": [{"identifier": "bad_node"}],
            }
        )

        result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("requires 'unified_job_template'", result["msg"])

    @patch.object(BaseResourceActionPlugin, "run")
    def test_missing_ujt_name_raises(self, mock_super_run):
        """Nodes with UJT missing name are rejected."""
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "workflow_nodes": [
                    {"identifier": "bad", "unified_job_template": {"type": "job_template"}},
                ],
            }
        )

        result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("requires 'name'", result["msg"])

    @patch.object(BaseResourceActionPlugin, "run")
    def test_missing_ujt_type_raises(self, mock_super_run):
        """Regular nodes with UJT missing type are rejected."""
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "workflow_nodes": [
                    {"identifier": "bad", "unified_job_template": {"name": "JT"}},
                ],
            }
        )

        result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("requires 'type'", result["msg"])

    @patch.object(BaseResourceActionPlugin, "run")
    def test_approval_conversion_clears_ujt(self, mock_super_run):
        """Converting a regular node to approval clears unified_job_template."""
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "workflow_nodes": [
                    {
                        "identifier": "convert_me",
                        "unified_job_template": {"name": "Approval", "type": "workflow_approval", "timeout": 300},
                    },
                ],
            }
        )
        existing_node = {"id": 80, "identifier": "convert_me", "unified_job_template": 42}

        def search_side_effect(path, query_params=None, **kwargs):
            if query_params and query_params.get("identifier") == "convert_me":
                return {"results": [existing_node]}
            return {"results": []}

        action._client.search_api.side_effect = search_side_effect
        action._client.is_workflow_approval_template.return_value = False
        action._client.manage_workflow_approval.return_value = True

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        patch_call = action._client.direct_request.call_args
        self.assertIsNotNone(patch_call)
        payload = patch_call[0][2]
        self.assertIsNone(payload.get("unified_job_template"))

    @patch.object(BaseResourceActionPlugin, "run")
    def test_approval_reapply_keeps_template(self, mock_super_run):
        """Reapplying an approval node with existing approval template does not clear UJT."""
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "workflow_nodes": [
                    {
                        "identifier": "approval1",
                        "unified_job_template": {"name": "Approve", "type": "workflow_approval", "timeout": 600},
                    },
                ],
            }
        )
        existing_node = {"id": 80, "identifier": "approval1", "unified_job_template": 55}

        def search_side_effect(path, query_params=None, **kwargs):
            if query_params and query_params.get("identifier") == "approval1":
                return {"results": [existing_node]}
            return {"results": []}

        action._client.search_api.side_effect = search_side_effect
        action._client.is_workflow_approval_template.return_value = True
        action._client.manage_workflow_approval.return_value = False

        result = action.run(task_vars={})

        self.assertFalse(result.get("failed", False))
        # UJT should NOT have been cleared — no PATCH with None
        for call in action._client.direct_request.call_args_list:
            if call[0][0] == "PATCH" and len(call[0]) > 2:
                self.assertNotIn("unified_job_template", call[0][2])

    @patch.object(BaseResourceActionPlugin, "run")
    def test_org_scoped_credential_association(self, mock_super_run):
        """Credentials with organization context are resolved with org filter."""
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "workflow_nodes": [
                    {
                        "identifier": "n1",
                        "unified_job_template": {"name": "JT", "type": "job_template"},
                        "related": {
                            "credentials": [
                                {"name": "my_cred", "organization": {"name": "OrgA"}},
                            ],
                        },
                    },
                ],
            }
        )
        node_data = {"id": 50, "identifier": "n1"}

        def search_side_effect(path, query_params=None, **kwargs):
            if query_params and query_params.get("identifier") == "n1":
                return {"results": [node_data]}
            return {"results": []}

        action._client.search_api.side_effect = search_side_effect
        action._client.lookup_resource_id.side_effect = lambda ep, field, val, **kw: {
            ("organizations", "name", "OrgA"): 5,
            ("unified_job_templates", "name", "JT"): 42,
            ("credentials", "name", "my_cred"): 99,
        }.get((ep, field, val), None)
        action._client.manage_associations.return_value = False

        action.run(task_vars={})

        # Verify credential resolved with org filter
        cred_lookup = [c for c in action._client.lookup_resource_id.call_args_list if c[0][0] == "credentials"]
        self.assertEqual(len(cred_lookup), 1)
        self.assertEqual(cred_lookup[0].kwargs.get("extra_query_params"), {"organization": 5})

        # Verify manage_associations called with resolved ID
        cred_assoc = [c for c in action._client.manage_associations.call_args_list if c[0][2] == "credentials"]
        self.assertEqual(len(cred_assoc), 1)
        self.assertEqual(cred_assoc[0][0][3], [99])

    @patch.object(BaseResourceActionPlugin, "run")
    def test_destroy_current_schema_alias(self, mock_super_run):
        """The 'destroy_current_schema' alias resolves to destroy_current_nodes."""
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action({"name": "wf1", "state": "present", "destroy_current_schema": True})
        action._client.search_api.return_value = {"results": [{"id": 100, "identifier": "n1"}]}

        result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        action._client.direct_request.assert_called_once_with("DELETE", "/api/controller/v2/workflow_job_template_nodes/100/")

    @patch.object(BaseResourceActionPlugin, "run")
    def test_string_false_does_not_destroy(self, mock_super_run):
        """String 'false' for destroy_current_nodes must not trigger deletion."""
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action({"name": "wf1", "state": "present", "destroy_current_nodes": "false"})

        result = action.run(task_vars={})

        self.assertFalse(result.get("changed", False))
        action._client.direct_request.assert_not_called()

    @patch.object(BaseResourceActionPlugin, "run")
    def test_validate_before_destroy(self, mock_super_run):
        """Invalid replacement nodes must fail before existing graph is destroyed."""
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "destroy_current_nodes": True,
                "workflow_nodes": [
                    {"identifier": "bad_node", "unified_job_template": {"name": "Missing", "type": "job_template"}},
                ],
            }
        )
        action._client.search_api.return_value = {"results": [{"id": 100, "identifier": "existing"}]}
        action._client.lookup_resource_id.side_effect = ValueError("Not found")

        result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        # Verify destroy was NOT called — no DELETE requests
        delete_calls = [c for c in action._client.direct_request.call_args_list if c[0][0] == "DELETE"]
        self.assertEqual(len(delete_calls), 0)

    @patch.object(BaseResourceActionPlugin, "run")
    def test_validate_before_destroy_missing_inventory(self, mock_super_run):
        """Missing inventory in replacement nodes must fail before destroy."""
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "destroy_current_nodes": True,
                "workflow_nodes": [
                    {
                        "identifier": "node1",
                        "unified_job_template": {"name": "JT", "type": "job_template"},
                        "inventory": {"name": "Missing Inventory"},
                    },
                ],
            }
        )
        action._client.search_api.return_value = {"results": [{"id": 100, "identifier": "existing"}]}

        def lookup_side_effect(ep, field, val, **kw):
            if ep == "unified_job_templates":
                return 42
            if ep == "inventories":
                raise ValueError("Not found")
            return None

        action._client.lookup_resource_id.side_effect = lookup_side_effect

        result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        delete_calls = [c for c in action._client.direct_request.call_args_list if c[0][0] == "DELETE"]
        self.assertEqual(len(delete_calls), 0)

    @patch.object(BaseResourceActionPlugin, "run")
    def test_approval_check_mode_idempotent(self, mock_super_run):
        """Existing unchanged approval node reports changed=False in check mode."""
        mock_super_run.return_value = {"changed": False, "failed": False, "id": 10}
        action = self._make_action(
            {
                "name": "wf1",
                "state": "present",
                "workflow_nodes": [
                    {
                        "identifier": "approval1",
                        "unified_job_template": {"name": "Approve", "type": "workflow_approval", "timeout": 600},
                    },
                ],
            },
            check_mode=True,
        )
        existing_node = {"id": 80, "identifier": "approval1", "unified_job_template": 55}

        def search_side_effect(path, query_params=None, **kwargs):
            if query_params and query_params.get("identifier") == "approval1":
                return {"results": [existing_node]}
            return {"results": []}

        action._client.search_api.side_effect = search_side_effect
        action._client.is_workflow_approval_template.return_value = True
        action._client.manage_workflow_approval.return_value = False

        result = action.run(task_vars={})

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])
        action._client.manage_workflow_approval.assert_called_once_with(80, {"name": "Approve", "timeout": 600}, check_mode=True)


if __name__ == "__main__":
    unittest.main()
