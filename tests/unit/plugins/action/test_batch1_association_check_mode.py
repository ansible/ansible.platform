"""Check-mode compatibility for Batch 1 association actions."""

from unittest.mock import MagicMock, patch

import pytest
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.action.inventory import ActionModule as InventoryAction
from ansible_collections.ansible.platform.plugins.action.inventory_source import ActionModule as InventorySourceAction
from ansible_collections.ansible.platform.plugins.action.schedule import ActionModule as ScheduleAction
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import ValidationError


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


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("error_type", [ValueError, ValidationError])
def test_schedule_missing_association_is_a_potential_change_only_in_check_mode(check_mode, error_type):
    """Allow missing dry-run dependencies while still comparing other associations."""
    action = ScheduleAction.__new__(ScheduleAction)
    action._task = MagicMock()
    action._task.args = {"name": "Weekly", "credentials": ["Missing"], "labels": ["Existing"], "instance_groups": []}
    action._task.check_mode = check_mode
    action._client = MagicMock()
    action._client.manage_associations.side_effect = [error_type("Resource 'credentials' with name=Missing not found"), False, False]
    with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "id": 7}):
        result = action.run(task_vars={})

    assert result.get("failed", False) is not check_mode
    assert result["changed"] is check_mode
    calls = action._client.manage_associations.call_args_list
    assert [call.args[2] for call in calls] == (["credentials", "labels", "instance_groups"] if check_mode else ["credentials"])
    assert all(call.kwargs["check_mode"] is check_mode for call in calls)


@pytest.mark.parametrize(
    "error",
    [
        ValueError("Resource 'credentials' with name=Duplicate matched multiple resources; provide additional filters"),
        RuntimeError("Connection failed"),
        ValidationError("Resource 'schedules' with name=Weekly not found"),
    ],
)
def test_schedule_check_mode_preserves_other_association_errors(error):
    """Keep ambiguity, connectivity, and unrelated missing-resource errors visible."""
    action = ScheduleAction.__new__(ScheduleAction)
    action._task = MagicMock()
    action._task.args = {"name": "Weekly", "credentials": ["resource"]}
    action._task.check_mode = True
    action._client = MagicMock()
    action._client.manage_associations.side_effect = error
    with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "id": 7}):
        result = action.run(task_vars={})

    assert result["failed"]
    assert not result["changed"]
    assert str(error) in result["msg"]
