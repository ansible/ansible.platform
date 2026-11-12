"""Unit tests for inventory_source_update action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock, patch

import pytest
from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.inventory_source_update import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError


@pytest.fixture
def action_module():
    """Create an ActionModule instance with mocked dependencies."""
    task = MagicMock()
    task.args = {}
    task.async_val = 0
    connection = MagicMock()
    play_context = MagicMock()
    loader = MagicMock()
    templar = MagicMock()
    shared_loader_obj = MagicMock()
    module = ActionModule(
        task=task,
        connection=connection,
        play_context=play_context,
        loader=loader,
        templar=templar,
        shared_loader_obj=shared_loader_obj,
    )
    return module


class TestResolveInventory:
    def test_numeric_id_passthrough(self, action_module):
        manager = MagicMock()
        result = action_module._resolve_inventory(manager, "42", None)
        assert result == 42
        manager.lookup_resource_id.assert_not_called()
        manager.search_api.assert_not_called()

    def test_name_without_org(self, action_module):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 10
        result = action_module._resolve_inventory(manager, "My Inventory", None)
        assert result == 10
        manager.lookup_resource_id.assert_called_once_with("inventories", "name", "My Inventory", service="controller", require_unique=True)

    def test_name_with_org(self, action_module):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 5
        manager.search_api.return_value = {"results": [{"id": 10}]}
        result = action_module._resolve_inventory(manager, "My Inventory", "Engineering")
        assert result == 10
        manager.lookup_resource_id.assert_called_once_with("organizations", "name", "Engineering", service="controller")
        manager.search_api.assert_called_once()

    def test_name_with_org_not_found(self, action_module):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 5
        manager.search_api.return_value = {"results": []}
        with pytest.raises(AnsibleError, match="not found in organization"):
            action_module._resolve_inventory(manager, "Missing", "Engineering")


class TestResolveInventorySource:
    def test_numeric_id_validated_against_inventory(self, action_module):
        manager = MagicMock()
        manager.search_api.return_value = {"results": [{"id": 99}]}
        result = action_module._resolve_inventory_source(manager, "99", 10)
        assert result == 99
        call_args = manager.search_api.call_args
        assert call_args[1]["query_params"] == {"id": 99, "inventory": 10}

    def test_numeric_id_wrong_inventory(self, action_module):
        manager = MagicMock()
        manager.search_api.return_value = {"results": []}
        with pytest.raises(AnsibleError, match="not found in inventory"):
            action_module._resolve_inventory_source(manager, "99", 10)

    def test_name_with_inventory(self, action_module):
        manager = MagicMock()
        manager.search_api.return_value = {"results": [{"id": 77}]}
        result = action_module._resolve_inventory_source(manager, "AWS Source", 10)
        assert result == 77
        call_args = manager.search_api.call_args
        assert call_args[1]["query_params"] == {"name": "AWS Source", "inventory": 10}

    def test_name_not_found(self, action_module):
        manager = MagicMock()
        manager.search_api.return_value = {"results": []}
        with pytest.raises(AnsibleError, match="not found in inventory"):
            action_module._resolve_inventory_source(manager, "Missing Source", 10)


def test_sync_request_uses_declared_endpoint_operation(action_module):
    manager = MagicMock()
    manager.search_api.return_value = {"results": [{"id": 23}]}
    manager.launch_resource.return_value = {"id": 55, "status": "pending"}
    action_module._task.check_mode = False
    prepared = {
        "result": {},
        "validated_params": {"name": "AWS Source", "inventory": "10", "wait": False},
        "manager": manager,
    }

    with patch.object(action_module, "_prepare_action", return_value=prepared):
        result = action_module.run(task_vars={})

    assert result["id"] == 55
    manager.search_api.assert_called_once_with(
        "/api/controller/v2/inventory_sources/",
        query_params={"inventory": 10, "name": "AWS Source"},
    )
    manager.launch_resource.assert_called_once_with(
        "/api/controller/v2/inventory_sources/23/update/",
        {},
        service="controller",
        retry=False,
    )


@pytest.mark.parametrize("timeout", [None, 0])
def test_wait_without_timeout_waits_indefinitely(action_module, timeout):
    manager = MagicMock()
    manager.search_api.return_value = {"results": [{"id": 23}]}
    manager.launch_resource.return_value = {"id": 55, "status": "pending", "url": "/api/controller/v2/inventory_updates/55/"}
    manager.wait_for_completion.return_value = {"id": 55, "status": "successful", "elapsed": 12.5, "started": "start", "finished": "finish"}
    action_module._task.check_mode = False
    prepared = {
        "result": {},
        "validated_params": {"name": "AWS Source", "inventory": "10", "wait": True, "timeout": timeout},
        "manager": manager,
    }

    with patch.object(action_module, "_prepare_action", return_value=prepared):
        result = action_module.run(task_vars={})

    assert manager.wait_for_completion.call_args.kwargs["timeout"] == -1.0
    assert result == {
        "changed": True,
        "failed": False,
        "id": 55,
        "status": "successful",
        "elapsed": 12.5,
        "started": "start",
        "finished": True,
        "finished_at": "finish",
    }


def test_wait_failure_preserves_job_data(action_module):
    manager = MagicMock()
    manager.search_api.return_value = {"results": [{"id": 23}]}
    manager.launch_resource.return_value = {"id": 55, "status": "pending", "url": "/api/controller/v2/inventory_updates/55/"}
    manager.wait_for_completion.return_value = {"id": 55, "status": "failed", "failed": True, "elapsed": 3.0}
    action_module._task.check_mode = False
    prepared = {
        "result": {},
        "validated_params": {"name": "AWS Source", "inventory": "10", "wait": True},
        "manager": manager,
    }

    with patch.object(action_module, "_prepare_action", return_value=prepared):
        result = action_module.run(task_vars={})

    assert result["failed"] is True
    assert result["job_data"] == manager.wait_for_completion.return_value


@pytest.mark.parametrize("timeout,expected", [(None, -1.0), (0, -1.0), (-1, 0.0), (-5, 0.0), (30, 30.0)])
def test_launch_wait_timeout_normalization(action_module, timeout, expected):
    """Use unlimited zero/omitted waits and immediate negative-timeout waits."""
    action = action_module
    action._task.args = {"name": "Resource", "wait": True, "timeout": timeout, "inventory": "1"}
    action._task.check_mode = False
    action._client = MagicMock()
    manager = action._client
    manager.lookup_resource_id.return_value = 1
    manager.search_api.return_value = {"results": [{"id": 1}]}
    manager.launch_resource.return_value = {"id": 42, "status": "pending"}
    manager.wait_for_completion.return_value = {"id": 42, "status": "successful"}
    with patch("ansible.plugins.action.ActionBase.run", return_value={}), patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
        result = action.run(task_vars={})
    assert not result.get("failed")
    assert manager.wait_for_completion.call_args.kwargs["timeout"] == expected


@pytest.mark.parametrize("status", ["running", "successful"])
def test_negative_launch_timeout_polls_once_using_real_waiter(action_module, status):
    """Stop after the first unfinished response while accepting a terminal job."""
    action = action_module
    action._task.args = {"name": "Resource", "wait": True, "timeout": -5, "inventory": "1"}
    action._task.check_mode = False
    action._client = MagicMock()
    manager = action._client
    manager.lookup_resource_id.return_value = 1
    manager.search_api.return_value = {"results": [{"id": 1}]}
    manager.launch_resource.return_value = {"id": 42, "status": "pending"}
    client = DirectHTTPClient.__new__(DirectHTTPClient)
    client.base_url = "https://gateway.example"
    client.api_versions = {"controller": "2"}
    client._get_json = MagicMock(side_effect=[{"id": 42, "status": status}, AssertionError("Waiter polled more than once")])
    manager.wait_for_completion = client.wait_for_completion
    with (
        patch("ansible.plugins.action.ActionBase.run", return_value={}),
        patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)),
        patch("ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client.time.sleep") as sleep,
    ):
        result = action.run(task_vars={})
    assert {
        "changed": result["changed"],
        "failed": result.get("failed", False),
        "id": result["id"],
        "status": result["status"],
    } == {"changed": True, "failed": status == "running", "id": 42, "status": status}, result.get("msg")
    client._get_json.assert_called_once()
    manager.launch_resource.assert_called_once()
    sleep.assert_not_called()


@pytest.mark.parametrize("timed_out", [False, True])
def test_inventory_update_retains_timestamp_using_documented_platform_key(action_module, timed_out):
    """Preserve timing for both completed and timed-out inventory updates."""
    action = action_module
    action._task.args = {"name": "Resource", "inventory": "1", "wait": True}
    action._task.check_mode = False
    action._client = MagicMock()
    manager = action._client
    manager.lookup_resource_id.return_value = 1
    manager.search_api.return_value = {"results": [{"id": 1}]}
    manager.launch_resource.return_value = {"id": 42, "status": "pending"}
    data = {"id": 42, "status": "successful", "elapsed": 2.0, "started": "2026-01-01T00:00:00Z", "finished": "2026-01-01T00:00:02Z"}
    manager.wait_for_completion.return_value = data
    if timed_out:
        data.update(status="running", finished=None)
        manager.wait_for_completion.side_effect = WaitTimeoutError("Timed out", last_result=data)
    with patch("ansible.plugins.action.ActionBase.run", return_value={}), patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
        result = action.run(task_vars={})
    expected = {"finished": not timed_out, "finished_at": data["finished"], "elapsed": 2.0}
    assert {key: result[key] for key in expected} == expected
