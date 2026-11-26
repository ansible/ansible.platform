"""Check-mode behavior for multi-object role assignments."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.role_team_assignment import ActionModule as RoleTeamAssignmentAction
from ansible_collections.ansible.platform.plugins.action.role_user_assignment import ActionModule as RoleUserAssignmentAction


@pytest.mark.parametrize(
    "action_class,args",
    [
        (
            RoleUserAssignmentAction,
            {"role_definition": "10", "user": "20", "object_ids": [30, 31]},
        ),
        (
            RoleTeamAssignmentAction,
            {"role_definition": "10", "team": "20", "assignment_objects": [{"object_id": 30}, {"object_id": 31}]},
        ),
    ],
)
@pytest.mark.parametrize(
    "state,found_ids,expected_changed",
    [
        ("present", {30}, True),
        ("present", {30, 31}, False),
        ("absent", {30}, True),
        ("absent", set(), False),
    ],
)
def test_multi_object_assignments_honor_check_mode(action_class, args, state, found_ids, expected_changed, monkeypatch):
    task_args = {**args, "state": state}
    manager = MagicMock()

    def find_assignment(*, operation, module_name, ansible_data):
        assert operation == "find"
        object_id = int(ansible_data["object_id"])
        return {"id": object_id + 100, "object_id": object_id} if object_id in found_ids else None

    manager.execute.side_effect = find_assignment

    action = action_class.__new__(action_class)
    action._task = SimpleNamespace(args=task_args, check_mode=True)
    action._display = MagicMock()
    action._display.verbosity = 0
    action._validate_action_input = MagicMock(return_value=SimpleNamespace(validated_params=task_args))
    action._get_or_spawn_manager = MagicMock(return_value=(manager, None))
    monkeypatch.setattr(ActionBase, "run", lambda self, tmp=None, task_vars=None: {"changed": False})

    result = action.run(task_vars={})

    assert result["changed"] is expected_changed
    assert result["failed"] is False
    assert [call.kwargs["operation"] for call in manager.execute.call_args_list] == ["find", "find"]
