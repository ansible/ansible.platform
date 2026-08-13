"""Unit tests for ad_hoc_command dataclass, API transform, and action plugin logic."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import unittest
from dataclasses import asdict
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.ad_hoc_command import AnsibleAdHocCommand
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.ad_hoc_command import (
    AdHocCommandTransformMixin_v1,
    APIAdHocCommand_v1,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext


class TestAnsibleAdHocCommand(unittest.TestCase):
    """Tests for the AnsibleAdHocCommand dataclass."""

    def test_required_fields_only(self):
        cmd = AnsibleAdHocCommand(inventory="Demo Inventory", credential="Demo Credential", module_name="ping")
        self.assertEqual(cmd.inventory, "Demo Inventory")
        self.assertEqual(cmd.credential, "Demo Credential")
        self.assertEqual(cmd.module_name, "ping")
        self.assertIsNone(cmd.job_type)
        self.assertIsNone(cmd.module_args)
        self.assertIsNone(cmd.execution_environment)
        self.assertIsNone(cmd.id)
        self.assertIsNone(cmd.status)

    def test_all_fields(self):
        cmd = AnsibleAdHocCommand(
            inventory="My Inv",
            credential="My Cred",
            module_name="command",
            module_args="echo hello",
            job_type="run",
            limit="webservers",
            forks=10,
            verbosity=2,
            extra_vars={"foo": "bar"},
            become_enabled=True,
            diff_mode=False,
            execution_environment="Default EE",
        )
        self.assertEqual(cmd.module_args, "echo hello")
        self.assertEqual(cmd.job_type, "run")
        self.assertEqual(cmd.forks, 10)
        self.assertEqual(cmd.extra_vars, {"foo": "bar"})
        self.assertTrue(cmd.become_enabled)
        self.assertFalse(cmd.diff_mode)

    def test_asdict_roundtrip(self):
        cmd = AnsibleAdHocCommand(inventory="inv", credential="cred", module_name="ping")
        d = asdict(cmd)
        self.assertIn("inventory", d)
        self.assertIn("module_name", d)
        self.assertEqual(d["inventory"], "inv")


class TestAPIAdHocCommand(unittest.TestCase):
    """Tests for the APIAdHocCommand_v1 wire-format dataclass."""

    def test_wire_format_types(self):
        api = APIAdHocCommand_v1(
            module_name="command",
            inventory=42,
            credential=7,
            execution_environment=3,
        )
        self.assertIsInstance(api.inventory, int)
        self.assertIsInstance(api.credential, int)
        self.assertIsInstance(api.execution_environment, int)


class TestAdHocCommandTransformMixin(unittest.TestCase):
    """Tests for the AdHocCommandTransformMixin_v1."""

    def _make_context(self):
        manager = MagicMock()
        session = MagicMock()
        return TransformContext(manager=manager, session=session, cache={}, api_version="1", operation="create")

    def test_from_ansible_data_basic(self):
        context = self._make_context()
        context.manager.lookup_resource_id.side_effect = lambda ep, field, val: {
            ("inventories", "name", "Demo Inventory"): 1,
            ("credentials", "name", "Demo Credential"): 5,
        }[(ep, field, val)]

        ansible_cmd = AnsibleAdHocCommand(
            inventory="Demo Inventory",
            credential="Demo Credential",
            module_name="ping",
        )

        api_data = AdHocCommandTransformMixin_v1.from_ansible_data(ansible_cmd, context)
        self.assertIsInstance(api_data, APIAdHocCommand_v1)
        self.assertEqual(api_data.module_name, "ping")
        self.assertEqual(api_data.inventory, 1)
        self.assertEqual(api_data.credential, 5)
        self.assertIsNone(api_data.execution_environment)

    def test_from_ansible_data_with_all_fields(self):
        context = self._make_context()
        context.manager.lookup_resource_id.side_effect = lambda ep, field, val: {
            ("inventories", "name", "My Inv"): 10,
            ("credentials", "name", "My Cred"): 20,
            ("execution_environments", "name", "Custom EE"): 30,
        }[(ep, field, val)]

        ansible_cmd = AnsibleAdHocCommand(
            inventory="My Inv",
            credential="My Cred",
            module_name="command",
            module_args="echo hello",
            job_type="run",
            limit="webservers",
            forks=5,
            verbosity=3,
            extra_vars={"my_var": "value"},
            become_enabled=True,
            diff_mode=True,
            execution_environment="Custom EE",
        )

        api_data = AdHocCommandTransformMixin_v1.from_ansible_data(ansible_cmd, context)
        self.assertEqual(api_data.inventory, 10)
        self.assertEqual(api_data.credential, 20)
        self.assertEqual(api_data.execution_environment, 30)
        self.assertEqual(api_data.module_args, "echo hello")
        self.assertEqual(api_data.job_type, "run")
        self.assertEqual(api_data.limit, "webservers")
        self.assertEqual(api_data.forks, 5)
        self.assertEqual(api_data.verbosity, 3)
        self.assertTrue(api_data.become_enabled)
        self.assertTrue(api_data.diff_mode)

    def test_extra_vars_dict_to_json(self):
        context = self._make_context()
        context.manager.lookup_resource_id.return_value = 1

        ansible_cmd = AnsibleAdHocCommand(
            inventory="inv",
            credential="cred",
            module_name="shell",
            extra_vars={"key": "value", "num": 42},
        )

        api_data = AdHocCommandTransformMixin_v1.from_ansible_data(ansible_cmd, context)
        parsed = json.loads(api_data.extra_vars)
        self.assertEqual(parsed["key"], "value")
        self.assertEqual(parsed["num"], 42)

    def test_extra_vars_none_not_sent(self):
        context = self._make_context()
        context.manager.lookup_resource_id.return_value = 1

        ansible_cmd = AnsibleAdHocCommand(
            inventory="inv",
            credential="cred",
            module_name="ping",
        )

        api_data = AdHocCommandTransformMixin_v1.from_ansible_data(ansible_cmd, context)
        self.assertIsNone(api_data.extra_vars)

    def test_name_resolution_calls(self):
        context = self._make_context()
        context.manager.lookup_resource_id.return_value = 99

        ansible_cmd = AnsibleAdHocCommand(
            inventory="My Inv",
            credential="My Cred",
            module_name="ping",
            execution_environment="My EE",
        )

        AdHocCommandTransformMixin_v1.from_ansible_data(ansible_cmd, context)

        calls = context.manager.lookup_resource_id.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][0], ("inventories", "name", "My Inv"))
        self.assertEqual(calls[1][0], ("credentials", "name", "My Cred"))
        self.assertEqual(calls[2][0], ("execution_environments", "name", "My EE"))

    def test_from_api(self):
        context = self._make_context()
        api_response = {
            "id": 42,
            "inventory": 10,
            "credential": 20,
            "module_name": "command",
            "module_args": "echo hello",
            "status": "successful",
            "job_type": "run",
            "limit": "all",
            "forks": 5,
            "verbosity": 2,
            "become_enabled": True,
            "diff_mode": False,
        }

        result = AdHocCommandTransformMixin_v1.from_api(api_response, context)
        self.assertIsInstance(result, AnsibleAdHocCommand)
        self.assertEqual(result.id, 42)
        self.assertEqual(result.module_name, "command")
        self.assertEqual(result.status, "successful")
        self.assertEqual(result.inventory, "10")
        self.assertEqual(result.credential, "20")
        self.assertTrue(result.become_enabled)

    def test_endpoint_operations(self):
        ops = AdHocCommandTransformMixin_v1.get_endpoint_operations()
        self.assertIn("create", ops)
        create_op = ops["create"]
        self.assertEqual(create_op.method, "POST")
        self.assertEqual(create_op.path, "/api/controller/v2/ad_hoc_commands/")
        self.assertIn("module_name", create_op.fields)
        self.assertIn("inventory", create_op.fields)
        self.assertIn("credential", create_op.fields)
        self.assertIn("execution_environment", create_op.fields)
        self.assertIn("extra_vars", create_op.fields)

        self.assertIn("get", ops)
        get_op = ops["get"]
        self.assertEqual(get_op.method, "GET")
        self.assertEqual(get_op.path, "/api/controller/v2/ad_hoc_commands/{id}/")
        self.assertEqual(get_op.path_params, ["id"])

    def test_lookup_field(self):
        self.assertEqual(AdHocCommandTransformMixin_v1.get_lookup_field(), "id")


class TestDynamicClassLoaderDiscovery(unittest.TestCase):
    """Verify the DynamicClassLoader can find ad_hoc_command classes."""

    def test_loader_finds_ad_hoc_command(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.loader import DynamicClassLoader
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry import APIVersionRegistry

        registry = APIVersionRegistry()
        loader = DynamicClassLoader(registry)

        AnsibleClass, APIClass, MixinClass = loader.load_classes_for_module("ad_hoc_command", "1")
        self.assertEqual(AnsibleClass.__name__, "AnsibleAdHocCommand")
        self.assertEqual(APIClass.__name__, "APIAdHocCommand_v1")
        self.assertEqual(MixinClass.__name__, "AdHocCommandTransformMixin_v1")

    def test_loader_ansible_class_fields(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.loader import DynamicClassLoader
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry import APIVersionRegistry

        registry = APIVersionRegistry()
        loader = DynamicClassLoader(registry)

        AnsibleClass, _, _ = loader.load_classes_for_module("ad_hoc_command", "1")
        obj = AnsibleClass(inventory="inv", credential="cred", module_name="ping")
        self.assertEqual(obj.inventory, "inv")
        self.assertIsNone(obj.extra_vars)


class TestModuleDocumentation(unittest.TestCase):
    """Verify the module DOCUMENTATION is well-formed."""

    def test_documentation_parseable(self):
        import yaml
        from ansible_collections.ansible.platform.plugins.modules import ad_hoc_command

        doc = yaml.safe_load(ad_hoc_command.DOCUMENTATION)
        self.assertEqual(doc["module"], "ad_hoc_command")
        self.assertIn("options", doc)
        self.assertIn("inventory", doc["options"])
        self.assertIn("credential", doc["options"])
        self.assertIn("module_name", doc["options"])
        self.assertIn("wait", doc["options"])
        self.assertIn("interval", doc["options"])
        self.assertIn("timeout", doc["options"])

    def test_required_fields(self):
        import yaml
        from ansible_collections.ansible.platform.plugins.modules import ad_hoc_command

        doc = yaml.safe_load(ad_hoc_command.DOCUMENTATION)
        opts = doc["options"]
        self.assertTrue(opts["inventory"].get("required"))
        self.assertTrue(opts["credential"].get("required"))
        self.assertTrue(opts["module_name"].get("required"))
        self.assertIsNone(opts["wait"].get("required"))

    def test_extends_auth_fragment(self):
        import yaml
        from ansible_collections.ansible.platform.plugins.modules import ad_hoc_command

        doc = yaml.safe_load(ad_hoc_command.DOCUMENTATION)
        fragments = doc.get("extends_documentation_fragment", [])
        self.assertIn("ansible.platform.auth", fragments)

    def test_no_state_fragment(self):
        """ad_hoc_command is not a CRUD resource — it should not extend the state fragment."""
        import yaml
        from ansible_collections.ansible.platform.plugins.modules import ad_hoc_command

        doc = yaml.safe_load(ad_hoc_command.DOCUMENTATION)
        fragments = doc.get("extends_documentation_fragment", [])
        self.assertNotIn("ansible.platform.state", fragments)

    def test_return_doc_parseable(self):
        import yaml
        from ansible_collections.ansible.platform.plugins.modules import ad_hoc_command

        ret = yaml.safe_load(ad_hoc_command.RETURN)
        self.assertIn("id", ret)
        self.assertIn("status", ret)

    def test_examples_parseable(self):
        import yaml
        from ansible_collections.ansible.platform.plugins.modules import ad_hoc_command

        examples = yaml.safe_load(ad_hoc_command.EXAMPLES)
        self.assertIsInstance(examples, list)
        self.assertGreater(len(examples), 0)


if __name__ == "__main__":
    unittest.main()
