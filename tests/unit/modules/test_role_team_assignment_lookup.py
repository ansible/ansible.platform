# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
from pathlib import Path

import pytest
from ansible.errors import AnsibleError

sys.path.insert(0, str(Path(__file__).resolve().parents[6]))

from ansible_collections.ansible.platform.plugins.modules.role_team_assignment import (
    _lookup_exact_named_resource,
    _matches_org,
    _resolve_named_object,
)


class FakeModule:
    def __init__(self, response, pages=None):
        self.response = response
        self.pages = pages or []
        self.queries = []

    def get_endpoint(self, endpoint, data=None):
        self.queries.append((endpoint, data))
        return self.response

    def make_request(self, method, url):
        return self.pages.pop(0)

    def fail_json(self, **kwargs):
        raise AnsibleError(kwargs["msg"])


def test_matches_org_accepts_flat_and_nested_ids():
    assert _matches_org({"organization_id": 2}, "2")
    assert _matches_org({"organization": {"id": 2}}, 2)
    assert not _matches_org({"organization_id": 1}, 2)


def test_exact_lookup_ignores_prefix_collision():
    module = FakeModule(
        {"status_code": 200, "json": {"results": [{"id": 1, "name": "Demo-copy"}, {"id": 2, "name": "Demo"}]}}
    )

    result = _lookup_exact_named_resource(module, "teams", "Demo")

    assert result["id"] == 2
    assert module.queries == [("teams", {"name": "Demo"})]


def test_exact_lookup_fails_for_lone_prefix_match():
    module = FakeModule({"status_code": 200, "json": {"results": [{"id": 1, "name": "Demo-copy"}]}})

    with pytest.raises(AnsibleError, match="Expected exactly one resource named 'Demo'"):
        _lookup_exact_named_resource(module, "teams", "Demo")


def test_exact_lookup_follows_pages():
    module = FakeModule(
        {"status_code": 200, "json": {"results": [{"id": 1, "name": "Demo-copy"}], "next": "/api/gateway/v1/teams/?page=2"}},
        [{"status_code": 200, "json": {"results": [{"id": 2, "name": "Demo"}], "next": None}}],
    )

    result = _lookup_exact_named_resource(module, "teams", "Demo")

    assert result["id"] == 2


def test_controller_lookup_filters_exact_name_and_organization():
    module = FakeModule(
        {"status_code": 200, "json": {"results": [{"id": 9, "name": "Production"}]}},
        [
            {
                "status_code": 200,
                "json": {
                    "results": [
                        {"id": 1, "name": "Demo-copy", "organization": 9},
                        {"id": 2, "name": "Demo", "organization": 8},
                        {"id": 3, "name": "Demo", "organization": 9},
                    ]
                },
            }
        ],
    )
    original_get_endpoint = module.get_endpoint

    def get_endpoint(endpoint, data=None):
        if endpoint == "/api/controller/v2/organizations/":
            return original_get_endpoint(endpoint, data)
        return module.pages.pop(0)

    module.get_endpoint = get_endpoint

    result = _resolve_named_object(module, {"type": "awx.project", "name": "Demo", "organization": "Production"})

    assert result["id"] == 3


def test_eda_lookup_filters_exact_name_and_organization_id():
    module = FakeModule(
        {"status_code": 200, "json": {"results": [{"id": 9, "name": "Production"}]}},
        [
            {
                "status_code": 200,
                "json": {
                    "results": [
                        {"id": 1, "name": "Demo-copy", "organization_id": 9},
                        {"id": 2, "name": "Demo", "organization_id": 8},
                        {"id": 3, "name": "Demo", "organization_id": 9},
                    ]
                },
            }
        ],
    )
    original_get_endpoint = module.get_endpoint

    def get_endpoint(endpoint, data=None):
        if endpoint == "/api/eda/v1/organizations/":
            return original_get_endpoint(endpoint, data)
        return module.pages.pop(0)

    module.get_endpoint = get_endpoint

    result = _resolve_named_object(module, {"type": "eda.project", "name": "Demo", "organization": "Production"})

    assert result["id"] == 3
