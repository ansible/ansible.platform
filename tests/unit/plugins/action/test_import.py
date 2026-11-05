# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the import action plugin's change tracking."""

from __future__ import absolute_import, division, print_function

from importlib import import_module
from unittest.mock import MagicMock, Mock

import pytest
from ansible.plugins import loader as plugin_loaders

ActionModule = import_module("ansible_collections.ansible.platform.plugins.action.import").ActionModule


@pytest.fixture
def action():
    return ActionModule.__new__(ActionModule)


def _stub_resource_action_dispatch(action, child_action):
    resource_task = Mock()
    action._task = Mock()
    action._task.copy.return_value = resource_task
    action._connection = Mock()
    action._play_context = Mock()
    action._loader = Mock()
    action._templar = Mock()
    action._shared_loader_obj = Mock()
    action._shared_loader_obj.action_loader.get.return_value = child_action
    return resource_task


def test_import_dispatches_full_resource_data_to_resource_action(action):
    manager = Mock()
    child_action = Mock()
    child_action.run.return_value = {"changed": True, "id": 42}
    resource_task = _stub_resource_action_dispatch(action, child_action)
    resource_data = {"name": "Example", "credentials": ["Build"], "survey_spec": {"name": "Survey"}}

    changed = action._import_single_resource(manager, "job_template", resource_data, {"gateway_hostname": "gateway"})

    assert changed is True
    assert resource_task.action == "ansible.platform.job_template"
    assert resource_task.args == resource_data
    action._shared_loader_obj.action_loader.get.assert_called_once_with(
        "ansible.platform.job_template",
        resource_task,
        action._connection,
        action._play_context,
        action._loader,
        action._templar,
        action._shared_loader_obj,
    )
    assert child_action._manager_override is manager
    child_action.run.assert_called_once_with(task_vars={"gateway_hostname": "gateway"})


def test_import_strips_api_only_fields_from_legacy_resource_data(action):
    manager = Mock()
    action._prepare_action = Mock(
        return_value={
            "result": {},
            "validated_params": {"assets": {"projects": [{"name": "Demo", "organization_ids": [1], "scm_revision": "abc123"}]}},
            "manager": manager,
        }
    )
    action._import_single_resource = Mock(return_value=False)
    action._import_inventory_children = Mock(return_value=({"changed": 0, "ok": 0, "failed": 0}, {"changed": 0, "ok": 0, "failed": 0}))
    action._display = Mock()
    action._play_context = Mock(check_mode=False)

    result = action.run()

    assert result["failed"] is False
    action._import_single_resource.assert_called_once_with(manager, "controller_project", {"name": "Demo"}, {})


def test_job_template_import_runs_real_action_and_reconciles_exported_fields(action):
    manager = Mock()
    manager.execute.side_effect = [
        ValueError("Resource with name=Ping not found"),
        {"id": 42, "name": "Ping", "changed": True},
    ]
    manager.manage_associations.return_value = True
    manager.manage_sub_resource.return_value = True

    resource_task = MagicMock()
    resource_task.async_val = 0
    resource_task.check_mode = False
    resource_task.args = {}
    action._task = MagicMock()
    action._task.copy.return_value = resource_task
    action._connection = MagicMock()
    action._connection._shell.tmpdir = "/tmp"
    action._play_context = MagicMock()
    action._loader = MagicMock()
    action._templar = MagicMock()
    action._shared_loader_obj = plugin_loaders

    result = action._run_resource_action(
        manager,
        "job_template",
        {"name": "Ping", "credentials": ["Local"], "survey_spec": {"name": "Survey"}},
        {},
    )

    assert result["changed"] is True
    create_call = next(call.kwargs for call in manager.execute.call_args_list if call.kwargs.get("operation") == "create")
    assert create_call["module_name"] == "job_template"
    assert create_call["ansible_data"]["name"] == "Ping"
    assert "credentials" not in create_call["ansible_data"]
    assert manager.manage_associations.call_args.args[2:4] == ("credentials", ["Local"])
    manager.manage_sub_resource.assert_called_once()


