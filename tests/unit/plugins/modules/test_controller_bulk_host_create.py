"""Unit tests for the controller_bulk_host_create module, dataclass, and transform mixin."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# ---------------------------------------------------------------------------
# 1. Ansible model dataclass tests
# ---------------------------------------------------------------------------


class TestAnsibleControllerBulkHostCreate:
    """Tests for the AnsibleControllerBulkHostCreate dataclass."""

    def test_dataclass_defaults(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_bulk_host_create import (
            AnsibleControllerBulkHostCreate,
        )

        instance = AnsibleControllerBulkHostCreate()
        assert instance.hosts == []
        assert instance.inventory is None

    def test_dataclass_with_values(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_bulk_host_create import (
            AnsibleControllerBulkHostCreate,
        )

        hosts = [{"name": "host1"}, {"name": "host2"}]
        instance = AnsibleControllerBulkHostCreate(hosts=hosts, inventory="my_inv")
        assert instance.hosts == hosts
        assert instance.inventory == "my_inv"
        assert len(instance.hosts) == 2

    def test_dataclass_is_dataclass(self):
        from dataclasses import is_dataclass

        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_bulk_host_create import (
            AnsibleControllerBulkHostCreate,
        )

        assert is_dataclass(AnsibleControllerBulkHostCreate)


# ---------------------------------------------------------------------------
# 2. Transform mixin tests
# ---------------------------------------------------------------------------


class TestControllerBulkHostCreateTransformMixin:
    """Tests for the API v2 transform mixin."""

    def test_from_ansible_data(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_bulk_host_create import (
            AnsibleControllerBulkHostCreate,
        )
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_bulk_host_create import (
            ControllerBulkHostCreateTransformMixin_v2,
        )

        ansible_data = AnsibleControllerBulkHostCreate(
            hosts=[{"name": "h1"}, {"name": "h2"}],
            inventory="42",
        )
        context = MagicMock()
        api_data = ControllerBulkHostCreateTransformMixin_v2.from_ansible_data(ansible_data, context)
        assert api_data.hosts == [{"name": "h1"}, {"name": "h2"}]
        assert api_data.inventory == "42"

    def test_get_endpoint_operations_has_create(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_bulk_host_create import (
            ControllerBulkHostCreateTransformMixin_v2,
        )

        ops = ControllerBulkHostCreateTransformMixin_v2.get_endpoint_operations()
        assert "create" in ops
        assert ops["create"].method == "POST"
        assert "bulk/host_create" in ops["create"].path

    def test_get_lookup_field(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_bulk_host_create import (
            ControllerBulkHostCreateTransformMixin_v2,
        )

        assert ControllerBulkHostCreateTransformMixin_v2.get_lookup_field() == "inventory"

    def test_from_api(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_bulk_host_create import (
            ControllerBulkHostCreateTransformMixin_v2,
        )

        api_data = {"hosts": [{"name": "h1"}], "inventory": "99"}
        context = MagicMock()
        result = ControllerBulkHostCreateTransformMixin_v2.from_api(api_data, context)
        assert result.hosts == [{"name": "h1"}]
        assert result.inventory == "99"


# ---------------------------------------------------------------------------
# 3. Module DOCUMENTATION parsing test
# ---------------------------------------------------------------------------


class TestModuleDocumentation:
    """Verify the module stub is importable and has valid DOCUMENTATION."""

    def test_documentation_is_parseable(self):
        from ansible_collections.ansible.platform.plugins.modules import controller_bulk_host_create

        doc = controller_bulk_host_create.DOCUMENTATION
        parsed = yaml.safe_load(doc)
        assert parsed["module"] == "controller_bulk_host_create"
        assert "hosts" in parsed["options"]
        assert "inventory" in parsed["options"]
        assert parsed["options"]["hosts"]["required"] is True
        assert parsed["options"]["inventory"]["required"] is True

    def test_extends_auth_fragment(self):
        from ansible_collections.ansible.platform.plugins.modules import controller_bulk_host_create

        doc = controller_bulk_host_create.DOCUMENTATION
        parsed = yaml.safe_load(doc)
        fragments = parsed.get("extends_documentation_fragment", [])
        assert "ansible.platform.auth" in fragments


# ---------------------------------------------------------------------------
# 4. meta/runtime.yml test
# ---------------------------------------------------------------------------


class TestRuntimeYml:
    """Verify the controller action group includes the new module."""

    def test_controller_action_group(self):
        runtime_path = Path(__file__).resolve().parents[4] / "meta" / "runtime.yml"
        with open(runtime_path) as f:
            runtime = yaml.safe_load(f)

        controller_group = runtime["action_groups"]["controller"]
        assert "controller_bulk_host_create" in controller_group


# ---------------------------------------------------------------------------
# 5. Action plugin MODEL_CLASS test
# ---------------------------------------------------------------------------


class TestActionPluginModelClass:
    """Verify the action plugin has MODEL_CLASS set."""

    def test_model_class_is_set(self):
        from ansible_collections.ansible.platform.plugins.action.controller_bulk_host_create import ActionModule
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_bulk_host_create import (
            AnsibleControllerBulkHostCreate,
        )

        assert ActionModule.MODEL_CLASS is AnsibleControllerBulkHostCreate


# ---------------------------------------------------------------------------
# 6. Variables serialization test
# ---------------------------------------------------------------------------


class TestVariablesSerialization:
    """Test that host variables dicts get serialized to JSON strings."""

    def test_variables_dict_serialized(self):
        """The action plugin serializes variables dicts to JSON strings."""
        hosts = [
            {"name": "h1", "variables": {"ansible_host": "1.2.3.4"}},
            {"name": "h2"},
        ]
        # Simulate what the action plugin does
        for h in hosts:
            if "variables" in h and isinstance(h["variables"], dict):
                h["variables"] = json.dumps(h["variables"])

        assert hosts[0]["variables"] == '{"ansible_host": "1.2.3.4"}'
        assert "variables" not in hosts[1]


# ---------------------------------------------------------------------------
# 7. SDK method tests (PlatformService.bulk_host_create)
# ---------------------------------------------------------------------------


class TestPlatformServiceBulkHostCreate:
    """Tests for PlatformService.bulk_host_create via mock."""

    def _make_service(self):
        """Create a PlatformService with mocked internals."""
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import (
            PlatformService,
        )

        with patch.object(PlatformService, "__init__", lambda self, *a, **kw: None):
            svc = PlatformService.__new__(PlatformService)
        import threading
        import time

        svc.session = MagicMock()
        svc.request_timeout = 30
        svc.base_url = "https://gw.example.com"
        svc.verify_ssl = True
        svc.ca_bundle = None
        svc.config = MagicMock()
        svc.config.requests_verify = True
        svc.api_versions = {"controller": "2"}
        svc.registry = MagicMock()
        svc.registry.get_supported_versions.return_value = ["2"]
        svc._activity_lock = threading.Lock()
        svc._last_activity_monotonic = time.monotonic()
        svc._lock = threading.Lock()
        svc._http_request_count = 0
        svc.retry_config = MagicMock()
        return svc

    def test_bulk_host_create_success(self):
        svc = self._make_service()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = b'{"created": 2}'
        mock_response.json.return_value = {"created": 2}
        svc._make_request = MagicMock(return_value=mock_response)

        result = svc.bulk_host_create(inventory_id=42, hosts=[{"name": "h1"}, {"name": "h2"}])

        assert result == {"created": 2}
        svc._make_request.assert_called_once()

    def test_bulk_host_create_failure(self):
        svc = self._make_service()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        svc._make_request = MagicMock(return_value=mock_response)

        with pytest.raises(ValueError, match="Bulk host create failed"):
            svc.bulk_host_create(inventory_id=42, hosts=[{"name": "bad"}])


# ---------------------------------------------------------------------------
# 8. RPC client delegation test
# ---------------------------------------------------------------------------


class TestManagerRPCClientBulkHostCreate:
    """Test that ManagerRPCClient.bulk_host_create delegates to service proxy."""

    def test_delegation(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import (
            ManagerRPCClient,
        )

        with patch.object(ManagerRPCClient, "__init__", lambda self, *a, **kw: None):
            rpc = ManagerRPCClient.__new__(ManagerRPCClient)
        rpc.service_proxy = MagicMock()
        rpc.service_proxy.bulk_host_create.return_value = {"created": 1}

        result = rpc.bulk_host_create(inventory_id=10, hosts=[{"name": "x"}], service="controller")

        assert result == {"created": 1}
        rpc.service_proxy.bulk_host_create.assert_called_once_with(10, [{"name": "x"}], "controller")
