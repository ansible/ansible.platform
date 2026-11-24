import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml
from ansible.constants import config as ansible_config
from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.doc_fragments.auth_lookup import ModuleDocFragment
from ansible_collections.ansible.platform.plugins.lookup import platform_api
from ansible_collections.ansible.platform.plugins.plugin_utils.manager import process_manager
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService

PLUGIN_NAME = "ansible.platform.platform_api_env_test"
ENV_NAMES = (
    "GATEWAY_HOSTNAME",
    "AAP_HOSTNAME",
    "GATEWAY_USERNAME",
    "AAP_USERNAME",
    "GATEWAY_PASSWORD",
    "AAP_PASSWORD",
    "GATEWAY_API_TOKEN",
    "AAP_TOKEN",
    "GATEWAY_VERIFY_SSL",
    "AAP_VALIDATE_CERTS",
    "GATEWAY_REQUEST_TIMEOUT",
    "AAP_REQUEST_TIMEOUT",
    "GATEWAY_HOST",
)


def _new_lookup_plugin():
    options = yaml.safe_load(platform_api.DOCUMENTATION)["options"]
    options.update(yaml.safe_load(ModuleDocFragment.DOCUMENTATION)["options"])
    options.pop("_terms")
    ansible_config.initialize_plugin_configuration_definitions("lookup", PLUGIN_NAME, options)

    plugin = platform_api.LookupModule()
    plugin._load_name = PLUGIN_NAME
    return plugin


def _stub_client(monkeypatch, search_api):
    client = Mock(search_api=search_api, _process=None)
    spawn = Mock(return_value=(client, None))
    monkeypatch.setattr(process_manager, "spawn_ephemeral_client", spawn)
    monkeypatch.setattr(process_manager.ProcessManager, "terminate_manager_process", lambda process: None)
    return spawn


def _run_lookup(monkeypatch, env, **kwargs):
    for env_name in ENV_NAMES:
        monkeypatch.delenv(env_name, raising=False)
    for env_name, value in env.items():
        monkeypatch.setenv(env_name, value)

    spawn = _stub_client(monkeypatch, Mock(return_value={"results": []}))
    _new_lookup_plugin().run(["users"], **kwargs)
    return spawn.call_args.args[1]


def _assert_config(config, **expected):
    assert {field: getattr(config, field) for field in expected} == expected


def test_exported_gateway_variables_reach_manager_config(monkeypatch):
    config = _run_lookup(
        monkeypatch,
        {
            "GATEWAY_HOSTNAME": "https://gateway.example.com",
            "GATEWAY_USERNAME": "admin",
            "GATEWAY_PASSWORD": "secret",
            "GATEWAY_VERIFY_SSL": "false",
            "GATEWAY_API_TOKEN": "token-value",
            "GATEWAY_REQUEST_TIMEOUT": "4.5",
        },
    )

    _assert_config(
        config,
        base_url="https://gateway.example.com",
        username="admin",
        password="secret",
        oauth_token="token-value",
        verify_ssl=False,
        request_timeout=4.5,
    )


def test_aap_environment_aliases_are_fallbacks(monkeypatch):
    config = _run_lookup(
        monkeypatch,
        {
            "AAP_HOSTNAME": "https://legacy.example.com",
            "AAP_USERNAME": "legacy-admin",
            "AAP_PASSWORD": "legacy-secret",
            "AAP_VALIDATE_CERTS": "true",
            "AAP_TOKEN": "legacy-token",
            "AAP_REQUEST_TIMEOUT": "9",
        },
    )

    _assert_config(
        config,
        base_url="https://legacy.example.com",
        username="legacy-admin",
        password="legacy-secret",
        oauth_token="legacy-token",
        verify_ssl=True,
        request_timeout=9.0,
    )


def test_gateway_environment_takes_precedence_over_aap_aliases(monkeypatch):
    config = _run_lookup(
        monkeypatch,
        {
            "GATEWAY_HOSTNAME": "https://gateway.example.com",
            "AAP_HOSTNAME": "https://legacy.example.com",
            "GATEWAY_USERNAME": "gateway-user",
            "AAP_USERNAME": "legacy-user",
            "GATEWAY_PASSWORD": "gateway-secret",
            "AAP_PASSWORD": "legacy-secret",
            "GATEWAY_API_TOKEN": "gateway-token",
            "AAP_TOKEN": "legacy-token",
            "GATEWAY_VERIFY_SSL": "false",
            "AAP_VALIDATE_CERTS": "true",
            "GATEWAY_REQUEST_TIMEOUT": "4.5",
            "AAP_REQUEST_TIMEOUT": "9",
        },
    )

    _assert_config(
        config,
        base_url="https://gateway.example.com",
        username="gateway-user",
        password="gateway-secret",
        oauth_token="gateway-token",
        verify_ssl=False,
        request_timeout=4.5,
    )