def test_job_template_import_preserves_explicit_nulls_without_clearing_omitted_fields(action):
    manager = Mock()
    manager.execute.side_effect = [
        {"id": 42, "name": "Ping", "description": "Existing description"},
        {"id": 42, "name": "Ping", "description": None, "changed": True},
    ]
    resource_task = MagicMock()
    resource_task.async_val = 0
    resource_task.check_mode = False
    resource_task.args = {}
    action._task = MagicMock()
    action._task.copy.return_value = resource_task
    action._connection = MagicMock()
    action._connection._shell.tmpdir = "/tmp"
    action._play_context = MagicMock()
    action._loader = MagicMock()
    action._templar = MagicMock()
    action._shared_loader_obj = plugin_loaders

    result = action._run_resource_action(manager, "job_template", {"name": "Ping", "description": None}, {})

    assert result["changed"] is True
    update_call = next(call.kwargs for call in manager.execute.call_args_list if call.kwargs.get("operation") == "update")
    assert update_call["ansible_data"] == {"name": "Ping", "description": None, "id": 42, "_platform_enforced": True}


def test_user_import_reconciles_exported_organization_memberships(action):
    manager = Mock()
    manager.execute.side_effect = [
        ValueError("Resource with name=alice not found"),
        {"id": 7, "username": "alice", "changed": True},
        ValueError("Resource with name=Organization Member not found"),
        {"id": 99, "changed": True},
    ]
    manager.lookup_resource_id.side_effect = [31, 42]
    resource_task = MagicMock()
    resource_task.async_val = 0
    resource_task.check_mode = False
    resource_task.args = {}
    action._task = MagicMock()
    action._task.copy.return_value = resource_task
    action._connection = MagicMock()
    action._connection._shell.tmpdir = "/tmp"
    action._play_context = MagicMock()
    action._loader = MagicMock()
    action._templar = MagicMock()
    action._shared_loader_obj = plugin_loaders

    result = action._run_resource_action(manager, "user", {"username": "alice", "organizations": ["Default"]}, {})

    assert result["changed"] is True
    manager.lookup_resource_id.assert_any_call("role_definitions", "name", "Organization Member", service="gateway")
    manager.lookup_resource_id.assert_any_call("organizations", "name", "Default", service="gateway")
    assert manager.execute.call_args_list[3].kwargs == {
        "operation": "create",
        "module_name": "role_user_assignment",
        "ansible_data": {"role_definition": "31", "object_id": 42, "user": "7"},
    }


@pytest.mark.parametrize(
    ("module_name", "resource_data", "association_field"),
    [
        (
            "schedule",
            {
                "name": "Weekly",
                "rrule": "DTSTART:20261007T120000Z RRULE:FREQ=WEEKLY;INTERVAL=1;COUNT=10",
                "unified_job_template": "Example",
                "credentials": ["Machine"],
            },
            "credentials",
        ),
        (
            "controller_project",
            {"name": "Demo Project", "scm_type": "manual", "notification_templates_started": ["Email"]},
            "notification_templates_started",
        ),
        (
            "inventory_source",
            {"name": "Cloud Inventory", "inventory": "Production", "source": "ec2", "notification_templates_success": ["Email"]},
            "notification_templates_success",
        ),
    ],
)
def test_import_runs_association_resource_actions(module_name, resource_data, association_field):
    """Resource action plugins must own association fields during import."""
    action = ActionModule.__new__(ActionModule)
    manager = Mock()
    manager.execute.side_effect = [ValueError("Resource with name=Example not found"), {"id": 42, "name": resource_data["name"], "changed": True}]
    manager.manage_associations.return_value = True

    resource_task = MagicMock()
    resource_task.async_val = 0
    resource_task.check_mode = False
    resource_task.args = {}
    action._task = MagicMock()
    action._task.copy.return_value = resource_task
    action._connection = MagicMock()
    action._connection._shell.tmpdir = "/tmp"
    action._play_context = MagicMock()
    action._loader = MagicMock()
    action._templar = MagicMock()
    action._shared_loader_obj = plugin_loaders

    result = action._run_resource_action(manager, module_name, resource_data, {})

    assert result["changed"] is True
    create_call = next(call.kwargs for call in manager.execute.call_args_list if call.kwargs.get("operation") == "create")
    assert association_field not in create_call["ansible_data"]
    association_call = manager.manage_associations.call_args
    assert association_call.args[2] == association_field
    assert association_call.args[3] == resource_data[association_field]
    assert association_call.kwargs["service"] == "controller"


