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
