# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the import action plugin's change tracking."""

from __future__ import absolute_import, division, print_function

from importlib import import_module
from unittest.mock import MagicMock, Mock, call

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


def test_import_preserves_authenticator_type(action):
    manager = Mock()
    action._prepare_action = Mock(
        return_value={
            "result": {},
            "validated_params": {
                "assets": {
                    "authenticators": [
                        {
                            "id": 7,
                            "name": "OIDC",
                            "type": "ansible_base.authentication.authenticator_plugins.oidc",
                            "url": "/api/gateway/v1/authenticators/7/",
                        }
                    ]
                }
            },
            "manager": manager,
        }
    )
    action._import_single_resource = Mock(return_value=False)
    action._import_inventory_children = Mock(return_value=({"changed": 0, "ok": 0, "failed": 0}, {"changed": 0, "ok": 0, "failed": 0}))
    action._display = Mock()
    action._play_context = Mock(check_mode=False)

    result = action.run()

    assert result["failed"] is False
    action._import_single_resource.assert_called_once_with(
        manager,
        "authenticator",
        {"name": "OIDC", "type": "ansible_base.authentication.authenticator_plugins.oidc"},
        {},
    )


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
        "ansible_data": {"role_definition": "31", "object_id": 42, "user_id": 7},
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
    if module_name == "controller_project":
        manager.search_api.side_effect = [
            {"results": []},
            {"id": 42, "name": resource_data["name"], "scm_type": resource_data["scm_type"]},
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


def test_import_skips_write_only_tokens(action):
    action._prepare_action = Mock(
        return_value={
            "result": {},
            "validated_params": {"assets": {"tokens": [{"description": "one", "scope": "write"}]}},
            "manager": Mock(),
        }
    )
    action._import_inventory_children = Mock(return_value=({"changed": 0, "ok": 0, "failed": 0}, {"changed": 0, "ok": 0, "failed": 0}))
    action._display = Mock()
    action._play_context = Mock(check_mode=False)

    result = action.run()

    assert result["failed"] is False
    assert result["changed"] is False
    assert result["results"]["tokens"]["skipped"] == 1


def test_build_role_assignment_cache_fetches_target_resources():
    manager = Mock()

    def search_api(**kwargs):
        endpoint = kwargs.get("endpoint")
        query = kwargs.get("query_params", {})
        if endpoint == "api/gateway/v1/role_definitions/":
            return {"results": [{"name": "Team Member", "id": 1}, {"name": "Org Admin", "id": 2}]}
        if endpoint == "api/gateway/v1/users/":
            username = query["username"]
            return {"results": [{"username": username, "id": {"alice": 10, "bob": 11}[username]}]}
        if endpoint == "api/gateway/v1/organizations/":
            return {"results": [{"name": "Default", "id": 100}]}
        if endpoint == "api/controller/v2/organizations/":
            return {"results": [{"name": "Default", "id": 200}]}
        if endpoint == "api/gateway/v1/teams/":
            return {"results": [{"name": "DevTeam", "id": 50, "organization": 100}]}
        if endpoint == "/api/controller/v2/projects/":
            return {"results": [{"name": "Demo Project", "id": 300, "organization": 200}]}
        raise AssertionError("unexpected endpoint: %s" % endpoint)

    manager.search_api.side_effect = search_api
    action = ActionModule.__new__(ActionModule)
    action._display = Mock()

    assets = {
        "role_user_assignments": [
            {"role_definition": "Team Member", "user": "alice", "object_name": "DevTeam", "object_type": "teams", "organization": "Default"},
            {"role_definition": "Org Admin", "user": "bob", "object_name": "Demo Project", "object_type": "awx.project", "organization": "Default"},
        ],
    }
    cache = action._build_role_assignment_cache(manager, assets)

    assert cache["role_definitions"] == {"Team Member": 1, "Org Admin": 2}
    assert cache["users"] == {"alice": 10, "bob": 11}
    assert cache["gateway_orgs"] == {"Default": 100}
    assert cache["controller_orgs"] == {"Default": 200}
    assert cache["teams"] == {("DevTeam", 100): 50}
    assert cache["awx.project"] == {("Demo Project", 200): 300}


def test_build_role_assignment_cache_resolves_numeric_usernames(action):
    manager = Mock()

    def search_api(**kwargs):
        endpoint = kwargs.get("endpoint")
        query = kwargs.get("query_params", {})
        if endpoint == "api/gateway/v1/role_definitions/":
            return {"results": []}
        if endpoint == "api/gateway/v1/users/":
            assert query == {"username": "123"}
            return {"results": [{"username": "123", "id": 77}]}
        if endpoint in ("api/gateway/v1/organizations/", "api/controller/v2/organizations/", "api/gateway/v1/teams/"):
            return {"results": []}
        raise AssertionError("unexpected endpoint: %s" % endpoint)

    manager.search_api.side_effect = search_api
    action._display = Mock()

    cache = action._build_role_assignment_cache(
        manager,
        {"role_user_assignments": [{"user": "123"}], "role_team_assignments": None},
    )

    assert cache["users"] == {"123": 77}
    resolved = action._pre_resolve_role_assignment({"user": "123"}, cache, "role_user_assignments")
    assert resolved["user_id"] == 77
    assert "user" not in resolved


def test_build_role_assignment_cache_uses_credential_type_names(action):
    manager = Mock()

    def search_api(**kwargs):
        endpoint = kwargs.get("endpoint")
        if endpoint == "api/gateway/v1/role_definitions/":
            return {"results": []}
        if endpoint == "api/gateway/v1/organizations/":
            return {"results": []}
        if endpoint == "api/controller/v2/organizations/":
            return {"results": [{"name": "Default", "id": 200}]}
        if endpoint == "api/gateway/v1/teams/":
            return {"results": []}
        if endpoint == "api/controller/v2/credential_types/":
            return {"results": [{"id": 3, "name": "Cloud"}]}
        if endpoint == "/api/controller/v2/credentials/":
            return {"results": [{"name": "Shared", "id": 9, "organization": 200, "credential_type": 3}]}
        raise AssertionError("unexpected endpoint: %s" % endpoint)

    manager.search_api.side_effect = search_api
    action._display = Mock()

    assets = {
        "role_user_assignments": [
            {
                "object_name": "Shared",
                "object_type": "awx.credential",
                "organization": "Default",
                "object_credential_type": "Cloud",
            }
        ]
    }
    cache = action._build_role_assignment_cache(manager, assets)

    assert cache["awx.credential"] == {("Shared", 200, "Cloud"): 9}
    resolved = action._pre_resolve_role_assignment(assets["role_user_assignments"][0], cache, "role_user_assignments")
    assert resolved["object_id"] == 9
    assert "object_name" not in resolved


def test_build_role_assignment_cache_skips_eda_objects(action):
    manager = Mock()
    manager.search_api.side_effect = [
        {"results": []},
        {"results": []},
        {"results": []},
        {"results": []},
        {"results": []},
    ]
    action._display = Mock()

    action._build_role_assignment_cache(
        manager,
        {"role_user_assignments": [{"object_name": "Activation", "object_type": "eda.activation"}]},
    )

    called_endpoints = [call.kwargs.get("endpoint") for call in manager.search_api.call_args_list]
    assert all(not (endpoint or "").startswith("/api/eda/") for endpoint in called_endpoints)


def test_import_skips_null_role_assignment_collections(action):
    manager = Mock()
    action._prepare_action = Mock(
        return_value={
            "result": {},
            "validated_params": {
                "assets": {
                    "role_user_assignments": [{"user": "123"}],
                    "role_team_assignments": None,
                }
            },
            "manager": manager,
        }
    )
    action._build_role_assignment_cache = Mock(return_value={"users": {"123": 77}})
    action._import_single_resource = Mock(return_value=False)
    action._import_inventory_children = Mock(return_value=({"changed": 0, "ok": 0, "failed": 0}, {"changed": 0, "ok": 0, "failed": 0}))
    action._display = Mock()
    action._play_context = Mock(check_mode=False)

    result = action.run()

    assert result["failed"] is False
    assert result["results"]["role_user_assignments"]["ok"] == 1
    assert "role_team_assignments" not in result["results"]
    action._import_single_resource.assert_called_once_with(manager, "role_user_assignment", {"user_id": 77}, {})


def test_role_cache_failure_keeps_selectors_and_continues_import(action):
    user_assignment = {"user": "alice", "role_definition": "Org Admin", "object_name": "Production", "object_type": "organizations"}
    team_assignment = {
        "team": "Platform",
        "team_organization": "Production",
        "role_definition": "Org Admin",
        "assignment_objects": [{"type": "organizations", "name": "Production"}],
    }
    assets = {
        "inventory": [{"name": "Production", "hosts": [{"name": "web"}]}],
        "role_user_assignments": [user_assignment],
        "role_team_assignments": [team_assignment],
    }

    def search_api(*, endpoint, **kwargs):
        if endpoint == "api/gateway/v1/teams/":
            raise ValueError("Team list exceeds the cache limit")
        return {"results": []}

    manager = Mock()
    manager.search_api.side_effect = search_api
    action._prepare_action = Mock(return_value={"result": {}, "validated_params": {"assets": assets}, "manager": manager})
    action._import_single_resource = Mock(side_effect=[True, ValueError("Assignment rejected"), True, True])
    action._display = Mock(verbosity=0)
    action._play_context = Mock(check_mode=False)

    result = action.run()

    assert action._import_single_resource.call_args_list == [
        call(manager, "inventory", {"name": "Production"}, {}),
        call(manager, "role_user_assignment", user_assignment, {}),
        call(manager, "role_team_assignment", team_assignment, {}),
        call(manager, "host", {"name": "web", "inventory": "Production"}, {}),
    ]
    assert [entry.kwargs["endpoint"] for entry in manager.search_api.call_args_list].count("api/gateway/v1/teams/") == 1
    assert result == {
        "changed": True,
        "failed": True,
        "results": {
            "inventory": {"changed": 1, "ok": 0, "failed": 0},
            "role_user_assignments": {"changed": 0, "ok": 0, "failed": 1},
            "role_team_assignments": {"changed": 1, "ok": 0, "failed": 0},
            "hosts": {"changed": 1, "ok": 0, "failed": 0},
        },
        "failed_resources": [{"type": "role_user_assignments", "name": "unknown", "error": "Assignment rejected"}],
        "msg": "1 resource(s) failed to import.",
    }


def test_pre_resolve_role_user_assignment_replaces_names_with_ids():
    action = ActionModule.__new__(ActionModule)
    action._display = Mock()

    cache = {
        "role_definitions": {"Team Member": 1},
        "users": {"alice": 10},
        "gateway_orgs": {"Eng": 100},
        "teams": {("DevTeam", 100): 50},
        "teams_unscoped": {"DevTeam": 50},
    }
    clean_data = {
        "role_definition": "Team Member",
        "user": "alice",
        "object_name": "DevTeam",
        "object_type": "teams",
        "organization": "Eng",
    }
    resolved = action._pre_resolve_role_assignment(clean_data, cache, "role_user_assignments")

    assert resolved["role_definition"] == 1
    assert resolved["user_id"] == 10
    assert "user" not in resolved
    assert resolved["object_id"] == 50
    assert "object_name" not in resolved
    assert "object_type" not in resolved
    assert "organization" not in resolved


def test_pre_resolve_falls_back_on_cache_miss():
    action = ActionModule.__new__(ActionModule)
    action._display = Mock()

    cache = {
        "role_definitions": {"Team Member": 1},
        "users": {},
        "gateway_orgs": {},
        "teams": {},
        "teams_unscoped": {},
    }
    clean_data = {
        "role_definition": "Team Member",
        "user": "unknown_user",
        "object_name": "MissingTeam",
        "object_type": "teams",
        "organization": "MissingOrg",
    }
    resolved = action._pre_resolve_role_assignment(clean_data, cache, "role_user_assignments")

    assert resolved["role_definition"] == 1
    assert resolved["user"] == "unknown_user"
    assert resolved["object_name"] == "MissingTeam"
    assert resolved["object_type"] == "teams"
    assert "object_id" not in resolved


def test_pre_resolve_role_team_assignment_resolves_assignment_objects():
    action = ActionModule.__new__(ActionModule)
    action._display = Mock()

    cache = {
        "role_definitions": {"Team Admin": 2},
        "gateway_orgs": {"Eng": 100},
        "controller_orgs": {},
        "teams": {("Platform", 100): 60},
        "teams_unscoped": {"Platform": 60},
    }
    clean_data = {
        "role_definition": "Team Admin",
        "team": "Platform",
        "assignment_objects": [{"name": "Eng", "type": "organizations"}],
    }
    resolved = action._pre_resolve_role_assignment(clean_data, cache, "role_team_assignments")

    assert resolved["role_definition"] == 2
    assert resolved["team"] == 60
    assert resolved["assignment_objects"] == [{"object_id": 100}]


def test_pre_resolve_controller_object_with_org_scope():
    action = ActionModule.__new__(ActionModule)
    action._display = Mock()

    cache = {
        "role_definitions": {"Inventory Admin": 5},
        "users": {"carol": 30},
        "gateway_orgs": {},
        "controller_orgs": {"Production": 200},
        "awx.inventory": {("Prod Hosts", 200): 400},
        "awx.inventory:unscoped": {"Prod Hosts": 400},
    }
    clean_data = {
        "role_definition": "Inventory Admin",
        "user": "carol",
        "object_name": "Prod Hosts",
        "object_type": "awx.inventory",
        "organization": "Production",
    }
    resolved = action._pre_resolve_role_assignment(clean_data, cache, "role_user_assignments")

    assert resolved["object_id"] == 400
    assert "object_name" not in resolved
