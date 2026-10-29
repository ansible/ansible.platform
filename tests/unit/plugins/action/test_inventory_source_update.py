"""Unit tests for inventory_source_update action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock

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
        manager.lookup_resource_id.assert_called_once_with("inventories", "name", "My Inventory", service="controller")

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
