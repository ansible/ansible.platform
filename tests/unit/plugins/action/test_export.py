# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the export action plugin's data transformation logic.

Tests the FK resolution, resource cleaning, and field filtering logic
against the action plugin's exported constants.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type


from ansible_collections.ansible.platform.plugins.action.export import (
    FK_RESOLUTION_MAP,
    GROUP_EXPORT_FIELDS,
    HOST_EXPORT_FIELDS,
    STRIP_FIELDS,
)


def clean_resource(resource, name_cache):
    """Replicate export action plugin's _clean_resource logic for testing."""
    cleaned = {}
    for key, value in resource.items():
        if key in STRIP_FIELDS:
            continue
        if key in FK_RESOLUTION_MAP and isinstance(value, int):
            endpoint = FK_RESOLUTION_MAP[key][0]
            cache = name_cache.get(endpoint, {})
            cleaned[key] = cache.get(value, value)
        else:
            cleaned[key] = value
    return cleaned


class TestCleanResource:
    def test_strips_internal_fields(self):
        resource = {
            "id": 1,
            "name": "Test",
            "url": "/api/v2/organizations/1/",
            "related": {},
            "summary_fields": {},
            "created": "2025-01-01",
            "modified": "2025-01-02",
            "description": "A test org",
        }
        result = clean_resource(resource, {})
        assert "id" not in result
        assert "url" not in result
        assert "related" not in result
        assert "summary_fields" not in result
        assert "created" not in result
        assert result["name"] == "Test"
        assert result["description"] == "A test org"

    def test_resolves_fk_ids_to_names(self):
        resource = {"name": "My JT", "inventory": 42, "project": 7, "organization": 1}
        name_cache = {
            "api/controller/v2/inventories/": {42: "Production"},
            "api/controller/v2/projects/": {7: "Demo Project"},
            "api/gateway/v1/organizations/": {1: "Default"},
        }
        result = clean_resource(resource, name_cache)
        assert result["inventory"] == "Production"
        assert result["project"] == "Demo Project"
        assert result["organization"] == "Default"

    def test_preserves_fk_id_on_cache_miss(self):
        resource = {"name": "Test", "inventory": 999}
        result = clean_resource(resource, {"api/controller/v2/inventories/": {}})
        assert result["inventory"] == 999

    def test_preserves_non_fk_fields(self):
        resource = {
            "name": "Test",
            "description": "desc",
            "verbosity": 2,
            "extra_vars": '{"key": "val"}',
            "playbook": "site.yml",
        }
        result = clean_resource(resource, {})
        assert result == resource

    def test_handles_null_fk_fields(self):
        resource = {"name": "Test", "organization": None, "inventory": None}
        result = clean_resource(resource, {})
        assert result["organization"] is None
        assert result["inventory"] is None

    def test_handles_string_fk_fields(self):
        resource = {"name": "Test", "organization": "Default"}
        result = clean_resource(resource, {})
        assert result["organization"] == "Default"

    def test_multiple_fk_fields(self):
        resource = {
            "name": "JT",
            "inventory": 1,
            "project": 2,
            "execution_environment": 3,
            "credential_type": 4,
            "organization": 5,
        }
        name_cache = {
            "api/controller/v2/inventories/": {1: "Inv1"},
            "api/controller/v2/projects/": {2: "Proj1"},
            "api/controller/v2/execution_environments/": {3: "EE1"},
            "api/controller/v2/credential_types/": {4: "Machine"},
            "api/gateway/v1/organizations/": {5: "Org1"},
        }
        result = clean_resource(resource, name_cache)
        assert result["inventory"] == "Inv1"
        assert result["project"] == "Proj1"
        assert result["execution_environment"] == "EE1"
        assert result["credential_type"] == "Machine"
        assert result["organization"] == "Org1"


