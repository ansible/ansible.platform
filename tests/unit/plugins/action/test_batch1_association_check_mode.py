"""Check-mode compatibility for Batch 1 association actions."""

from unittest.mock import MagicMock, patch

import pytest
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.action.inventory import ActionModule as InventoryAction
from ansible_collections.ansible.platform.plugins.action.inventory_source import ActionModule as InventorySourceAction
from ansible_collections.ansible.platform.plugins.action.schedule import ActionModule as ScheduleAction


@pytest.mark.parametrize(
    "action_type,field",
    [(InventoryAction, "instance_groups"), (ScheduleAction, "credentials"), (InventorySourceAction, "notification_templates_success")],
)
@pytest.mark.parametrize("desired", [["resource"], []])
@pytest.mark.parametrize("changed", [False, True])
def test_check_mode_compares_associations(action_type, field, desired, changed):
    """Predict unchanged, added, and cleared associations through SDK dry runs."""
    action = action_type.__new__(action_type)
    action._task = MagicMock()
    action._task.args = {"name": "resource", field: desired}
    action._task.check_mode = True
    action._client = MagicMock()
    action._client.manage_associations.return_value = changed
    with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "id": 7}):
        result = action.run(task_vars={})

    assert result["changed"] is changed
    action._client.manage_associations.assert_called_once()
    assert action._client.manage_associations.call_args.kwargs["check_mode"] is True
    assert action._client.manage_associations.call_args.args[3] == desired


@pytest.mark.parametrize("action_type", [InventoryAction, ScheduleAction, InventorySourceAction])
def test_read_only_state_does_not_reconcile_associations(action_type):
    """Read-only lookups remain read-only when association arguments are supplied."""
    action = action_type.__new__(action_type)
    action._task = MagicMock()
    action._task.args = {"name": "resource", "state": "exists", "instance_groups": [], "credentials": [], "notification_templates_success": []}
    action._task.check_mode = True
    action._client = MagicMock()
    with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "id": 7}):
        result = action.run(task_vars={})

    assert result["changed"] is False
    action._client.manage_associations.assert_not_called()
