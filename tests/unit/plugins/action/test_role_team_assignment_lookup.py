# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock

import pytest

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.role_team_assignment import (
    ActionModule,
    _get_expected_endpoint,
    _matches_org,
    _service_kind,
)


def test_service_kind_routes():
    assert _service_kind("job_templates") == "controller"
    assert _service_kind("eda_projects") == "eda"
    assert _service_kind("namespaces") == "hub"
    assert _service_kind("teams") == "gateway"


def test_get_expected_endpoint_eda_override():
    assert _get_expected_endpoint("eda.project") == "eda_projects"
    assert _get_expected_endpoint("awx.project") == "projects"


def test_matches_org_accepts_id_or_nested():
    assert _matches_org({"organization_id": 2}, 2)
    assert _matches_org({"organization": {"id": 2}}, "2")
    assert not _matches_org({"organization_id": 1}, 2)


def _action():
    # Bypass Ansible ActionBase init; only exercise lookup helpers.
    return ActionModule.__new__(ActionModule)


def test_resolve_named_object_controller_with_organization():
    action = _action()
    action._display = MagicMock()
    manager = MagicMock()
    manager.search_api.side_effect = [
        {"results": [{"id": 2, "name": "Preprod"}]},
        {"results": [{"id": 202, "name": "mco - preprod", "organization": 2}]},
    ]

    oid = action._resolve_named_object_id(
        manager,
        {"type": "job_templates", "name": "mco - preprod", "organization": "Preprod"},
    )

    assert oid == "202"
    assert manager.search_api.call_args_list[1].kwargs["query_params"] == {
        "name": "mco - preprod",
        "organization": 2,
    }


def test_resolve_named_object_eda_filters_organization():
    action = _action()
    action._display = MagicMock()
    manager = MagicMock()
    manager.search_api.side_effect = [
        {"results": [{"id": 9, "name": "EDA Org"}]},
        {
            "results": [
                {"id": 1, "name": "Demo", "organization_id": 1},
                {"id": 5, "name": "Demo", "organization_id": 9},
            ]
        },
    ]

    oid = action._resolve_named_object_id(
        manager,
        {"type": "eda_projects", "name": "Demo", "organization": "EDA Org"},
    )

    assert oid == "5"


def test_resolve_named_object_ambiguous_without_org_fails():
    action = _action()
    action._display = MagicMock()
    manager = MagicMock()
    manager.search_api.return_value = {
        "results": [
            {"id": 101, "name": "mco - preprod", "organization": 1},
            {"id": 202, "name": "mco - preprod", "organization": 2},
        ]
    }

    with pytest.raises(ValueError, match="Expected exactly one"):
        action._resolve_named_object_id(
            manager,
            {"type": "job_templates", "name": "mco - preprod"},
        )


def test_resolve_named_object_rejects_org_on_hub():
    action = _action()
    action._display = MagicMock()
    manager = MagicMock()

    with pytest.raises(AnsibleError, match="not supported for Hub"):
        action._resolve_named_object_id(
            manager,
            {"type": "namespaces", "name": "ns1", "organization": "Prod"},
        )
