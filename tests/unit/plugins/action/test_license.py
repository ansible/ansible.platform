# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the license action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import base64
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from ansible.playbook.task import Task
from ansible_collections.ansible.platform.plugins.action.license import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient


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


def _licensed_config():
    return {
        "license_info": {
            "instance_count": 100,
            "valid_key": True,
            "trial": False,
            "license_type": "enterprise",
        },
    }


class TestLicenseAction(unittest.TestCase):
    """The action adapts Ansible inputs and delegates license behavior to the SDK."""

    def _run_with_prepare(self, module, manager, validated_params):
        with patch.object(module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": validated_params,
                "manager": manager,
            }
            return module.run(task_vars={})

    def test_manifest_contents_and_force_are_forwarded_to_sdk(self):
        for force in (False, True):
            with self.subTest(force=force):
                module = _make_module()
                manager = _make_manager()
                manager.execute.return_value = {"changed": True, **_licensed_config()}
                with tempfile.NamedTemporaryFile(suffix=".zip") as manifest_file:
                    manifest_file.write(b"fake-manifest-data")
                    manifest_file.flush()
                    with patch.object(module, "_find_needle", return_value=manifest_file.name) as find_file:
                        result = self._run_with_prepare(module, manager, {"state": "present", "manifest": "relative-manifest.zip", "force": force})

                find_file.assert_called_once_with("files", "relative-manifest.zip")
                manager.execute.assert_called_once()
                request = manager.execute.call_args.kwargs
                self.assertEqual(request["operation"], "create")
                self.assertEqual(request["module_name"], "license")
                self.assertEqual(request["ansible_data"]["manifest"], base64.b64encode(b"fake-manifest-data").decode("ascii"))
                self.assertIs(request["ansible_data"]["force"], force)
                self.assertEqual(result, {"changed": True, **_licensed_config()})
                self.assertNotIn("manifest", result)
                manager.post_resource.assert_not_called()

    def test_subscription_changed_status_and_message_come_from_sdk(self):
        for changed in (False, True):
            with self.subTest(changed=changed):
                module = _make_module()
                manager = _make_manager()
                sdk_result = {"changed": changed, **_licensed_config()}
                if not changed:
                    sdk_result["msg"] = "Already licensed. Use force=true to re-apply."
                manager.execute.return_value = sdk_result

                result = self._run_with_prepare(module, manager, {"state": "present", "subscription_id": "sub-123", "force": True})

                self.assertEqual(result, sdk_result)
                manager.execute.assert_called_once()
                request = manager.execute.call_args.kwargs
                self.assertEqual(request["operation"], "create")
                self.assertEqual(request["ansible_data"]["subscription_id"], "sub-123")
                self.assertIs(request["ansible_data"]["force"], True)
                manager.post_resource.assert_not_called()

    def test_absent_delegates_removal_and_noop_to_sdk(self):
        for sdk_result in ({"changed": True, "msg": "License removed"}, {"changed": False, "msg": "No license to remove"}):
            with self.subTest(result=sdk_result):
                module = _make_module()
                manager = _make_manager()
                manager.execute.return_value = sdk_result

                result = self._run_with_prepare(module, manager, {"state": "absent"})

                self.assertEqual(result, sdk_result)
                manager.execute.assert_called_once()
                request = manager.execute.call_args.kwargs
                self.assertEqual(request["operation"], "delete")
                self.assertNotIn("id", request["ansible_data"])
                manager.delete_resource.assert_not_called()

    def test_check_mode_is_forwarded_and_prediction_is_preserved(self):
        for state in ("present", "absent"):
            with self.subTest(state=state):
                module = _make_module(check_mode=True)
                manager = _make_manager()
                manager.execute.return_value = {"changed": True}

                result = self._run_with_prepare(module, manager, {"state": state, "subscription_id": "sub-123"})

                self.assertEqual(result, {"changed": True})
                manager.execute.assert_called_once()
                request = manager.execute.call_args.kwargs
                self.assertEqual(request["operation"], "delete" if state == "absent" else "create")
                self.assertIs(request["ansible_data"]["_platform_check_mode"], True)
                manager.post_resource.assert_not_called()
                manager.delete_resource.assert_not_called()

    def test_present_without_manifest_or_subscription(self):
        module = _make_module(args={"state": "present"})
        with self.assertRaisesRegex(Exception, "manifest|subscription_id"):
            module._validate_action_input()

    def test_sdk_validation_error_becomes_failed_module_result(self):
        module = _make_module()
        manager = _make_manager()
        manager.execute.side_effect = ValueError("Exactly one non-empty manifest or subscription_id is required")

        result = self._run_with_prepare(module, manager, {"state": "present", "manifest": "", "subscription_id": ""})

        self.assertIs(result["failed"], True)
        self.assertIs(result["changed"], False)
        self.assertIn("manifest or subscription_id", result["msg"])
        manager.post_resource.assert_not_called()

    def test_manifest_file_not_found_fails_before_sdk_call(self):
        from ansible.errors import AnsibleError

        module = _make_module()
        manager = _make_manager()
        with patch.object(module, "_find_needle", side_effect=AnsibleError("not found")):
            result = self._run_with_prepare(module, manager, {"state": "present", "manifest": "/nonexistent.zip"})

        self.assertIs(result["failed"], True)
        self.assertIs(result["changed"], False)
        manager.execute.assert_not_called()

    def test_unreadable_manifest_fails_before_sdk_call(self):
        module = _make_module()
        manager = _make_manager()
        with patch.object(module, "_find_needle", return_value="manifest.zip"), patch("builtins.open", side_effect=PermissionError("unreadable manifest")):
            result = self._run_with_prepare(module, manager, {"state": "present", "manifest": "manifest.zip"})

        self.assertIs(result["failed"], True)
        self.assertIn("unreadable manifest", result["msg"])
        manager.execute.assert_not_called()

    def test_sdk_api_failure_becomes_failed_module_result(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError

        module = _make_module()
        manager = _make_manager()
        manager.execute.side_effect = APIError("License rejected", status_code=400)

        result = self._run_with_prepare(module, manager, {"state": "present", "subscription_id": "sub-123"})

        self.assertIs(result["failed"], True)
        self.assertIn("License rejected", result["msg"])


class TestPostResourceRetry(unittest.TestCase):
    """Tests that post_resource respects the retry parameter."""

    def _make_service(self):
        import threading

        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.retry import RetryConfig

        svc = PlatformService.__new__(PlatformService)
        svc.record_activity = MagicMock()
        svc.session = MagicMock()
        svc.cache = {}
        svc.base_url = "https://gw.example.com"
        svc.request_timeout = 30
        svc.config = None
        svc.verify_ssl = True
        svc.ca_bundle = None
        svc.api_versions = {"controller": "2"}
        svc.registry = MagicMock()
        svc.registry.get_supported_versions.return_value = ["2"]
        svc.retry_config = RetryConfig(max_attempts=3, initial_delay=0, jitter=False)
        svc._lock = threading.Lock()
        svc._http_request_count = 0
        svc._handle_auth_error = MagicMock(return_value=False)
        return svc

    def test_post_resource_retry_false_uses_single_attempt(self):
        """retry=False should pass RetryConfig(max_attempts=1) to _make_request."""
        svc = self._make_service()
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b'{"ok": true}'
        resp.json.return_value = {"ok": True}
        svc._make_request = MagicMock(return_value=resp)

        svc.post_resource("config/", {"manifest": "data"}, service="controller", retry=False)

        call_kwargs = svc._make_request.call_args
        retry_config = call_kwargs.kwargs.get("retry_config") or call_kwargs[1].get("retry_config")
        self.assertIsNotNone(retry_config)
        self.assertEqual(retry_config.max_attempts, 1)

    def test_post_resource_retry_true_uses_default(self):
        """retry=True (default) should not pass a custom retry_config."""
        svc = self._make_service()
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b'{"ok": true}'
        resp.json.return_value = {"ok": True}
        svc._make_request = MagicMock(return_value=resp)

        svc.post_resource("config/", {"manifest": "data"}, service="controller")

        call_kwargs = svc._make_request.call_args
        retry_config = call_kwargs.kwargs.get("retry_config") or call_kwargs[1].get("retry_config")
        self.assertIsNone(retry_config)
