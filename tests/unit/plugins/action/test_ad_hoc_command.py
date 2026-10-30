# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the ad_hoc_command action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import unittest
from unittest.mock import MagicMock, patch

from ansible.playbook.task import Task
from ansible_collections.ansible.platform.plugins.action.ad_hoc_command import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError


def _make_module(args=None, check_mode=False):
    """Create an ActionModule instance with mocked dependencies."""
    task = MagicMock(spec=Task)
    task.args = args or {}
    task.check_mode = check_mode
    task.async_val = 0
    task.environment = []

    connection = MagicMock()
    play_context = MagicMock()
    loader = MagicMock()
    templar = MagicMock()
    shared_loader_obj = MagicMock()

    module = ActionModule(
        task=task,
        connection=connection,
        play_context=play_context,
        loader=loader,
        templar=templar,
        shared_loader_obj=shared_loader_obj,
    )
    module._display = MagicMock()
    module._display.verbosity = 0
    return module


def _make_manager():
    """Create a manager mock limited to the supported RPC client API."""
    return MagicMock(spec=ManagerRPCClient)


class TestActionModuleAttributes(unittest.TestCase):
    """Test basic class attributes."""

    def test_module_name(self):
        module = _make_module()
        self.assertEqual(module.MODULE_NAME, "ad_hoc_command")


class TestDocumentationValidation(unittest.TestCase):
    """Test the real module documentation and argument validation path."""

    @patch.object(ActionModule, "_get_or_spawn_manager")
    def test_documented_types_and_defaults_reach_action(self, mock_get_manager):
        module = _make_module(
            args={
                "inventory": "Demo",
                "credential": "Demo",
                "module_name": "command",
                "forks": "4",
                "verbosity": "3",
                "become_enabled": "yes",
                "diff_mode": "no",
                "extra_vars": {"env": "production"},
                "wait": "yes",
            },
        )
        manager = _make_manager()
        manager.lookup_resource_id.side_effect = [101, 202]
        manager.launch_resource.return_value = {"id": 42, "status": "pending"}
        manager.wait_for_completion.return_value = {"id": 42, "status": "successful"}
        mock_get_manager.return_value = (manager, {})

        result = module.run(task_vars={})

        self.assertFalse(result["failed"])
        post_data = manager.launch_resource.call_args.args[1]
        self.assertEqual(post_data["forks"], 4)
        self.assertIs(type(post_data["forks"]), int)
        self.assertEqual(post_data["verbosity"], 3)
        self.assertIs(type(post_data["verbosity"]), int)
        self.assertIs(post_data["become_enabled"], True)
        self.assertIs(post_data["diff_mode"], False)
        self.assertEqual(post_data["extra_vars"], json.dumps({"env": "production"}))
        manager.wait_for_completion.assert_called_once_with(
            "/api/controller/v2/ad_hoc_commands/42/",
            timeout=-1.0,
            interval=2.0,
            service="controller",
        )

    @patch.object(ActionModule, "_get_or_spawn_manager")
    def test_zero_timeout_is_forwarded_as_unbounded(self, mock_get_manager):
        module = _make_module(
            args={
                "inventory": "Demo",
                "credential": "Demo",
                "module_name": "command",
                "wait": True,
                "timeout": "0",
            },
        )
        manager = _make_manager()
        manager.lookup_resource_id.side_effect = [101, 202]
        manager.launch_resource.return_value = {"id": 42, "status": "pending"}
        manager.wait_for_completion.return_value = {"id": 42, "status": "successful"}
        mock_get_manager.return_value = (manager, {})

        result = module.run(task_vars={})

        self.assertFalse(result["failed"])
        manager.wait_for_completion.assert_called_once_with(
            "/api/controller/v2/ad_hoc_commands/42/",
            timeout=-1.0,
            interval=2.0,
            service="controller",
        )


class TestCheckMode(unittest.TestCase):
    """Test check mode behavior."""

    @patch.object(ActionModule, "_get_or_spawn_manager")
    def test_check_mode_resolves_references_but_skips_launch(self, mock_get_manager):
        module = _make_module(
            args={"inventory": "Demo", "credential": "Demo", "module_name": "ping"},
            check_mode=True,
        )
        manager = _make_manager()
        manager.lookup_resource_id.side_effect = [101, 202]
        mock_get_manager.return_value = (manager, {})

        result = module.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertFalse(result["failed"])
        self.assertIn("check mode", result["msg"])
        self.assertEqual(manager.lookup_resource_id.call_count, 2)
        manager.launch_resource.assert_not_called()
        manager.wait_for_completion.assert_not_called()

    @patch.object(ActionModule, "_get_or_spawn_manager")
    def test_check_mode_reports_missing_reference(self, mock_get_manager):
        module = _make_module(
            args={"inventory": "Missing", "credential": "Demo", "module_name": "ping"},
            check_mode=True,
        )
        manager = _make_manager()
        manager.lookup_resource_id.side_effect = ValueError("inventory not found")
        mock_get_manager.return_value = (manager, {})

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertFalse(result["changed"])
        self.assertIn("inventory not found", result["msg"])
        manager.launch_resource.assert_not_called()