class TestHostGroupFieldFilter:
    def test_host_fields_filter(self):
        raw = {
            "id": 1,
            "name": "web01",
            "enabled": True,
            "variables": "{}",
            "url": "/api/...",
            "related": {},
            "summary_fields": {},
            "created": "2025-01-01",
            "description": "Web server",
        }
        filtered = {k: v for k, v in raw.items() if k in HOST_EXPORT_FIELDS and v is not None}
        assert "id" not in filtered
        assert "url" not in filtered
        assert filtered["name"] == "web01"
        assert filtered["enabled"] is True
        assert "description" in filtered

    def test_group_fields_filter(self):
        raw = {
            "id": 5,
            "name": "webservers",
            "description": "",
            "variables": '{"env": "prod"}',
            "url": "/api/...",
            "related": {},
        }
        filtered = {k: v for k, v in raw.items() if k in GROUP_EXPORT_FIELDS and v is not None}
        assert "id" not in filtered
        assert "url" not in filtered
        assert filtered["name"] == "webservers"

    def test_host_strips_empty_values(self):
        raw = {"name": "host1", "enabled": True, "variables": None, "description": None}
        filtered = {k: v for k, v in raw.items() if k in HOST_EXPORT_FIELDS and v is not None}
        assert "variables" not in filtered
        assert "description" not in filtered


class TestExportImportRoundTrip:
    def test_exported_org_importable(self):
        raw = {
            "id": 1,
            "name": "Default",
            "description": "",
            "url": "/api/...",
            "related": {},
            "summary_fields": {},
            "created": "2025-01-01",
            "modified": "2025-01-01",
        }
        cleaned = clean_resource(raw, {})
        assert "name" in cleaned
        assert "id" not in cleaned
        assert "url" not in cleaned

    def test_exported_credential_importable(self):
        raw = {
            "id": 5,
            "name": "My Cred",
            "credential_type": 1,
            "organization": 1,
            "inputs": {"username": "admin", "password": "$encrypted$"},
            "url": "/api/...",
            "related": {},
            "summary_fields": {},
            "created": "2025-01-01",
            "modified": "2025-01-01",
        }
        cache = {
            "api/controller/v2/credential_types/": {1: "Machine"},
            "api/gateway/v1/organizations/": {1: "Default"},
        }
        cleaned = clean_resource(raw, cache)
        assert cleaned["credential_type"] == "Machine"
        assert cleaned["organization"] == "Default"
        assert cleaned["inputs"] == {"username": "admin", "password": "$encrypted$"}
        assert "id" not in cleaned

    def test_exported_job_template_importable(self):
        raw = {
            "id": 10,
            "name": "Deploy",
            "inventory": 42,
            "project": 7,
            "organization": 1,
            "playbook": "deploy.yml",
            "job_type": "run",
            "verbosity": 0,
            "forks": 0,
            "extra_vars": "",
            "url": "/api/...",
            "related": {},
            "summary_fields": {},
            "created": "2025-01-01",
            "modified": "2025-01-01",
        }
        cache = {
            "api/controller/v2/inventories/": {42: "Production"},
            "api/controller/v2/projects/": {7: "Demo Project"},
            "api/gateway/v1/organizations/": {1: "Default"},
        }
        cleaned = clean_resource(raw, cache)
        assert cleaned["name"] == "Deploy"
        assert cleaned["inventory"] == "Production"
        assert cleaned["project"] == "Demo Project"
        assert cleaned["organization"] == "Default"
        assert cleaned["playbook"] == "deploy.yml"
        assert "id" not in cleaned
        assert "url" not in cleaned


def test_default_environment_is_preserved_and_resolved():
    resource = {"name": "Project", "default_environment": 7}
    name_cache = {"api/controller/v2/execution_environments/": {7: "Default EE"}}

    result = clean_resource(resource, name_cache)

    assert result["default_environment"] == "Default EE"


def test_filtered_search_uses_endpoint_agnostic_exact_queries():
    from ansible_collections.ansible.platform.plugins.action.export import ActionModule

    class SearchManager:
        def __init__(self):
            self.calls = []

        def search_api(self, **kwargs):
            self.calls.append(kwargs)
            name = kwargs["query_params"]["name"]
            return {"results": [{"id": name, "name": name}]}

    manager = SearchManager()
    action = ActionModule.__new__(ActionModule)

    result = action._search_resources(manager, "api/gateway/v1/organizations/", "name", ["one", "two"], 10)

    assert [item["name"] for item in result["results"]] == ["one", "two"]
    assert all("or__name" not in call["query_params"] for call in manager.calls)
