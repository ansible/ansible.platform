# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest
from ansible_collections.ansible.platform.plugins.module_utils.resource_type_map import (
    ASSIGNMENT_TYPE_PATH_MAP,
    get_expected_assignment_type,
    lookup_path_for,
)


# ---------------------------------------------------------------------------
# get_expected_assignment_type
# ---------------------------------------------------------------------------

def test_gateway_organization_maps_to_plural():
    assert get_expected_assignment_type("shared.organization") == "organizations"


def test_gateway_team_maps_to_plural():
    assert get_expected_assignment_type("shared.team") == "teams"


def test_eda_types_return_content_type_directly():
    assert get_expected_assignment_type("eda.project") == "eda.project"
    assert get_expected_assignment_type("eda.activation") == "eda.activation"
    assert get_expected_assignment_type("eda.edacredential") == "eda.edacredential"
    assert get_expected_assignment_type("eda.eventstream") == "eda.eventstream"
    assert get_expected_assignment_type("eda.decisionenvironment") == "eda.decisionenvironment"


def test_awx_types_return_content_type_directly():
    assert get_expected_assignment_type("awx.project") == "awx.project"
    assert get_expected_assignment_type("awx.inventory") == "awx.inventory"
    assert get_expected_assignment_type("awx.credential") == "awx.credential"
    assert get_expected_assignment_type("awx.jobtemplate") == "awx.jobtemplate"
    assert get_expected_assignment_type("awx.workflowjobtemplate") == "awx.workflowjobtemplate"
    assert get_expected_assignment_type("awx.executionenvironment") == "awx.executionenvironment"
    assert get_expected_assignment_type("awx.instancegroup") == "awx.instancegroup"
    assert get_expected_assignment_type("awx.notificationtemplate") == "awx.notificationtemplate"


def test_galaxy_types_return_content_type_directly():
    assert get_expected_assignment_type("galaxy.namespace") == "galaxy.namespace"
    assert get_expected_assignment_type("galaxy.collectionremote") == "galaxy.collectionremote"
    assert get_expected_assignment_type("galaxy.ansiblerepository") == "galaxy.ansiblerepository"
    assert get_expected_assignment_type("galaxy.containernamespace") == "galaxy.containernamespace"


def test_empty_content_type_returns_none():
    assert get_expected_assignment_type("") is None
    assert get_expected_assignment_type(None) is None


def test_unknown_content_type_raises():
    with pytest.raises(ValueError, match="Unknown content_type"):
        get_expected_assignment_type("unknown.type")


# ---------------------------------------------------------------------------
# lookup_path_for
# ---------------------------------------------------------------------------

def test_gateway_types_return_bare_name():
    assert lookup_path_for("organizations") == "organizations"
    assert lookup_path_for("teams") == "teams"


def test_eda_project_routes_to_eda_api():
    path = lookup_path_for("eda.project")
    assert path == "/api/eda/v1/projects/"
    assert path.startswith("/api/eda/")


def test_eda_activation_routes_to_eda_api():
    assert lookup_path_for("eda.activation") == "/api/eda/v1/activations/"


def test_awx_inventory_routes_to_controller_api():
    path = lookup_path_for("awx.inventory")
    assert path == "/api/controller/v2/inventories/"
    assert path.startswith("/api/controller/")


def test_awx_project_routes_to_controller_not_eda():
    # Ensures awx.project and eda.project resolve to different services
    assert lookup_path_for("awx.project") == "/api/controller/v2/projects/"
    assert lookup_path_for("eda.project") == "/api/eda/v1/projects/"
    assert lookup_path_for("awx.project") != lookup_path_for("eda.project")


def test_galaxy_namespace_routes_to_hub_api():
    path = lookup_path_for("galaxy.namespace")
    assert path == "/api/galaxy/v3/namespaces/"
    assert path.startswith("/api/galaxy/")


def test_all_non_gateway_paths_start_with_api():
    """build_url passes through any path starting with /api/ unchanged."""
    for assignment_type, path in ASSIGNMENT_TYPE_PATH_MAP.items():
        if assignment_type not in ("organizations", "teams"):
            assert path.startswith("/api/"), (
                "Expected full /api/ path for '%s' but got '%s'" % (assignment_type, path)
            )
