# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for user organization membership reconciliation."""

from __future__ import absolute_import, division, print_function

from importlib import import_module
from unittest.mock import Mock

import pytest
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin

ActionModule = import_module("ansible_collections.ansible.platform.plugins.action.user").ActionModule


def _action(manager, check_mode=False):
    action = ActionModule.__new__(ActionModule)
    action._client = manager
    action._task = Mock(check_mode=check_mode, args={"state": "present"})
    return action


def test_existing_membership_is_idempotent():
    manager = Mock()
    manager.lookup_resource_id.side_effect = [31, 42]
    manager.execute.return_value = {"id": 99}
    action = _action(manager)
    result = {"id": 7, "changed": False}

    action._handle_organization_memberships(result, ["Default"])

    assert result["changed"] is False
    manager.execute.assert_called_once_with(
        operation="find",
        module_name="role_user_assignment",
        ansible_data={"role_definition": "31", "object_id": 42, "user": "7"},
    )


def test_missing_membership_is_reported_changed_in_check_mode_without_create():
    manager = Mock()
    manager.lookup_resource_id.side_effect = [31, 42]
    manager.execute.side_effect = ValueError("Resource with name=Organization Member not found")
    action = _action(manager, check_mode=True)
    result = {"id": 7, "changed": False}

    action._handle_organization_memberships(result, ["Default"])

    assert result["changed"] is True
    manager.execute.assert_called_once_with(
        operation="find",
        module_name="role_user_assignment",
        ansible_data={"role_definition": "31", "object_id": 42, "user": "7"},
    )


def test_unresolved_organization_fails_without_creating_assignment():
    manager = Mock()
    manager.lookup_resource_id.side_effect = [31, None]
    action = _action(manager)
    result = {"id": 7, "changed": False}

    action._handle_organization_memberships(result, ["Missing"])

    assert result["failed"] is True
    assert "Organization 'Missing' was not found" in result["msg"]
    manager.execute.assert_not_called()


def test_assignment_lookup_errors_fail_without_attempting_create():
    manager = Mock()
    manager.lookup_resource_id.side_effect = [31, 42]
    manager.execute.side_effect = RuntimeError("Gateway unavailable")
    action = _action(manager)
    result = {"id": 7, "changed": False}

    action._handle_organization_memberships(result, ["Default"])

    assert result["failed"] is True
    assert "Gateway unavailable" in result["msg"]
    manager.execute.assert_called_once_with(
        operation="find",
        module_name="role_user_assignment",
        ansible_data={"role_definition": "31", "object_id": 42, "user": "7"},
    )


def test_new_user_membership_check_mode_does_not_require_a_user_id():
    manager = Mock()
    manager.lookup_resource_id.side_effect = [31, 42]
    action = _action(manager, check_mode=True)
    result = {"changed": True}

    action._handle_organization_memberships(result, ["Default"])

    assert result["changed"] is True
    manager.execute.assert_not_called()


@pytest.mark.parametrize("state", ["absent", "exists"])
def test_read_or_delete_states_do_not_reconcile_memberships(state, monkeypatch):
    manager = Mock()
    action = _action(manager)
    action._task.args.update(state=state, organizations=["Default"])
    monkeypatch.setattr(BaseResourceActionPlugin, "run", lambda self, tmp=None, task_vars=None: {"id": 7, "changed": False})

    action.run()

    manager.lookup_resource_id.assert_not_called()
    manager.execute.assert_not_called()
