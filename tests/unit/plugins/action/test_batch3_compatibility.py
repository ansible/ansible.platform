"""Batch 3 lookup, approval, and association check-mode regressions."""

import json
from unittest.mock import MagicMock, patch

import pytest
from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.action.instance_group import ActionModule as InstanceGroupAction
from ansible_collections.ansible.platform.plugins.action.workflow_job_template_node import ActionModule as NodeAction
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.workflow_job_template_node import AnsibleWorkflowJobTemplateNode
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.workflow_job_template_node import WorkflowJobTemplateNodeTransformMixin_v2


@pytest.mark.parametrize(
    "module,alias,canonical,extra",
    [("workflow_launch", "workflow_template", "name", {}), ("workflow_job_template_node", "workflow", "workflow_job_template", {"identifier": "leaf"})],
)
def test_real_preparation_normalizes_legacy_workflow_aliases(module, alias, canonical, extra):
    """Pass only canonical validated keys into models when aliases are used."""
    from importlib import import_module

    action_type = import_module("ansible_collections.ansible.platform.plugins.action." + module).ActionModule
    action = action_type.__new__(action_type)
    action._task = MagicMock(args={alias: "Workflow", **extra})
    action._display = MagicMock()
    with patch("ansible.plugins.action.ActionBase.run", return_value={}), patch.object(action, "_get_or_spawn_manager", return_value=(MagicMock(), None)):
        prepared = action._prepare_action(None, {})
    assert alias not in prepared["validated_params"]
    assert alias not in prepared["resource_data"]
    model = action.MODEL_CLASS(**prepared["resource_data"])
    assert getattr(model, canonical) == "Workflow"


@pytest.mark.parametrize("action_type,field", [(InstanceGroupAction, "instances"), (NodeAction, "credentials")])
@pytest.mark.parametrize("changed", [False, True])
def test_association_check_mode_compares_instead_of_writing(action_type, field, changed):
    """Use the SDK's association comparison for changed and unchanged dry runs."""
    action = action_type.__new__(action_type)
    action._task = MagicMock(args={"name": "Resource", field: ["Existing"]}, check_mode=True)
    action._client = MagicMock()
    action._client.manage_associations.return_value = changed
    result_data = {"id": 7, "changed": False, action.MODULE_NAME: {"id": 7, "workflow_job_template": 3}}
    with patch.object(BaseResourceActionPlugin, "run", return_value=result_data):
        result = action.run(task_vars={})
    assert result["changed"] is changed
    assert action._client.manage_associations.call_args.kwargs["check_mode"] is True


def test_node_parent_and_target_use_independent_organization_scopes():
    """Resolve a target outside its parent workflow's organization."""
    manager = MagicMock()
    manager.lookup_resource_id.side_effect = [10, 20, 30, 40]
    model = AnsibleWorkflowJobTemplateNode(
        identifier="leaf", workflow_job_template="Parent", organization="Parent Org", unified_job_template="Job", lookup_organization="Job Org"
    )
    result = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(model, {"manager": manager, "operation": "create"})
    assert result.workflow_job_template == 20
    assert result.unified_job_template == 40
    manager.lookup_resource_id.assert_any_call("workflow_job_templates", "name", "Parent", service="controller", extra_query_params={"organization": 10})
    manager.lookup_resource_id.assert_any_call("unified_job_templates", "name", "Job", service="controller", extra_query_params={"organization": 30})


@pytest.mark.parametrize("operation", ["find", "delete"])
def test_node_lookup_ignores_unused_launch_references(operation):
    """Find and delete nodes without resolving unused update fields."""
    manager = MagicMock()
    model = AnsibleWorkflowJobTemplateNode(
        identifier="leaf", workflow_job_template="3", unified_job_template="Missing", inventory="Missing", execution_environment="Missing"
    )
    result = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(model, {"manager": manager, "operation": operation})
    assert result.workflow_job_template == 3
    manager.lookup_resource_id.assert_not_called()


