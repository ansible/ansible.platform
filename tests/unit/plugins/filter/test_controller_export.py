# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
from pathlib import Path

import pytest

# Allow direct import when ansible_collections namespace isn't installed.
_plugins_dir = Path(__file__).resolve().parents[4] / "plugins"
if str(_plugins_dir.parent) not in sys.path:
    sys.path.insert(0, str(_plugins_dir.parent))

from plugins.filter.controller_export import (  # noqa: E402
    FilterModule,
    _convert_resource,
    _resolve_natural_key,
    from_awxkit_export,
)


class TestResolveNaturalKey:
    def test_simple_name(self):
        assert _resolve_natural_key({"type": "organization", "name": "Default"}) == "Default"

    def test_username(self):
        assert _resolve_natural_key({"type": "user", "username": "admin"}) == "admin"

    def test_hostname(self):
        assert _resolve_natural_key({"type": "host", "hostname": "web1.example.com"}) == "web1.example.com"

    def test_nested_org(self):
        nk = {"type": "credential", "name": "My Cred", "organization": {"type": "organization", "name": "Default"}}
        assert _resolve_natural_key(nk) == "My Cred"

    def test_plain_string_passthrough(self):
        assert _resolve_natural_key("already_a_name") == "already_a_name"

    def test_none(self):
        assert _resolve_natural_key(None) is None


class TestConvertResource:
    def test_strips_natural_key(self):
        resource = {
            "name": "Default",
            "description": "",
            "natural_key": {"type": "organization", "name": "Default"},
        }
        result = _convert_resource(resource)
        assert "natural_key" not in result
        assert result["name"] == "Default"
        assert result["description"] == ""

    def test_resolves_fk_to_name(self):
        resource = {
            "name": "My Inventory",
            "organization": {"type": "organization", "name": "Default"},
            "natural_key": {"type": "inventory", "name": "My Inventory"},
        }
        result = _convert_resource(resource)
        assert result["organization"] == "Default"

    def test_preserves_non_fk_fields(self):
        resource = {
            "name": "Test",
            "description": "A test resource",
            "extra_vars": '{"key": "value"}',
            "verbosity": 2,
            "natural_key": {"type": "job_template", "name": "Test"},
        }
        result = _convert_resource(resource)
        assert result["description"] == "A test resource"
        assert result["extra_vars"] == '{"key": "value"}'
        assert result["verbosity"] == 2

    def test_flattens_association_related(self):
        resource = {
            "name": "My JT",
            "natural_key": {"type": "job_template", "name": "My JT"},
            "related": {
                "credentials": [
                    {"type": "credential", "name": "Cred1", "organization": {"type": "organization", "name": "Default"}},
                    {"type": "credential", "name": "Cred2", "organization": {"type": "organization", "name": "Default"}},
                ],
                "labels": [
                    {"type": "label", "name": "prod"},
                ],
            },
        }
        result = _convert_resource(resource)
        assert result["credentials"] == ["Cred1", "Cred2"]
        assert result["labels"] == ["prod"]
        assert "related" not in result

    def test_preserves_survey_spec(self):
        survey = {"name": "", "description": "", "spec": [{"question_name": "Q1", "type": "text"}]}
        resource = {
            "name": "My JT",
            "natural_key": {"type": "job_template", "name": "My JT"},
            "related": {"survey_spec": survey},
        }
        result = _convert_resource(resource)
        assert result["survey_spec"] == survey

    def test_multiple_fk_fields(self):
        resource = {
            "name": "My JT",
            "inventory": {"type": "inventory", "name": "Demo Inventory"},
            "project": {"type": "project", "name": "Demo Project"},
            "execution_environment": {"type": "execution_environment", "name": "Default EE"},
            "credential_type": None,
            "natural_key": {"type": "job_template", "name": "My JT"},
        }
        result = _convert_resource(resource)
        assert result["inventory"] == "Demo Inventory"
        assert result["project"] == "Demo Project"
        assert result["execution_environment"] == "Default EE"
        assert result["credential_type"] is None


class TestFromAwxkitExport:
    def test_full_export(self):
        data = {
            "organizations": [
                {"name": "Default", "description": "", "natural_key": {"type": "organization", "name": "Default"}},
            ],
            "credentials": [
                {
                    "name": "My Cred",
                    "credential_type": {"type": "credential_type", "name": "Machine"},
                    "organization": {"type": "organization", "name": "Default"},
                    "inputs": {"username": "admin"},
                    "natural_key": {"type": "credential", "name": "My Cred"},
                },
            ],
        }
        result = from_awxkit_export(data)
        assert "organizations" in result
        assert result["organizations"][0]["name"] == "Default"
        assert "natural_key" not in result["organizations"][0]
        assert result["credentials"][0]["credential_type"] == "Machine"
        assert result["credentials"][0]["organization"] == "Default"

    def test_skips_missing_resource_types(self):
        data = {"organizations": [{"name": "Default", "natural_key": {"type": "organization", "name": "Default"}}]}
        result = from_awxkit_export(data)
        assert "organizations" in result
        assert "credentials" not in result
        assert "projects" not in result

    def test_ignores_unknown_resource_types(self):
        data = {
            "organizations": [{"name": "Default", "natural_key": {"type": "organization", "name": "Default"}}],
            "unknown_things": [{"name": "x"}],
        }
        result = from_awxkit_export(data)
        assert "unknown_things" not in result

    def test_empty_export(self):
        assert from_awxkit_export({}) == {}

    def test_rejects_non_dict(self):
        with pytest.raises(TypeError, match="expects a dict"):
            from_awxkit_export("not a dict")

    def test_skips_none_resource_list(self):
        data = {"organizations": None, "credentials": []}
        result = from_awxkit_export(data)
        assert "organizations" not in result
        assert result["credentials"] == []


class TestFilterModule:
    def test_filters_registered(self):
        fm = FilterModule()
        filters = fm.filters()
        assert "from_awxkit_export" in filters
        assert "controller_resource_module_map" in filters

    def test_module_map_returns_dict(self):
        fm = FilterModule()
        mapping = fm.filters()["controller_resource_module_map"]()
        assert mapping["organizations"] == "organization"
        assert mapping["credentials"] == "controller_credential"
        assert mapping["projects"] == "controller_project"
        assert mapping["credential_types"] == "controller_credential_type"
        assert len(mapping) == 13
