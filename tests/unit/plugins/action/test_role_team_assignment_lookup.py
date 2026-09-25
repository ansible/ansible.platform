# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import asdict
from unittest.mock import MagicMock

import pytest
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.role_team_assignment import (
    AnsibleRoleTeamAssignment,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.role_team_assignment import (
    APIRoleTeamAssignment_v1,
    RoleTeamAssignmentTransformMixin_v1,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.resource_type_map import (
    get_expected_assignment_type,
    service_kind,
)


def _service():
    service = PlatformService.__new__(PlatformService)
    service.record_activity = MagicMock()
    service.loader = MagicMock()
    service.loader.load_classes_for_module.return_value = (
        AnsibleRoleTeamAssignment,
        APIRoleTeamAssignment_v1,
        RoleTeamAssignmentTransformMixin_v1,
    )
    service.session = MagicMock()
    service.cache = {}
    service.api_version = "1"
    service.search_api = MagicMock()
    service.lookup_resource_id = MagicMock()
    service._execute_operations = MagicMock(return_value={"id": 44, "role_definition": "5", "team": "7", "object_id": "202"})
    return service


def _resolve(service, object_lookup):
    return service.execute(
        operation="resolve",
        module_name="role_team_assignment",
        ansible_data_dict={"role_definition": "5", "object_lookup": object_lookup},
    )


def test_direct_client_supports_mixin_resolve_operation():
    client = DirectHTTPClient.__new__(DirectHTTPClient)
    client._authenticated = True
    client.api_version = "1"
    client.session = MagicMock()
    client.cache = {}
    client.loader = MagicMock()
    client.loader.load_classes_for_module.return_value = (
        AnsibleRoleTeamAssignment,
        APIRoleTeamAssignment_v1,
        RoleTeamAssignmentTransformMixin_v1,
    )
    client.search_api = MagicMock(return_value={"results": [{"id": 55, "name": "Build"}]})

    result = client.execute(
        operation="resolve",
        module_name="role_team_assignment",
        ansible_data={
            "role_definition": "5",
            "object_lookup": {"type": "awx.jobtemplate", "name": "Build"},
        },
    )

    assert result == {"object_id": "55"}


def test_lookup_metadata_is_not_part_of_serialized_assignment_model():
    assignment = AnsibleRoleTeamAssignment(
        role_definition="5",
        object_lookup={"type": "awx.jobtemplate", "name": "Build"},
    )

    assert "object_lookup" not in asdict(assignment)
    assert assignment._object_lookup == {"type": "awx.jobtemplate", "name": "Build"}


def test_service_kind_routes():
    assert service_kind("awx.jobtemplate") == "controller"
    assert service_kind("eda.project") == "eda"
    assert service_kind("galaxy.namespace") == "hub"
    assert service_kind("teams") == "gateway"


def test_get_expected_assignment_type_returns_content_type_directly():
    assert get_expected_assignment_type("eda.project") == "eda.project"
    assert get_expected_assignment_type("awx.project") == "awx.project"
    assert get_expected_assignment_type("awx.inventory") == "awx.inventory"
    assert get_expected_assignment_type("shared.organization") == "organizations"
    assert get_expected_assignment_type("shared.team") == "teams"


def test_execute_resolves_controller_object_with_exact_organization():
    service = _service()
    service.search_api.side_effect = [
        {"results": [{"id": 1, "name": "Preprod-copy"}, {"id": 2, "name": "Preprod"}]},
        {
            "results": [
                {"id": 101, "name": "mco - preprod-copy", "organization": 2},
                {"id": 202, "name": "mco - preprod", "organization": 2},
            ]
        },
    ]

    result = _resolve(
        service,
        {"type": "awx.jobtemplate", "name": "mco - preprod", "organization": "Preprod"},
    )

    assert result == {"object_id": "202"}
    assert service.search_api.call_args_list[0].args[0] == "/api/controller/v2/organizations/"
    assert service.search_api.call_args_list[1].kwargs["query_params"] == {
        "name": "mco - preprod",
        "organization": 2,
    }


def test_execute_resolves_eda_object_and_filters_organization():
    service = _service()
    service.search_api.side_effect = [
        {"results": [{"id": 8, "name": "EDA Org-copy"}, {"id": 9, "name": "EDA Org"}]},
        {
            "results": [
                {"id": 1, "name": "Demo", "organization_id": 1},
                {"id": 4, "name": "Demo-copy", "organization_id": 9},
                {"id": 5, "name": "Demo", "organization_id": 9},
            ]
        },
    ]

    result = _resolve(service, {"type": "eda.project", "name": "Demo", "organization": "EDA Org"})

    assert result == {"object_id": "5"}
    assert service.search_api.call_args_list[1].kwargs["query_params"] == {"name": "Demo"}


def test_execute_rejects_ambiguous_unscoped_controller_object():
    service = _service()
    service.search_api.return_value = {
        "results": [
            {"id": 101, "name": "mco - preprod", "organization": 1},
            {"id": 202, "name": "mco - preprod", "organization": 2},
        ]
    }

    with pytest.raises(ValueError, match="Expected exactly one"):
        _resolve(service, {"type": "awx.jobtemplate", "name": "mco - preprod"})


@pytest.mark.parametrize(
    "object_lookup, message",
    [
        ({"type": "galaxy.namespace", "name": "ns1", "organization": "Prod"}, "not supported for Hub"),
        (
            {"type": "awx.executionenvironment", "name": "ee", "organization": "Prod"},
            "not supported for Controller",
        ),
        ({"type": "organizations", "name": "Org", "organization": "Prod"}, "only supported for Gateway"),
    ],
)
def test_execute_rejects_unsupported_organization_scope(object_lookup, message):
    with pytest.raises(ValueError, match=message):
        _resolve(_service(), object_lookup)


def test_execute_resolves_gateway_team_with_exact_organization_match():
    service = _service()
    service.lookup_resource_id.return_value = 2
    service.search_api.return_value = {
        "data": [
            {"id": 10, "name": "Team-copy", "organization": 2},
            {"id": 11, "name": "Team", "organization": {"id": 2}},
        ]
    }

    result = _resolve(service, {"type": "teams", "name": "Team", "organization": "Production"})

    assert result == {"object_id": "11"}
    service.lookup_resource_id.assert_called_once_with("organizations", "name", "Production")
    service.search_api.assert_called_once_with("teams", query_params={"name": "Team", "organization": 2})


def test_resolved_id_flows_through_execute_without_lookup_metadata_in_api_payload():
    service = _service()
    service.search_api.return_value = {"results": [{"id": 202, "name": "Build"}]}
    resolved = _resolve(service, {"type": "awx.jobtemplate", "name": "Build"})

    service.execute(
        operation="create",
        module_name="role_team_assignment",
        ansible_data_dict={"role_definition": "5", "team": "7", **resolved},
    )

    api_data = service._execute_operations.call_args.args[1]
    assert asdict(api_data) == {
        "role_definition": "5",
        "team": "7",
        "team_ansible_id": None,
        "object_id": "202",
        "object_ansible_id": None,
        "id": None,
        "url": None,
        "created": None,
        "modified": None,
    }