def test_node_preserves_explicit_execution_environment_clear():
    """Send the legacy empty value instead of looking up an empty name."""
    manager = MagicMock()
    model = AnsibleWorkflowJobTemplateNode(identifier="leaf", workflow_job_template="3", execution_environment="")
    result = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(model, {"manager": manager, "operation": "update"})
    assert result.execution_environment == ""
    manager.lookup_resource_id.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_node_approval_reconciliation_uses_shared_sdk(check_mode):
    """Keep action orchestration independent of the HTTP transport."""
    action = NodeAction.__new__(NodeAction)
    action._task = MagicMock(args={"identifier": "approval", "workflow_job_template": "3", "approval_node": {"name": "Approve"}}, check_mode=check_mode)
    action._client = MagicMock()
    action._client.manage_workflow_approval.return_value = False
    with patch.object(BaseResourceActionPlugin, "run", return_value={"id": 7, "changed": False}):
        result = action.run(task_vars={})
    assert not result["changed"]
    assert result["workflow_node_id"] == 7
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
    action = NodeAction.__new__(NodeAction)
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


@pytest.mark.parametrize("persistent", [False, True])
def test_job_list_preserves_legacy_limit_above_one_thousand_jobs(persistent):
    """Retrieve multiple pages beyond the SDK's default safety cap."""
    from ansible_collections.ansible.platform.plugins.action.job_list import ActionModule
    from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
    from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient

    client_type = PlatformService if persistent else DirectHTTPClient
    client = client_type.__new__(client_type)
    client.base_url = "https://gateway.example"
    client.api_versions = {"gateway": "1", "controller": "2"}
    client.cache = {}
    client._authenticated = True
    client.record_activity = MagicMock()
    client.session = MagicMock()
    results = [{"id": i} for i in range(1001)]
    responses = []
    for page, next_url in [(results[:1000], "/api/controller/v2/jobs/?page=2"), (results[1000:], None)]:
        body = {"count": 1001, "results": page, "next": next_url, "previous": None}
        response = MagicMock()
        response.read.return_value = json.dumps(body).encode()
        response.json.return_value = body
        responses.append(response)
    client._make_request = MagicMock(side_effect=responses)
    action = ActionModule.__new__(ActionModule)
    action._display = MagicMock()
    action._prepare_action = MagicMock(return_value={"result": {}, "validated_params": {"all_pages": True}, "manager": client})
    result = action.run(task_vars={})
    assert not result["failed"]
    assert result["results"] == results
    assert result["next"] is None
    assert client._make_request.call_count == 2


@pytest.mark.parametrize("reference,expected", [("42", 42), ("Deploy++Org", 42)])
def test_export_resolves_non_name_selectors(reference, expected):
    """Export numeric IDs and named URLs through the appropriate ID query."""
    from ansible_collections.ansible.platform.plugins.action.export import ActionModule

    manager = MagicMock()
    manager.lookup_resource_id.return_value = 42
    manager.search_api.return_value = {"results": [{"id": 42, "name": "Deploy"}]}
    action = ActionModule.__new__(ActionModule)
    result = action._search_resources(manager, "api/controller/v2/projects/", "name", [reference], 10)
    assert result == {"results": [{"id": 42, "name": "Deploy"}]}
    manager.search_api.assert_called_once_with(endpoint="api/controller/v2/projects/", query_params={"id": expected}, return_all=True, max_objects=10)
    if "++" in reference:
        manager.lookup_resource_id.assert_called_once_with("projects", "name", reference, service="controller")
    else:
        manager.lookup_resource_id.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("wait", [False, True])
def test_workflow_launch_negative_timeout_respects_wait_and_check_mode(check_mode, wait):
    """Only wait on negative timeouts after a real launch when requested."""
    from ansible_collections.ansible.platform.plugins.action.workflow_launch import ActionModule

    action = ActionModule.__new__(ActionModule)
    action._task = MagicMock(check_mode=check_mode)
    action._display = MagicMock(verbosity=0)
    manager = MagicMock()
    manager.search_api.return_value = {"results": [{"id": 3}]}
    manager.launch_resource.return_value = {"id": 42, "status": "pending"}
    manager.wait_for_completion.return_value = {"id": 42, "status": "successful"}
    action._prepare_action = MagicMock(
        return_value={"result": {}, "validated_params": {"name": "Workflow", "timeout": -5, "wait": wait}, "resource_data": {}, "manager": manager}
    )
    result = action.run(task_vars={})
    assert not result.get("failed"), result.get("msg")
    if check_mode:
        manager.launch_resource.assert_not_called()
    else:
        manager.launch_resource.assert_called_once()
    if wait and not check_mode:
        assert manager.wait_for_completion.call_args.kwargs["timeout"] == 0.0
    else:
        manager.wait_for_completion.assert_not_called()
