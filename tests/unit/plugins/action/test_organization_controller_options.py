"""Tests for Controller-owned organization options on the Gateway organization action."""

from __future__ import absolute_import, division, print_function

from unittest.mock import MagicMock, patch

import pytest
from ansible.playbook.task import Task
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.action.organization import (
    _CONTROLLER_ASSOCIATIONS,
    _CONTROLLER_SETTINGS,
    CONTROLLER_ORGANIZATION_PATH,
    ActionModule,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.organization import AnsibleOrganization
from ansible_collections.ansible.platform.plugins.plugin_utils.api.gateway.v1.organization import OrganizationTransformMixin_v1
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError


def _make_action():
    task = MagicMock(spec=Task)
    task.args = {"name": "Example"}
    task.check_mode = False
    task.async_val = 0
    task.environment = []
    return ActionModule(
        task=task,
        connection=MagicMock(),
        play_context=MagicMock(),
        loader=MagicMock(),
        templar=MagicMock(),
        shared_loader_obj=MagicMock(),
    )


def test_controller_organization_lookup_uses_shared_ansible_id():
    manager = MagicMock()
    manager.search_api.return_value = {
        "results": [
            {
                "id": 31,
                "summary_fields": {"resource": {"ansible_id": "org-uuid"}},
            }
        ]
    }

    result = ActionModule._find_controller_organization_id(manager, "org-uuid")

    assert result == 31
    manager.search_api.assert_called_once_with(
        CONTROLLER_ORGANIZATION_PATH,
        query_params={"resource__ansible_id": "org-uuid"},
        return_all=True,
        service="controller",
    )


def test_controller_organization_lookup_rejects_duplicate_shared_ids():
    manager = MagicMock()
    manager.search_api.return_value = {
        "results": [
            {"id": 31, "summary_fields": {"resource": {"ansible_id": "org-uuid"}}},
            {"id": 32, "summary_fields": {"resource": {"ansible_id": "org-uuid"}}},
        ]
    }

    with pytest.raises(ValueError, match="Expected one Controller organization"):
        ActionModule._find_controller_organization_id(manager, "org-uuid")


def test_optional_options_are_documented_without_defaults():
    action = _make_action()
    argument_spec = action._build_argspec_from_docs(action._get_documentation())["argument_spec"]
    expected_types = {
        "default_environment": "str",
        "max_hosts": "int",
        "instance_groups": "list",
        "notification_templates_started": "list",
        "notification_templates_success": "list",
        "notification_templates_error": "list",
        "notification_templates_approvals": "list",
        "galaxy_credentials": "list",
    }

    for field, expected_type in expected_types.items():
        assert argument_spec[field]["type"] == expected_type
        assert argument_spec[field].get("required", False) is False
        assert argument_spec[field].get("default") is None


def test_ansible_organization_model_has_no_controller_option_defaults():
    organization = AnsibleOrganization(name="Example")

    for field in (*_CONTROLLER_SETTINGS, *_CONTROLLER_ASSOCIATIONS):
        assert getattr(organization, field) is None


def test_prepare_action_uses_gateway_ansible_id_to_resolve_controller_org():
    action = _make_action()
    manager = MagicMock()
    manager.search_api.side_effect = [
        {"results": [{"id": 17, "name": "Example"}]},
        {"summary_fields": {"resource": {"ansible_id": "org-uuid"}}},
        {"results": [{"id": 31, "summary_fields": {"resource": {"ansible_id": "org-uuid"}}}]},
    ]
    manager.lookup_resource_id.return_value = 44
    prepared = {
        "validated_params": {
            "name": "Example",
            "state": "present",
            "default_environment": "Production EE",
            "max_hosts": 100,
        },
        "resource_data": {"name": "Example"},
        "write_only_data": {},
        "manager": manager,
    }

    with patch.object(BaseResourceActionPlugin, "_prepare_action", return_value=prepared):
        action._prepare_action(task_vars={})

    assert action._controller_organization_id == 31
    assert action._controller_update_template == CONTROLLER_ORGANIZATION_PATH + "/{id}/"
    assert action._controller_update == {"default_environment": 44, "max_hosts": 100}
    manager.lookup_resource_id.assert_called_once_with("execution_environments", "name", "Production EE", service="controller")
    assert manager.search_api.call_args_list[2].kwargs["query_params"] == {"resource__ansible_id": "org-uuid"}


def test_prepare_action_uses_gateway_list_ansible_id_without_detail_request():
    action = _make_action()
    manager = MagicMock()
    manager.search_api.side_effect = [
        {
            "results": [
                {
                    "id": 17,
                    "name": "Example",
                    "summary_fields": {"resource": {"ansible_id": "org-uuid"}},
                }
            ]
        },
        {"results": [{"id": 31, "summary_fields": {"resource": {"ansible_id": "org-uuid"}}}]},
    ]
    prepared = {
        "validated_params": {
            "name": "Example",
            "state": "present",
            "max_hosts": 100,
        },
        "resource_data": {"name": "Example"},
        "write_only_data": {},
        "manager": manager,
    }

    with patch.object(BaseResourceActionPlugin, "_prepare_action", return_value=prepared):
        action._prepare_action(task_vars={})

    assert action._controller_organization_id == 31
    assert manager.search_api.call_count == 2
    assert manager.search_api.call_args_list[1].kwargs["query_params"] == {"resource__ansible_id": "org-uuid"}


def test_prepare_action_reuses_gateway_result_for_base_find():
    action = _make_action()
    manager = MagicMock()
    manager.search_api.side_effect = [
        {
            "results": [
                {
                    "id": 17,
                    "name": "Example",
                    "description": "Managed by Gateway",
                    "summary_fields": {"resource": {"ansible_id": "org-uuid"}},
                }
            ]
        },
        {"results": [{"id": 31, "summary_fields": {"resource": {"ansible_id": "org-uuid"}}}]},
    ]
    prepared = {
        "validated_params": {"name": "Example", "state": "present", "max_hosts": 100},
        "resource_data": {"name": "Example"},
        "write_only_data": {},
        "manager": manager,
    }

    with patch.object(BaseResourceActionPlugin, "_prepare_action", return_value=prepared):
        action._prepare_action(task_vars={})

    gateway_result = action._find_existing_resource(manager, prepared["resource_data"])

    assert gateway_result["id"] == 17
    assert gateway_result["name"] == "Example"
    assert gateway_result["description"] == "Managed by Gateway"
    manager.execute.assert_not_called()
    assert manager.search_api.call_count == 2


def test_prepare_action_reuses_gateway_not_found_for_base_find():
    action = _make_action()
    manager = MagicMock()
    manager.search_api.return_value = {"results": []}
    prepared = {
        "validated_params": {"name": "Example", "state": "present", "max_hosts": 100},
        "resource_data": {"name": "Example"},
        "write_only_data": {},
        "manager": manager,
    }

    with patch.object(BaseResourceActionPlugin, "_prepare_action", return_value=prepared):
        action._prepare_action(task_vars={})

    assert action._find_existing_resource(manager, prepared["resource_data"]) == {}
    manager.execute.assert_not_called()
    manager.search_api.assert_called_once()


def test_controller_fields_are_not_in_gateway_endpoint_payloads():
    operations = OrganizationTransformMixin_v1.get_endpoint_operations()

    assert ActionModule._WRITE_ONLY_FIELDS == frozenset(_CONTROLLER_SETTINGS) | frozenset(_CONTROLLER_ASSOCIATIONS)
    assert operations["create"].fields == ["name", "description"]
    assert operations["update"].fields == ["name", "description"]


def test_omitted_association_is_not_reconciled():
    action = _make_action()
    action._client = MagicMock()
    action._controller_settings = {}
    action._controller_associations = {}

    with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "failed": False}):
        result = action.run(task_vars={})

    assert result["changed"] is False
    action._client.manage_associations.assert_not_called()