class TestLaunchWithoutWait(unittest.TestCase):
    """Test launching without waiting."""

    @patch.object(ActionModule, "_get_or_spawn_manager")
    def test_launch_no_wait_by_default(self, mock_manager):
        module = _make_module(
            args={"inventory": "Demo", "credential": "Demo", "module_name": "ping"},
        )
        manager = _make_manager()
        manager.lookup_resource_id.side_effect = [1, 2]
        manager.launch_resource.return_value = {"id": 42, "status": "pending"}
        mock_manager.return_value = (manager, {})

        result = module.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertFalse(result["failed"])
        self.assertEqual(result["id"], 42)
        self.assertEqual(result["status"], "pending")
        manager.launch_resource.assert_called_once_with(
            "/api/controller/v2/ad_hoc_commands/",
            {"inventory": 1, "credential": 2, "module_name": "ping"},
            service="controller",
            retry=False,
        )
        manager.wait_for_completion.assert_not_called()


class TestLaunchWithWait(unittest.TestCase):
    """Test launching with waiting."""

    @patch.object(ActionModule, "_get_documentation")
    @patch.object(ActionModule, "_build_argspec_from_docs")
    @patch.object(ActionModule, "_validate_data")
    @patch.object(ActionModule, "_get_or_spawn_manager")
    def test_launch_with_wait_success(self, mock_manager, mock_validate, mock_argspec, mock_doc):
        module = _make_module(
            args={"inventory": "Demo", "credential": "Demo", "module_name": "ping", "wait": True},
        )
        mock_doc.return_value = {"options": {}}
        mock_argspec.return_value = {"inventory": {}}
        validated = MagicMock()
        validated.validated_parameters = {
            "inventory": "Demo",
            "credential": "Demo",
            "module_name": "ping",
            "wait": True,
            "interval": 2.0,
            "timeout": None,
        }
        mock_validate.return_value = validated
        manager = _make_manager()
        manager.lookup_resource_id.side_effect = [1, 2]
        manager.launch_resource.return_value = {"id": 42, "status": "pending"}
        manager.wait_for_completion.return_value = {"id": 42, "status": "successful"}
        mock_manager.return_value = (manager, {})

        result = module.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertFalse(result["failed"])
        self.assertEqual(result["id"], 42)
        self.assertEqual(result["status"], "successful")

    @patch.object(ActionModule, "_get_documentation")
    @patch.object(ActionModule, "_build_argspec_from_docs")
    @patch.object(ActionModule, "_validate_data")
    @patch.object(ActionModule, "_get_or_spawn_manager")
    def test_launch_with_wait_failure_status(self, mock_manager, mock_validate, mock_argspec, mock_doc):
        module = _make_module(
            args={"inventory": "Demo", "credential": "Demo", "module_name": "ping", "wait": True},
        )
        mock_doc.return_value = {"options": {}}
        mock_argspec.return_value = {"inventory": {}}
        validated = MagicMock()
        validated.validated_parameters = {
            "inventory": "Demo",
            "credential": "Demo",
            "module_name": "ping",
            "wait": True,
            "interval": 2.0,
            "timeout": None,
        }
        mock_validate.return_value = validated
        manager = _make_manager()
        manager.lookup_resource_id.side_effect = [1, 2] * 3
        manager.launch_resource.return_value = {"id": 42, "status": "pending"}
        manager.wait_for_completion.side_effect = [{"id": 42, "status": status} for status in ("failed", "error", "canceled")]
        mock_manager.return_value = (manager, {})

        for status in ("failed", "error", "canceled"):
            with self.subTest(status=status):
                result = module.run(task_vars={})

                self.assertTrue(result["changed"])
                self.assertTrue(result["failed"])
                self.assertEqual(result["status"], status)

    @patch.object(ActionModule, "_get_documentation")
    @patch.object(ActionModule, "_build_argspec_from_docs")
    @patch.object(ActionModule, "_validate_data")
    @patch.object(ActionModule, "_get_or_spawn_manager")
    def test_launch_with_wait_timeout(self, mock_manager, mock_validate, mock_argspec, mock_doc):
        module = _make_module(
            args={"inventory": "Demo", "credential": "Demo", "module_name": "ping", "wait": True},
        )
        mock_doc.return_value = {"options": {}}
        mock_argspec.return_value = {"inventory": {}}
        validated = MagicMock()
        validated.validated_parameters = {
            "inventory": "Demo",
            "credential": "Demo",
            "module_name": "ping",
            "wait": True,
            "interval": 2.0,
            "timeout": 10,
        }
        mock_validate.return_value = validated
        manager = _make_manager()
        manager.lookup_resource_id.side_effect = [1, 2]
        manager.launch_resource.return_value = {"id": 42, "status": "running"}
        exc = WaitTimeoutError("Timed out")
        exc.last_result = {"id": 42, "status": "running"}
        manager.wait_for_completion.side_effect = exc
        mock_manager.return_value = (manager, {})

        result = module.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertTrue(result["failed"])
        self.assertEqual(result["id"], 42)
        self.assertEqual(result["status"], "running")
        self.assertIn("Timed out", result["msg"])
        manager.wait_for_completion.assert_called_once_with(
            "/api/controller/v2/ad_hoc_commands/42/",
            timeout=10.0,
            interval=2.0,
            service="controller",
        )


