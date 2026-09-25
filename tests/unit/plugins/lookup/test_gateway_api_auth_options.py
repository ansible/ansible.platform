from ansible.constants import config as ansible_config
from ansible_collections.ansible.platform.plugins.doc_fragments.auth_lookup import ModuleDocFragment
from ansible_collections.ansible.platform.plugins.lookup import gateway_api
import yaml


PLUGIN_NAME = "ansible.platform.gateway_api_env_test"
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
    options = yaml.safe_load(gateway_api.DOCUMENTATION)["options"]
    options.update(yaml.safe_load(ModuleDocFragment.DOCUMENTATION)["options"])
    options.pop("_terms")
    ansible_config.initialize_plugin_configuration_definitions("lookup", PLUGIN_NAME, options)

    plugin = gateway_api.LookupModule()
    plugin._load_name = PLUGIN_NAME
    return plugin


def _run_lookup(monkeypatch, env, **kwargs):
    for env_name in ENV_NAMES:
        monkeypatch.delenv(env_name, raising=False)
    for env_name, value in env.items():
        monkeypatch.setenv(env_name, value)

    captured = {}
    real_aap_module = gateway_api.AAPModule

    class FakeAAPModule:
        short_params = real_aap_module.short_params

        def __init__(self, argument_spec, direct_params, error_callback, warn_callback):
            captured.update(direct_params)

        def get_endpoint(self, endpoint, data=None):
            return {"status_code": 200, "json": {"count": 0, "results": []}}

    monkeypatch.setattr(gateway_api, "AAPModule", FakeAAPModule)
    _new_lookup_plugin().run(["users"], **kwargs)
    return captured


def test_auth_options_register_environment_fallbacks():
    options = yaml.safe_load(ModuleDocFragment.DOCUMENTATION)["options"]
    expected_env = {
        "host": ["AAP_HOSTNAME", "GATEWAY_HOSTNAME"],
        "username": ["AAP_USERNAME", "GATEWAY_USERNAME"],
        "password": ["AAP_PASSWORD", "GATEWAY_PASSWORD"],
        "oauth_token": ["AAP_TOKEN", "GATEWAY_API_TOKEN"],
        "verify_ssl": ["AAP_VALIDATE_CERTS", "GATEWAY_VERIFY_SSL"],
        "request_timeout": ["AAP_REQUEST_TIMEOUT", "GATEWAY_REQUEST_TIMEOUT"],
    }

    for option_name, expected_names in expected_env.items():
        assert [entry["name"] for entry in options[option_name]["env"]] == expected_names

    assert options["verify_ssl"]["type"] == "bool"
    assert options["request_timeout"]["type"] == "float"


def test_exported_gateway_variables_reach_aap_module(monkeypatch):
    params = _run_lookup(
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

    assert params == {
        "gateway_hostname": "https://gateway.example.com",
        "gateway_username": "admin",
        "gateway_password": "secret",
        "gateway_validate_certs": False,
        "gateway_token": "token-value",
        "gateway_request_timeout": 4.5,
    }


def test_aap_environment_aliases_are_fallbacks(monkeypatch):
    params = _run_lookup(
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

    assert params == {
        "gateway_hostname": "https://legacy.example.com",
        "gateway_username": "legacy-admin",
        "gateway_password": "legacy-secret",
        "gateway_validate_certs": True,
        "gateway_token": "legacy-token",
        "gateway_request_timeout": 9.0,
    }


def test_gateway_environment_takes_precedence_over_aap_aliases(monkeypatch):
    params = _run_lookup(
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

    assert params == {
        "gateway_hostname": "https://gateway.example.com",
        "gateway_username": "gateway-user",
        "gateway_password": "gateway-secret",
        "gateway_token": "gateway-token",
        "gateway_validate_certs": False,
        "gateway_request_timeout": 4.5,
    }


def test_explicit_lookup_options_override_environment(monkeypatch):
    params = _run_lookup(
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

    assert params["gateway_hostname"] == "https://explicit.example.com"
    assert params["gateway_username"] == "explicit-user"
    assert params["gateway_validate_certs"] is True


def test_gateway_host_legacy_spelling_is_not_used(monkeypatch):
    params = _run_lookup(monkeypatch, {"GATEWAY_HOST": "https://old-name.example.com"})

    assert "gateway_hostname" not in params