def test_explicit_lookup_options_override_environment(monkeypatch):
    config = _run_lookup(
        monkeypatch,
        {
            "GATEWAY_HOSTNAME": "https://environment.example.com",
            "GATEWAY_USERNAME": "environment-user",
            "GATEWAY_VERIFY_SSL": "false",
        },
        host="https://explicit.example.com",
        username="explicit-user",
        verify_ssl=True,
    )

    _assert_config(config, base_url="https://explicit.example.com", username="explicit-user", verify_ssl=True)


def test_gateway_host_legacy_spelling_is_not_used(monkeypatch):
    config = _run_lookup(monkeypatch, {"GATEWAY_HOST": "https://old-name.example.com"})

    assert config.base_url == "https://localhost/"


@pytest.fixture
def api(monkeypatch):
    manager = PlatformService.__new__(PlatformService)
    manager.base_url = "https://gateway.example.com"
    manager.api_versions = {}
    manager._detect_service_version = {"gateway": "1", "controller": "7", "eda": "1"}.__getitem__
    manager.record_activity = lambda: None
    manager._make_request = Mock(return_value=SimpleNamespace(json=lambda: {"results": []}))
    _stub_client(monkeypatch, manager.search_api)
    return manager


@pytest.mark.parametrize(
    ("endpoint", "service", "expected_path"),
    [
        ("instances", None, "/api/controller/v7/instances/"),
        ("/instances/42", None, "/api/controller/v7/instances/42/"),
        ("instances?enabled=true", None, "/api/controller/v7/instances?enabled=true"),
        ("decision-environments", None, "/api/eda/v1/decision-environments/"),
        ("instances", "gateway", "/api/gateway/v1/instances/"),
        ("organizations", "eda", "/api/eda/v1/organizations/"),
        ("organizations", None, "/api/gateway/v1/organizations/"),
        ("custom_endpoint", None, "/api/gateway/v1/custom_endpoint/"),
        ("/api/eda/v1/organizations/", "controller", "/api/eda/v1/organizations/"),
        ("api/controller/v2/instances/", "eda", "/api/controller/v2/instances/"),
    ],
)
def test_platform_api_routes_endpoints(api, endpoint, service, expected_path):
    lookup = _new_lookup_plugin()
    options = {"service": service} if service else {}

    lookup.run([endpoint], **options)
    assert api._make_request.call_args.args[1] == api.base_url + expected_path


def test_gateway_api_redirects_to_platform_api(tmp_path):
    collection = tmp_path / "ansible_collections" / "ansible" / "platform"
    collection.parent.mkdir(parents=True)
    collection.symlink_to(Path(__file__).resolve().parents[4], target_is_directory=True)
    old_name = "ansible.platform.gateway_api"
    new_name = "ansible.platform.platform_api"
    docs = subprocess.run(
        [sys.executable, "-m", "ansible.cli.doc", "-t", "lookup", "-j", old_name, new_name],
        env={**os.environ, "ANSIBLE_COLLECTIONS_PATH": str(tmp_path), "ANSIBLE_HOME": str(tmp_path)},
        check=True,
        capture_output=True,
        text=True,
    )
    resolved = json.loads(docs.stdout)

    assert resolved[old_name]["doc"]["filename"] == resolved[new_name]["doc"]["filename"]


def test_platform_api_forwards_pagination_options_and_returns_ids(monkeypatch):
    search_api = Mock(return_value={"results": [{"id": 42}, {"id": 43}]})
    _stub_client(monkeypatch, search_api)
    filters = {"enabled": True}

    assert _new_lookup_plugin().run(["instances"], query_params=filters, return_all=True, max_objects=5, return_ids=True) == ["42", "43"]
    search_api.assert_called_once_with(endpoint="instances", query_params=filters, return_all=True, max_objects=5, service="controller")


def test_platform_api_reports_request_error(monkeypatch):
    _stub_client(monkeypatch, Mock(side_effect=RuntimeError("request failed")))

    with pytest.raises(AnsibleError, match="API request failed for 'instances': request failed"):
        _new_lookup_plugin().run(["instances"])
