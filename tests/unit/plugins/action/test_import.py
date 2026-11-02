# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the import action plugin's change tracking."""

from __future__ import absolute_import, division, print_function

from importlib import import_module
from unittest.mock import Mock

import pytest

ActionModule = import_module("ansible_collections.ansible.platform.plugins.action.import").ActionModule


@pytest.fixture
def action():
    return ActionModule.__new__(ActionModule)


def test_existing_resource_uses_update_changed_result(action):
    manager = Mock()
    manager.execute.side_effect = [
        {"id": 42, "name": "Example"},
        {"changed": False, "id": 42, "name": "Example"},
    ]

    changed = action._import_single_resource(manager, "organization", {"name": "Example"})

    assert changed is False
    manager.execute.assert_any_call(
        operation="update",
        module_name="organization",
        ansible_data={"name": "Example", "id": 42},
    )


def test_missing_resource_returns_create_changed_result(action):
    manager = Mock()
    manager.execute.side_effect = [ValueError("Resource with name=Example not found"), {"changed": True, "id": 42}]

    changed = action._import_single_resource(manager, "organization", {"name": "Example"})

    assert changed is True
    manager.execute.assert_any_call(
        operation="create",
        module_name="organization",
        ansible_data={"name": "Example"},
    )


def test_find_errors_other_than_not_found_are_not_silenced(action):
    manager = Mock()
    manager.execute.side_effect = ValueError("permission denied")

    with pytest.raises(ValueError, match="permission denied"):
        action._import_single_resource(manager, "organization", {"name": "Example"})


def test_missing_manager_changed_flag_is_rejected(action):
    manager = Mock()
    manager.execute.side_effect = [ValueError("Resource with name=Example not found"), {"id": 42}]

    with pytest.raises(ValueError, match="explicit changed flag"):
        action._import_single_resource(manager, "organization", {"name": "Example"})


def test_inventory_children_create_groups_before_associations(action):
    action._import_single_resource = Mock(side_effect=[False, False])
    manager = Mock()
    manager.execute.side_effect = [{"id": 10}, {"id": 11}]
    manager.manage_associations.return_value = False
    failed_resources = []
    inventory = [
        {
            "name": "Production",
            "groups": [
                {"name": "parent", "children": ["child"]},
                {"name": "child"},
            ],
        }
    ]

    hosts, groups = action._import_inventory_children(manager, inventory, False, failed_resources)

    assert hosts == {"changed": 0, "ok": 0, "failed": 0}
    assert groups == {"changed": 0, "ok": 2, "failed": 0}
    assert [call.args[1] for call in action._import_single_resource.call_args_list] == ["group", "group"]
    assert manager.manage_associations.call_args_list[0].args[:4] == ("groups", 10, "children", ["child"])
    assert failed_resources == []


def test_inventory_children_second_import_is_idempotent(action):
    manager = Mock()
    manager.execute.return_value = {"id": 10}
    manager.manage_associations.return_value = False
    failed_resources = []
    inventory = [{"name": "Production", "groups": [{"name": "web", "hosts": ["web01"]}]}]

    action._import_single_resource = Mock(return_value=False)
    first_hosts, first_groups = action._import_inventory_children(manager, inventory, False, failed_resources)
    second_hosts, second_groups = action._import_inventory_children(manager, inventory, False, failed_resources)

    assert first_hosts == second_hosts == {"changed": 0, "ok": 0, "failed": 0}
    assert first_groups == second_groups == {"changed": 0, "ok": 1, "failed": 0}
    assert manager.manage_associations.call_count == 2
    assert failed_resources == []


def test_inventory_children_association_failure_is_reported(action):
    manager = Mock()
    manager.execute.return_value = {"id": 10}
    manager.manage_associations.side_effect = RuntimeError("association failed")
    failed_resources = []
    inventory = [{"name": "Production", "groups": [{"name": "web", "hosts": ["web01"]}]}]

    action._import_single_resource = Mock(return_value=False)
    hosts, groups = action._import_inventory_children(manager, inventory, False, failed_resources)

    assert hosts == {"changed": 0, "ok": 0, "failed": 0}
    assert groups == {"changed": 0, "ok": 0, "failed": 1}
    assert failed_resources == [{"type": "groups", "name": "web", "error": "association failed"}]
