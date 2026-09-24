import yaml
from ansible.constants import config as ansible_config
from ansible_collections.ansible.platform.plugins.doc_fragments.auth_lookup import ModuleDocFragment
from ansible_collections.ansible.platform.plugins.lookup import gateway_api
from ansible_collections.ansible.platform.plugins.plugin_utils.manager import process_manager

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

    class FakeClient:
        _process = None

        def search_api(self, **kwargs):
            return {"count": 0, "results": []}

        def shutdown_manager(self):
            return None

        def close(self):
            return None

    def fake_spawn_ephemeral_client(task_vars, gateway_config):
        captured["gateway_config"] = gateway_config
        return FakeClient(), None

    monkeypatch.setattr(process_manager, "spawn_ephemeral_client", fake_spawn_ephemeral_client)
    monkeypatch.setattr(process_manager.ProcessManager, "terminate_manager_process", lambda process: None)
    _new_lookup_plugin().run(["users"], **kwargs)
    return captured["gateway_config"]


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

    assert config.base_url == "https://gateway.example.com"
    assert config.username == "admin"
    assert config.password == "secret"
    assert config.oauth_token == "token-value"
    assert config.verify_ssl is False
    assert config.request_timeout == 4.5


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

    assert config.base_url == "https://legacy.example.com"
    assert config.username == "legacy-admin"
    assert config.password == "legacy-secret"
    assert config.oauth_token == "legacy-token"
    assert config.verify_ssl is True
    assert config.request_timeout == 9.0


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

    assert config.base_url == "https://gateway.example.com"
    assert config.username == "gateway-user"
    assert config.password == "gateway-secret"
    assert config.oauth_token == "gateway-token"
    assert config.verify_ssl is False
    assert config.request_timeout == 4.5


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

    assert config.base_url == "https://explicit.example.com"
    assert config.username == "explicit-user"
    assert config.verify_ssl is True


def test_gateway_host_legacy_spelling_is_not_used(monkeypatch):
    config = _run_lookup(monkeypatch, {"GATEWAY_HOST": "https://old-name.example.com"})

    assert config.base_url == "https://localhost/"
