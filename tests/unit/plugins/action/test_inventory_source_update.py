"""Unit tests for inventory_source_update action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock, patch

import pytest
from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.inventory_source_update import ActionModule


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
def test_wait_without_timeout_preserves_legacy_indefinite_wait(action_module, timeout):
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
    assert result["elapsed"] == 12.5
    assert result["started"] == "start"
    assert result["finished"] == "finish"


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
