"""Approval template reconciliation contracts for both SDK transports."""

import json
from unittest.mock import MagicMock

import pytest
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient


@pytest.fixture(params=[DirectHTTPClient, PlatformService], ids=["direct", "persistent"])
def client(request):
    """Construct either SDK transport with isolated HTTP responses."""
    instance = request.param.__new__(request.param)
    instance.base_url = "https://gateway.example"
    instance.api_versions = {"gateway": "1", "controller": "2"}
    instance.cache = {}
    instance._authenticated = True
    instance.session = MagicMock()
    instance.record_activity = MagicMock()
    instance.search_api = MagicMock()
    response = MagicMock()
    response.read.return_value = b"{}"
    response.json.return_value = {}
    response.content = b"{}"
    instance._make_request = MagicMock(return_value=response)
    return instance


@pytest.mark.parametrize("check_mode", [False, True])
def test_create_approval_uses_node_endpoint_and_never_retries(client, check_mode):
    """Create once in live mode and predict creation without dry-run writes."""
    client.search_api.return_value = {"id": 7, "unified_job_template": None}
    assert client.manage_workflow_approval(7, {"name": "Approve", "timeout": 0}, check_mode=check_mode)
    if check_mode:
        client._make_request.assert_not_called()
    else:
        call = client._make_request.call_args
        assert call.args[0].upper() == "POST"
        assert call.args[1] == "https://gateway.example/api/controller/v2/workflow_job_template_nodes/7/create_approval_template/"
        assert call.kwargs["json"] == {"name": "Approve", "timeout": 0}
        if isinstance(client, PlatformService):
            assert call.kwargs["retry_config"].max_attempts == 1


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("description", ["Old", ""])
def test_existing_approval_compares_fields_and_only_patches_changes(client, check_mode, description):
    """Keep approval idempotency and explicit empty descriptions in both modes."""
    client.search_api.side_effect = [
        {"id": 7, "unified_job_template": 30},
        {"id": 30, "type": "workflow_approval_template", "name": "Approve", "description": description, "timeout": 0},
    ]
    changed = client.manage_workflow_approval(7, {"name": "Approve", "description": "", "timeout": 0}, check_mode=check_mode)
    assert changed is (description != "")
    if check_mode or description == "":
        client._make_request.assert_not_called()
    else:
        call = client._make_request.call_args
        assert call.args[:2] == ("PATCH", "https://gateway.example/api/controller/v2/workflow_approval_templates/30/")
        payload = call.kwargs.get("json")
        if payload is None:
            payload = json.loads(call.kwargs["data"])
        assert payload == {"description": ""}


def test_approval_does_not_mutate_a_job_template(client):
    """Reject unrelated target types before attempting an approval update."""
    client.search_api.side_effect = [{"unified_job_template": 30}, {"id": 30, "type": "job_template", "name": "Job"}]
    with pytest.raises(ValueError, match="non-approval template"):
        client.manage_workflow_approval(7, {"name": "Approve"})
    client._make_request.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_rpc_forwards_approval_check_mode(check_mode):
    """Preserve the active connection mode when invoking approval reconciliation."""
    client = ManagerRPCClient.__new__(ManagerRPCClient)
    client.service_proxy = MagicMock()
    client.service_proxy.manage_workflow_approval.return_value = False
    assert client.manage_workflow_approval(7, {"name": "Approve"}, check_mode=check_mode) is False
    client.service_proxy.manage_workflow_approval.assert_called_once_with(7, {"name": "Approve"}, check_mode)
