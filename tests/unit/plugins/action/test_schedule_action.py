"""Unit tests for schedule action idempotency behavior."""

from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.action.schedule import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.schedule import AnsibleSchedule
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.schedule import ScheduleTransformMixin_v2


def test_organization_does_not_trigger_schedule_update():
    action = ActionModule.__new__(ActionModule)

    assert not action._should_update(
        {"name": "Weekly", "organization": "Engineering"},
        {"name": "Weekly", "organization": None},
    )


def test_other_schedule_fields_use_parent_change_detection():
    action = ActionModule.__new__(ActionModule)

    assert action._should_update(
        {"name": "Weekly", "organization": "Engineering", "description": "Updated"},
        {"name": "Weekly", "organization": None, "description": "Old"},
    )


def test_exists_fails_when_organization_lookup_reports_not_found():
    action = ActionModule.__new__(ActionModule)
    action._task = MagicMock()
    action._task.args = {"name": "Weekly", "unified_job_template": "Shared", "organization": "Missing Org", "state": "exists"}
    action._task.check_mode = False
    action._display = MagicMock()
    action._display.verbosity = 0

    manager = MagicMock()
    manager.lookup_resource_id.side_effect = ValueError("Resource 'organizations' with name=Missing Org not found")

    def find_schedule(**kwargs):
        ScheduleTransformMixin_v2.from_ansible_data(
            AnsibleSchedule(name="Weekly", unified_job_template="Shared", organization="Missing Org"),
            {"operation": "find", "manager": manager},
        )

    manager.execute.side_effect = find_schedule
    resource_data = {"name": "Weekly", "unified_job_template": "Shared", "organization": "Missing Org"}
    prepared = {
        "result": {},
        "argspec": {"argument_spec": {}},
        "validated_params": {**resource_data, "state": "exists"},
        "resource_data": resource_data,
        "write_only_data": {},
        "manager": manager,
    }

    with patch.object(action, "_prepare_action", return_value=prepared):
        result = action.run(task_vars={})

    assert result["failed"]
    assert "Failed to resolve schedule organization" in result["msg"]
    assert "exists" not in result
