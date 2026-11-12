from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock, patch

import pytest
from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.action.workflow_job_template_node import ActionModule, WorkflowNodeNotFoundError

__metaclass__ = type


class TestWorkflowNodeIdentifierResolution(unittest.TestCase):
    def test_resolves_identifiers_in_one_workflow_scoped_batch(self):
        manager = MagicMock()
        manager.lookup_resource_ids.return_value = {"123": 30, "child": 31}

        result = ActionModule._resolve_node_ids_in_workflow(manager, 77, ["123", "child", "123"])

        self.assertEqual(result, [30, 31, 30])
        manager.lookup_resource_ids.assert_called_once_with(
            "workflow_job_template_nodes",
            "identifier",
            ["123", "child", "123"],
            service="controller",
            extra_query_params={"workflow_job_template": 77},
            numeric_is_id=False,
            allow_missing=True,
        )

    def test_preserves_missing_identifier_error_with_workflow_scope(self):
        manager = MagicMock()
        manager.lookup_resource_ids.return_value = {"present": 30}

        with self.assertRaisesRegex(WorkflowNodeNotFoundError, "Workflow node with identifier 'missing' not found in workflow 77"):
            ActionModule._resolve_node_ids_in_workflow(manager, 77, ["present", "missing"])

    def test_missing_association_is_only_predicted_in_check_mode(self):
        """Use the real missing-node exception without relying on its message."""
        for check_mode in (False, True):
            with self.subTest(check_mode=check_mode):
                action = ActionModule.__new__(ActionModule)
                action._task = MagicMock(args={"success_nodes": ["missing"]}, check_mode=check_mode)
                action._client = MagicMock()
                action._client.lookup_resource_ids.return_value = {}
                current = {"id": 7, "changed": False, "workflow_job_template_node": {"workflow_job_template": 77}}
                with patch.object(BaseResourceActionPlugin, "run", return_value=current):
                    result = action.run(task_vars={})
                self.assertEqual(
                    {"failed": result.get("failed", False), "changed": result["changed"]},
                    {"failed": not check_mode, "changed": check_mode},
                )
                action._client.manage_associations.assert_not_called()

    def test_other_lookup_errors_are_not_predicted_as_changes(self):
        """Propagate lookup failures even when their text resembles a missing node."""
        for message in ("Permission denied", "Workflow node with identifier 'missing' not found in workflow 77"):
            with self.subTest(message=message):
                action = ActionModule.__new__(ActionModule)
                action._task = MagicMock(args={"success_nodes": ["missing"]}, check_mode=True)
                action._client = MagicMock()
                action._client.lookup_resource_ids.side_effect = ValueError(message)
                current = {"id": 7, "changed": False, "workflow_job_template_node": {"workflow_job_template": 77}}
                with patch.object(BaseResourceActionPlugin, "run", return_value=current):
                    result = action.run(task_vars={})
                self.assertEqual({"failed": result["failed"], "changed": result["changed"]}, {"failed": True, "changed": False})
                self.assertIn(message, result["msg"])
                action._client.manage_associations.assert_not_called()


@pytest.mark.parametrize("changed", [False, True])
def test_association_check_mode_compares_instead_of_writing(changed):
    """Use the SDK's association comparison for changed and unchanged dry runs."""
    action = ActionModule.__new__(ActionModule)
    action._task = MagicMock(args={"name": "Resource", "credentials": ["Existing"]}, check_mode=True)
    action._client = MagicMock()
    action._client.manage_associations.return_value = changed
    result_data = {"id": 7, "changed": False, action.MODULE_NAME: {"id": 7, "workflow_job_template": 3}}
    with patch.object(BaseResourceActionPlugin, "run", return_value=result_data):
        result = action.run(task_vars={})
    assert result["changed"] is changed
    assert action._client.manage_associations.call_args.kwargs["check_mode"] is True


@pytest.mark.parametrize("check_mode", [False, True])
def test_node_approval_reconciliation_uses_shared_sdk(check_mode):
    """Keep action orchestration independent of the HTTP transport."""
    action = ActionModule.__new__(ActionModule)
    action._task = MagicMock(args={"identifier": "approval", "workflow_job_template": "3", "approval_node": {"name": "Approve"}}, check_mode=check_mode)
    action._client = MagicMock()
    action._client.manage_workflow_approval.return_value = False
    with patch.object(BaseResourceActionPlugin, "run", return_value={"id": 7, "changed": False}):
        result = action.run(task_vars={})
    assert result == {"id": 7, "changed": False, "workflow_node_id": 7}
    action._client.manage_workflow_approval.assert_called_once_with(7, {"name": "Approve"}, check_mode=check_mode)


@pytest.mark.parametrize(
    "extra,valid",
    [
        ({"approval_node": {"name": "Approve", "timeout": 0}}, True),
        ({"approval_node": {}}, False),
        ({"approval_node": {"name": "Approve"}, "unified_job_template": "Job"}, False),
        ({"lookup_organization": "Other Org", "unified_job_template": "Job"}, True),
        ({"verbosity": "3"}, True),
    ],
)
def test_real_node_argument_validation_preserves_approval_contract(extra, valid):
    """Validate nested approval fields and exclusions with the real argspec."""
    action = ActionModule.__new__(ActionModule)
    action._task = MagicMock(args={"identifier": "node", "workflow_job_template": "Parent", **extra})
    action._display = MagicMock()
    argspec = action._build_argspec_from_docs(action._get_documentation())
    if valid:
        validation = action._validate_data(action._task.args, argspec, "input")
        assert not validation.error_messages
        if "verbosity" in extra:
            assert validation.validated_parameters["verbosity"] == 3
    else:
        with pytest.raises(AnsibleError, match="Input validation failed"):
            action._validate_data(action._task.args, argspec, "input")


if __name__ == "__main__":
    unittest.main()
