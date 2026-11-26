# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Constructed inventory option validation and check-mode behavior."""

from unittest.mock import Mock

import pytest
from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.inventory import ActionModule


@pytest.fixture
def inventory_action(monkeypatch):
    action = ActionModule.__new__(ActionModule)
    action._task = Mock(args={"name": "Constructed", "organization": "1", "kind": "constructed", "limit": ""}, check_mode=False, environment=[])
    action._display = Mock(verbosity=0)
    manager = Mock()
    monkeypatch.setattr(ActionBase, "run", lambda *args: {})
    monkeypatch.setattr(action, "_get_or_spawn_manager", Mock(return_value=(manager, None)))
    return action, manager


@pytest.mark.parametrize("kind", [None, "", "smart"])
def test_source_options_require_constructed_kind(inventory_action, kind):
    action, manager = inventory_action
    action._task.args["kind"] = kind

    result = action.run()

    assert (result["failed"], result["msg"], manager.mock_calls) == (True, "source_vars and limit require kind: constructed", [])


@pytest.mark.parametrize("name", ["Regular", "42"])
def test_source_options_reject_existing_regular_inventory(inventory_action, name):
    action, manager = inventory_action
    action._task.args["name"] = name
    manager.lookup_organization_names.return_value = []
    regular = {"id": 42, "kind": ""}
    manager.execute.side_effect = [regular] if name == "42" else [ValueError("Resource with name=Regular not found"), regular]

    result = action.run()

    assert (result["failed"], result["msg"], [call.kwargs["ansible_data"].get("limit") for call in manager.execute.call_args_list]) == (
        True,
        "source_vars and limit cannot be applied to an existing inventory that is not constructed",
        [None] if name == "42" else ["", None],
    )


def test_constructed_lookup_failure_does_not_fall_back(inventory_action):
    action, manager = inventory_action
    manager.lookup_organization_names.return_value = []
    manager.execute.side_effect = ValueError("Constructed inventory query failed")

    result = action.run()

    assert (result["failed"], result["msg"], manager.execute.call_count) == (True, "Constructed inventory query failed", 1)


def test_source_options_reject_copy_from_regular_inventory(inventory_action):
    action, manager = inventory_action
    action._task.args["copy_from"] = "Regular"
    manager.lookup_resource_id.return_value = 10
    manager.search_api.side_effect = [{"results": []}, {"id": 10, "kind": ""}]

    result = action.run()

    assert (result["failed"], result["msg"], manager.copy_resource.call_count) == (
        True,
        "Failed to copy from 'Regular': source_vars and limit require a constructed inventory as copy_from",
        0,
    )


@pytest.mark.parametrize(("stored_limit", "would_change"), [("123", True), ("", False)])
def test_constructed_inventory_check_mode_reads_source_without_writing(inventory_action, stored_limit, would_change):
    action, manager = inventory_action
    action._task.check_mode = True
    action._task.args["input_inventories"] = ["Input"]
    manager.lookup_organization_names.return_value = []
    current = {"id": 42, "name": "Constructed", "organization": "1", "kind": "constructed"}
    manager.execute.return_value = {**current, "limit": stored_limit}
    manager.manage_associations.return_value = False

    result = action.run()

    assert (result["failed"], result["changed"], [call.kwargs["operation"] for call in manager.execute.call_args_list]) == (
        False,
        would_change,
        ["find"],
    )
    manager.manage_associations.assert_called_once_with(
        "/api/controller/v2/inventories", 42, "input_inventories", ["Input"], "inventories", "name", service="controller", check_mode=True
    )
