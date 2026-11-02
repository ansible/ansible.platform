# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the license action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import base64
import os
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


def _unlicensed_config():
    return {
        "license_info": {},
    }


class TestLicenseAction(unittest.TestCase):
    """Tests for license action plugin."""

    def _run_with_prepare(self, module, manager, validated_params):
        with patch.object(module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": validated_params,
                "manager": manager,
            }
            return module.run(task_vars={})

    def test_absent_no_license(self):
        """state=absent with no existing license returns changed=False."""
        module = _make_module()
        manager = _make_manager()
        manager.execute.return_value = _unlicensed_config()

        result = self._run_with_prepare(module, manager, {"state": "absent"})

        self.assertFalse(result["changed"])
        self.assertIn("No license", result["msg"])
        manager.delete_resource.assert_not_called()

    def test_absent_removes_license(self):
        """state=absent with existing license calls delete_resource."""
        module = _make_module()
        manager = _make_manager()
        manager.execute.return_value = _licensed_config()
        manager.delete_resource.return_value = {}

        result = self._run_with_prepare(module, manager, {"state": "absent"})

        self.assertTrue(result["changed"])
        manager.delete_resource.assert_called_once_with("config/", service="controller")

    def test_absent_check_mode(self):
        """state=absent in check mode does not call delete."""
        module = _make_module(check_mode=True)
        manager = _make_manager()
        manager.execute.return_value = _licensed_config()

        result = self._run_with_prepare(module, manager, {"state": "absent"})

        self.assertTrue(result["changed"])
        manager.delete_resource.assert_not_called()

    def test_manifest_already_licensed_no_force(self):
        """Manifest with existing license and no force returns changed=False."""
        module = _make_module()
        manager = _make_manager()
        manager.execute.return_value = _licensed_config()

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(b"fake-manifest-data")
            manifest_path = f.name

        try:
            with patch.object(module, "_find_needle", return_value=manifest_path):
                result = self._run_with_prepare(module, manager, {"state": "present", "manifest": manifest_path})
        finally:
            os.unlink(manifest_path)

        self.assertFalse(result["changed"])
        self.assertIn("Already licensed", result["msg"])

    def test_manifest_creates_license(self):
        """Manifest POST uses execute('create') through SDK."""
        module = _make_module()
        manager = _make_manager()
        manager.execute.side_effect = [
            _unlicensed_config(),
            {"changed": True, "license_info": _licensed_config()["license_info"]},
        ]

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(b"fake-manifest-data")
            manifest_path = f.name

        try:
            with patch.object(module, "_find_needle", return_value=manifest_path):
                result = self._run_with_prepare(module, manager, {"state": "present", "manifest": manifest_path})
        finally:
            os.unlink(manifest_path)

        self.assertTrue(result["changed"])
        calls = manager.execute.call_args_list
        self.assertEqual(calls[0][1]["operation"], "find")
        self.assertEqual(calls[1][1]["operation"], "create")
        manifest_b64 = base64.b64encode(b"fake-manifest-data").decode()
        self.assertEqual(calls[1][1]["ansible_data"]["manifest"], manifest_b64)

    def test_manifest_check_mode(self):
        """Manifest in check mode returns changed=True without API call."""
        module = _make_module(check_mode=True)
        manager = _make_manager()
        manager.execute.return_value = _unlicensed_config()

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(b"fake-manifest-data")
            manifest_path = f.name

        try:
            with patch.object(module, "_find_needle", return_value=manifest_path):
                result = self._run_with_prepare(module, manager, {"state": "present", "manifest": manifest_path})
        finally:
            os.unlink(manifest_path)

        self.assertTrue(result["changed"])
        self.assertEqual(manager.execute.call_count, 1)

    def test_subscription_creates_license(self):
        """Subscription uses post_resource with attach endpoint and retry=False."""
        module = _make_module()
        manager = _make_manager()
        manager.execute.side_effect = [
            _unlicensed_config(),
            _licensed_config(),
        ]
        manager.post_resource.return_value = {}

        result = self._run_with_prepare(module, manager, {"state": "present", "subscription_id": "sub-123"})

        self.assertTrue(result["changed"])
        manager.post_resource.assert_called_once_with(
            "config/attach/",
            {"subscription_id": "sub-123"},
            service="controller",
            retry=False,
        )

    def test_subscription_already_licensed_no_force(self):
        """Subscription with existing license and no force returns changed=False."""
        module = _make_module()
        manager = _make_manager()
        manager.execute.return_value = _licensed_config()

        result = self._run_with_prepare(module, manager, {"state": "present", "subscription_id": "sub-123"})

        self.assertFalse(result["changed"])
        manager.post_resource.assert_not_called()

    def test_manifest_with_force_reapplies(self):
        """force=True bypasses the already-licensed check."""
        module = _make_module()
        manager = _make_manager()
        manager.execute.side_effect = [
            _licensed_config(),
            {"changed": True, "license_info": _licensed_config()["license_info"]},
        ]

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(b"fake-manifest-data")
            manifest_path = f.name

        try:
            with patch.object(module, "_find_needle", return_value=manifest_path):
                result = self._run_with_prepare(module, manager, {"state": "present", "manifest": manifest_path, "force": True})
        finally:
            os.unlink(manifest_path)

        self.assertTrue(result["changed"])
        self.assertEqual(manager.execute.call_count, 2)

    def test_present_without_manifest_or_subscription(self):
        """state=present without manifest or subscription_id fails."""
        module = _make_module()
        manager = _make_manager()

        result = self._run_with_prepare(module, manager, {"state": "present"})

        self.assertTrue(result["failed"])
        self.assertIn("manifest", result["msg"])

    def test_manifest_file_not_found(self):
        """Missing manifest file returns failed result."""
        module = _make_module()
        manager = _make_manager()

        from ansible.errors import AnsibleError

        with patch.object(module, "_find_needle", side_effect=AnsibleError("not found")):
            result = self._run_with_prepare(module, manager, {"state": "present", "manifest": "/nonexistent.zip"})

        self.assertTrue(result["failed"])


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