class TestFKResolution(unittest.TestCase):
    """Test FK name-to-ID resolution."""

    @patch.object(ActionModule, "_get_documentation")
    @patch.object(ActionModule, "_build_argspec_from_docs")
    @patch.object(ActionModule, "_validate_data")
    @patch.object(ActionModule, "_get_or_spawn_manager")
    def test_inventory_and_credential_resolved(self, mock_manager, mock_validate, mock_argspec, mock_doc):
        module = _make_module(
            args={"inventory": "My Inv", "credential": "My Cred", "module_name": "ping", "wait": False},
        )
        mock_doc.return_value = {"options": {}}
        mock_argspec.return_value = {"inventory": {}}
        validated = MagicMock()
        validated.validated_parameters = {
            "inventory": "My Inv",
            "credential": "My Cred",
            "module_name": "ping",
            "wait": False,
        }
        mock_validate.return_value = validated
        manager = _make_manager()
        manager.lookup_resource_id.side_effect = [10, 20]
        manager.launch_resource.return_value = {"id": 1, "status": "pending"}
        mock_manager.return_value = (manager, {})

        module.run(task_vars={})

        calls = manager.lookup_resource_id.call_args_list
        self.assertEqual(calls[0].args, ("inventories", "name", "My Inv"))
        self.assertEqual(calls[0].kwargs, {"service": "controller", "require_unique": True})
        self.assertEqual(calls[1].args, ("credentials", "name", "My Cred"))
        self.assertEqual(calls[1].kwargs, {"service": "controller", "require_unique": True})
        post_data = manager.launch_resource.call_args.args[1]
        self.assertEqual(post_data["inventory"], 10)
        self.assertEqual(post_data["credential"], 20)

    @patch.object(ActionModule, "_get_documentation")
    @patch.object(ActionModule, "_build_argspec_from_docs")
    @patch.object(ActionModule, "_validate_data")
    @patch.object(ActionModule, "_get_or_spawn_manager")
    def test_execution_environment_resolved(self, mock_manager, mock_validate, mock_argspec, mock_doc):
        module = _make_module(
            args={
                "inventory": "Inv",
                "credential": "Cred",
                "module_name": "ping",
                "execution_environment": "My EE",
                "wait": False,
            },
        )
        mock_doc.return_value = {"options": {}}
        mock_argspec.return_value = {"inventory": {}}
        validated = MagicMock()
        validated.validated_parameters = {
            "inventory": "Inv",
            "credential": "Cred",
            "module_name": "ping",
            "execution_environment": "My EE",
            "wait": False,
        }
        mock_validate.return_value = validated
        manager = _make_manager()
        manager.lookup_resource_id.side_effect = [10, 20, 30]
        manager.launch_resource.return_value = {"id": 1, "status": "pending"}
        mock_manager.return_value = (manager, {})

        module.run(task_vars={})

        calls = manager.lookup_resource_id.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[2].args, ("execution_environments", "name", "My EE"))
        self.assertEqual(calls[2].kwargs, {"service": "controller", "require_unique": True})
        post_data = manager.launch_resource.call_args.args[1]
        self.assertEqual(post_data["execution_environment"], 30)