def test_explicit_empty_association_is_reconciled_in_check_mode():
    action = _make_action()
    action._task.check_mode = True
    action._client = MagicMock()
    action._controller_organization_id = 31
    action._controller_update_template = CONTROLLER_ORGANIZATION_PATH + "/{id}/"
    action._controller_update = {}
    action._controller_settings = {}
    action._controller_associations = {"instance_groups": []}
    action._client.manage_associations.return_value = True

    with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "failed": False}):
        result = action.run(task_vars={})

    assert result["changed"] is True
    action._client.manage_associations.assert_called_once_with(
        CONTROLLER_ORGANIZATION_PATH,
        31,
        "instance_groups",
        [],
        "instance_groups",
        "name",
        service="controller",
        check_mode=True,
    )
    action._client.direct_request.assert_not_called()


def test_controller_update_preserves_gateway_id_in_result():
    action = _make_action()
    action._client = MagicMock()
    action._controller_organization_id = 31
    action._controller_update_template = CONTROLLER_ORGANIZATION_PATH + "/{id}/"
    action._controller_update = {"max_hosts": 100}
    action._controller_settings = {"max_hosts": 100}
    action._controller_associations = {}
    action._client.search_api.return_value = {"max_hosts": 10}
    gateway_result = {"id": 17, "organization": {"id": 17}, "changed": False, "failed": False}

    with patch.object(BaseResourceActionPlugin, "run", return_value=gateway_result):
        result = action.run(task_vars={})

    assert result["id"] == 17
    assert result["organization"]["id"] == 17
    action._client.direct_request.assert_called_once_with(
        "PATCH",
        CONTROLLER_ORGANIZATION_PATH + "/31/",
        data={"max_hosts": 100},
    )


def test_controller_validation_error_fails_the_action():
    action = _make_action()
    action._client = MagicMock()
    action._controller_organization_id = 31
    action._controller_update_template = CONTROLLER_ORGANIZATION_PATH + "/{id}/"
    action._controller_update = {"max_hosts": -1}
    action._controller_settings = {"max_hosts": -1}
    action._controller_associations = {}
    action._client.search_api.return_value = {"max_hosts": 10}
    action._client.direct_request.side_effect = APIError("API request failed: HTTP 400", status_code=400)

    with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "failed": False}):
        result = action.run(task_vars={})

    assert result["failed"] is True
    assert "HTTP 400" in result["msg"]
    action._client.direct_request.assert_called_once_with(
        "PATCH",
        CONTROLLER_ORGANIZATION_PATH + "/31/",
        data={"max_hosts": -1},
    )
