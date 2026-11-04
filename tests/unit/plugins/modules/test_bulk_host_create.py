"""Unit tests for the bulk_host_create model, documentation, and transform."""

from pathlib import Path
from unittest.mock import MagicMock

import yaml

# ---------------------------------------------------------------------------
# 1. Ansible model dataclass tests
# ---------------------------------------------------------------------------


class TestAnsibleBulkHostCreate:
    """Tests for the AnsibleBulkHostCreate dataclass."""

    def test_dataclass_defaults(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.bulk_host_create import (
            AnsibleBulkHostCreate,
        )

        instance = AnsibleBulkHostCreate()
        assert instance.hosts == []
        assert instance.inventory is None

    def test_dataclass_with_values(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.bulk_host_create import (
            AnsibleBulkHostCreate,
        )

        hosts = [{"name": "host1"}, {"name": "host2"}]
        instance = AnsibleBulkHostCreate(hosts=hosts, inventory="my_inv")
        assert instance.hosts == hosts
        assert instance.inventory == "my_inv"
        assert len(instance.hosts) == 2

    def test_dataclass_is_dataclass(self):
        from dataclasses import is_dataclass

        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.bulk_host_create import (
            AnsibleBulkHostCreate,
        )

        assert is_dataclass(AnsibleBulkHostCreate)


# ---------------------------------------------------------------------------
# 2. Module DOCUMENTATION parsing test
# ---------------------------------------------------------------------------


class TestModuleDocumentation:
    """Verify the module stub is importable and has valid DOCUMENTATION."""

    def test_documentation_is_parseable(self):
        from ansible_collections.ansible.platform.plugins.modules import bulk_host_create

        doc = bulk_host_create.DOCUMENTATION
        parsed = yaml.safe_load(doc)
        assert parsed["module"] == "bulk_host_create"
        assert "hosts" in parsed["options"]
        assert "inventory" in parsed["options"]
        assert parsed["options"]["hosts"]["required"] is True
        assert parsed["options"]["inventory"]["required"] is True

    def test_extends_auth_fragment(self):
        from ansible_collections.ansible.platform.plugins.modules import bulk_host_create

        doc = bulk_host_create.DOCUMENTATION
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
        assert "bulk_host_create" in controller_group


# ---------------------------------------------------------------------------
# 5. Action plugin MODEL_CLASS test
# ---------------------------------------------------------------------------


class TestActionPluginModelClass:
    """Verify the action plugin has MODEL_CLASS set."""

    def test_model_class_is_set(self):
        from ansible_collections.ansible.platform.plugins.action.bulk_host_create import ActionModule
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.bulk_host_create import (
            AnsibleBulkHostCreate,
        )

        assert ActionModule.MODEL_CLASS is AnsibleBulkHostCreate


# ---------------------------------------------------------------------------
# 6. Transform and operation contract
# ---------------------------------------------------------------------------


class TestBulkHostCreateTransform:
    """Verify the transform produces the body declared by its endpoint operation."""

    def test_transform_builds_scoped_endpoint_payload(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.bulk_host_create import AnsibleBulkHostCreate
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.bulk_host_create import (
            BulkHostCreateTransformMixin_v2,
        )
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext

        manager = MagicMock()
        manager.lookup_resource_id.side_effect = [7, 42]
        source = AnsibleBulkHostCreate(
            inventory="Production",
            organization="Default",
            hosts=[{"name": "host1", "variables": {"ansible_host": "192.0.2.1"}}],
        )
        context = TransformContext(manager=manager, session=MagicMock(), cache={}, api_version="2", service="controller", operation="create")

        api_data = BulkHostCreateTransformMixin_v2.from_ansible_data(source, context)
        operation = BulkHostCreateTransformMixin_v2.get_endpoint_operations()["create"]
        payload = BulkHostCreateTransformMixin_v2.to_operation_payload(api_data, operation)

        assert operation.path == "/api/controller/v2/bulk/host_create/"
        assert operation.method == "POST"
        assert payload == {"inventory": 42, "hosts": [{"name": "host1", "variables": '{"ansible_host": "192.0.2.1"}'}]}
        assert manager.lookup_resource_id.call_args_list[0].kwargs == {"service": "controller"}
        assert manager.lookup_resource_id.call_args_list[1].kwargs == {
            "service": "controller",
            "require_unique": True,
            "extra_query_params": {"organization": 7},
        }