def test_resource_action_failure_is_reported(action):
    child_action = Mock()
    child_action.run.return_value = {"failed": True, "msg": "association failed"}
    _stub_resource_action_dispatch(action, child_action)

    with pytest.raises(ValueError, match="association failed"):
        action._run_resource_action(Mock(), "job_template", {"name": "Example"}, {})


def test_resource_action_must_report_changed(action):
    child_action = Mock()
    child_action.run.return_value = {"id": 42}
    _stub_resource_action_dispatch(action, child_action)

    with pytest.raises(ValueError, match="explicit changed flag"):
        action._run_resource_action(Mock(), "organization", {"name": "Example"}, {})


def test_resource_action_uses_the_injected_manager(action):
    from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin

    manager = Mock()
    child_action = Mock(_manager_override=manager)

    assert BaseResourceActionPlugin._get_or_spawn_manager(child_action, {}) == (manager, None)


def test_inventory_children_create_groups_before_associations(action):
    action._run_resource_action = Mock(side_effect=[{"id": 10, "changed": False}, {"id": 11, "changed": False}])
    manager = Mock()
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

    hosts, groups = action._import_inventory_children(manager, inventory, False, failed_resources, {})

    assert hosts == {"changed": 0, "ok": 0, "failed": 0}
    assert groups == {"changed": 0, "ok": 2, "failed": 0}
    assert [call.args[1] for call in action._run_resource_action.call_args_list] == ["group", "group"]
    assert manager.manage_associations.call_args_list[0].args[:4] == ("groups", 10, "children", ["child"])
    assert failed_resources == []


def test_inventory_children_second_import_is_idempotent(action):
    manager = Mock()
    manager.execute.return_value = {"id": 10}
    manager.manage_associations.return_value = False
    failed_resources = []
    inventory = [{"name": "Production", "groups": [{"name": "web", "hosts": ["web01"]}]}]

    action._run_resource_action = Mock(return_value={"id": 10, "changed": False})
    first_hosts, first_groups = action._import_inventory_children(manager, inventory, False, failed_resources, {})
    second_hosts, second_groups = action._import_inventory_children(manager, inventory, False, failed_resources, {})

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

    action._run_resource_action = Mock(return_value={"id": 10, "changed": False})
    hosts, groups = action._import_inventory_children(manager, inventory, False, failed_resources, {})

    assert hosts == {"changed": 0, "ok": 0, "failed": 0}
    assert groups == {"changed": 0, "ok": 0, "failed": 1}
    assert failed_resources == [{"type": "groups", "name": "web", "error": "association failed"}]


def test_inventory_group_check_mode_reports_association_change_without_writing(action):
    manager = Mock()
    action._run_resource_action = Mock(return_value={"changed": True, "id": None})
    failed_resources = []
    inventory = [{"name": "Production", "groups": [{"name": "web", "children": ["api"]}]}]

    hosts, groups = action._import_inventory_children(manager, inventory, True, failed_resources, {})

    assert hosts == {"changed": 0, "ok": 0, "failed": 0}
    assert groups == {"changed": 1, "ok": 0, "failed": 0}
    manager.manage_associations.assert_not_called()
    assert failed_resources == []


def test_malformed_resource_collection_is_reported(action):
    action._prepare_action = Mock(
        return_value={
            "result": {},
            "validated_params": {"assets": {"organizations": {"name": "Example"}}},
            "manager": Mock(),
        }
    )
    action._display = Mock()
    action._play_context = Mock(check_mode=False)

    result = action.run()

    assert result["failed"] is True
    assert result["results"]["organizations"]["failed"] == 1
    assert result["failed_resources"][0]["error"] == "Expected a list of resource dictionaries."


def test_malformed_resource_item_is_reported(action):
    action._prepare_action = Mock(
        return_value={
            "result": {},
            "validated_params": {"assets": {"organizations": ["not-a-dict"]}},
            "manager": Mock(),
        }
    )
    action._display = Mock()
    action._play_context = Mock(check_mode=False)

    result = action.run()

    assert result["failed"] is True
    assert result["results"]["organizations"]["failed"] == 1
    assert result["failed_resources"][0]["name"] == "[0]"
