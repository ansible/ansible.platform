"""Unit tests for schedule action idempotency behavior."""

from ansible_collections.ansible.platform.plugins.action.schedule import ActionModule


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