class TestExtraVarsSerialization(unittest.TestCase):
    """Test extra_vars dict → JSON string serialization."""

    @patch.object(ActionModule, "_get_documentation")
    @patch.object(ActionModule, "_build_argspec_from_docs")
    @patch.object(ActionModule, "_validate_data")
    @patch.object(ActionModule, "_get_or_spawn_manager")
    def test_extra_vars_dict_serialized_as_json(self, mock_manager, mock_validate, mock_argspec, mock_doc):
        module = _make_module(
            args={
                "inventory": "Inv",
                "credential": "Cred",
                "module_name": "ping",
                "extra_vars": {"foo": "bar"},
                "wait": False,
            },
        )
        mock_doc.return_value = {"options": {}}
        mock_argspec.return_value = {"inventory": {}}
        validated = MagicMock()
        validated.validated_parameters = {
            "inventory": "Inv",
            "credential": "Cred",
            "module_name": "ping",
            "extra_vars": {"foo": "bar"},
            "wait": False,
        }
        mock_validate.return_value = validated
        manager = _make_manager()
        manager.lookup_resource_id.side_effect = [10, 20]
        manager.launch_resource.return_value = {"id": 1, "status": "pending"}
        mock_manager.return_value = (manager, {})

        module.run(task_vars={})

        launch_call = manager.launch_resource.call_args
        post_data = launch_call.args[1]
        self.assertEqual(post_data["extra_vars"], json.dumps({"foo": "bar"}))


class TestOptionalFields(unittest.TestCase):
    """Test optional fields are included when provided."""

    @patch.object(ActionModule, "_get_documentation")
    @patch.object(ActionModule, "_build_argspec_from_docs")
    @patch.object(ActionModule, "_validate_data")
    @patch.object(ActionModule, "_get_or_spawn_manager")
    def test_optional_fields_forwarded(self, mock_manager, mock_validate, mock_argspec, mock_doc):
        module = _make_module(
            args={
                "inventory": "Inv",
                "credential": "Cred",
                "module_name": "command",
                "module_args": "echo hello",
                "job_type": "run",
                "limit": "webservers",
                "forks": 10,
                "verbosity": 3,
                "become_enabled": True,
                "diff_mode": True,
                "wait": False,
            },
        )
        mock_doc.return_value = {"options": {}}
        mock_argspec.return_value = {"inventory": {}}
        validated = MagicMock()
        validated.validated_parameters = {
            "inventory": "Inv",
            "credential": "Cred",
            "module_name": "command",
            "module_args": "echo hello",
            "job_type": "run",
            "limit": "webservers",
            "forks": 10,
            "verbosity": 3,
            "become_enabled": True,
            "diff_mode": True,
            "wait": False,
        }
        mock_validate.return_value = validated
        manager = _make_manager()
        manager.lookup_resource_id.side_effect = [10, 20]
        manager.launch_resource.return_value = {"id": 1, "status": "pending"}
        mock_manager.return_value = (manager, {})

        module.run(task_vars={})

        post_data = manager.launch_resource.call_args.args[1]
        self.assertEqual(post_data["module_name"], "command")
        self.assertEqual(post_data["module_args"], "echo hello")
        self.assertEqual(post_data["job_type"], "run")
        self.assertEqual(post_data["limit"], "webservers")
        self.assertEqual(post_data["forks"], 10)
        self.assertEqual(post_data["verbosity"], 3)
        self.assertTrue(post_data["become_enabled"])
        self.assertTrue(post_data["diff_mode"])


class TestNotFoundError(unittest.TestCase):
    """Test error when inventory/credential not found."""

    @patch.object(ActionModule, "_get_documentation")
    @patch.object(ActionModule, "_build_argspec_from_docs")
    @patch.object(ActionModule, "_validate_data")
    @patch.object(ActionModule, "_get_or_spawn_manager")
    def test_inventory_not_found(self, mock_manager, mock_validate, mock_argspec, mock_doc):
        module = _make_module(
            args={"inventory": "NoExist", "credential": "Cred", "module_name": "ping", "wait": False},
        )
        mock_doc.return_value = {"options": {}}
        mock_argspec.return_value = {"inventory": {}}
        validated = MagicMock()
        validated.validated_parameters = {
            "inventory": "NoExist",
            "credential": "Cred",
            "module_name": "ping",
            "wait": False,
        }
        mock_validate.return_value = validated
        manager = _make_manager()
        manager.lookup_resource_id.side_effect = ValueError("Resource 'inventories' with name=NoExist not found")
        mock_manager.return_value = (manager, {})

        result = module.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("not found", result["msg"])


if __name__ == "__main__":
    unittest.main()
