# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for PlatformService wait/poll (ad_hoc_command execute(wait=True))."""

from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import DEFAULT_WAIT_TIMEOUT, WaitTimeoutError
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig


def _make_platform_service(base_url="https://gw.example.com"):
    """PlatformService with network and credentials mocked."""
    mock_session = MagicMock()
    mock_requests = MagicMock()
    mock_requests.Session.return_value = mock_session
    mock_store = MagicMock()
    mock_store.get_auth_credentials.return_value = ("admin", "admin", None)
    with patch("ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager.get_credential_manager") as mock_cred:
        mock_cred.return_value.get_or_create_store.return_value = mock_store
        with patch("ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager._get_requests") as mock_get_requests:
            mock_get_requests.return_value = mock_requests
            config = GatewayConfig(base_url=base_url, username="admin", password="admin", idle_timeout=30.0)
            return PlatformService(config)


def _ansible_data():
    return {
        "inventory": "Demo Inventory",
        "credential": "Demo Credential",
        "module_name": "ping",
    }


class TestExecuteWait(unittest.TestCase):
    def setUp(self):
        self.svc = _make_platform_service()

    def test_poll_to_completion(self):
        """Case 1: create returns pending, find polls to a finished result."""
        pending = {"id": 1, "status": "pending", "finished": None, "event_processing_finished": False}
        finished = {"id": 1, "status": "successful", "finished": "2026-01-01T00:00:00Z", "event_processing_finished": True}

        with patch.object(self.svc, "_create_resource", return_value=dict(pending)):
            with patch.object(self.svc, "_find_resource", side_effect=[dict(pending), dict(finished)]) as mock_find:
                with patch("ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager.time.sleep"):
                    result = self.svc.execute(
                        operation="create",
                        module_name="ad_hoc_command",
                        ansible_data_dict={**_ansible_data(), "wait": True, "interval": 0, "timeout": 5},
                    )

        self.assertEqual(result["status"], "successful")
        self.assertEqual(mock_find.call_count, 2)

    def test_timeout_raises_and_preserves_id(self):
        """Case 2: timeout raises WaitTimeoutError carrying the last poll result (id/status)."""
        pending = {"id": 7, "status": "pending", "finished": None, "event_processing_finished": False}

        # timeout=0 with real time.monotonic(): elapsed is always >= 0, so the
        # raise fires after exactly one _find_resource call — no need to mock
        # time itself (record_activity() elsewhere also calls time.monotonic(),
        # which would desync a fixed side_effect list).
        with patch.object(self.svc, "_create_resource", return_value=dict(pending)):
            with patch.object(self.svc, "_find_resource", return_value=dict(pending)) as mock_find:
                with patch("ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager.time.sleep"):
                    with self.assertRaises(ValueError) as ctx:
                        self.svc.execute(
                            operation="create",
                            module_name="ad_hoc_command",
                            ansible_data_dict={**_ansible_data(), "wait": True, "interval": 0, "timeout": 0},
                        )

        self.assertEqual(mock_find.call_count, 1)
        self.assertIsInstance(ctx.exception, WaitTimeoutError)
        self.assertIn("Timed out waiting for ad_hoc_command", str(ctx.exception))
        self.assertEqual(ctx.exception.last_result.get("id"), 7)
        self.assertEqual(ctx.exception.last_result.get("status"), "pending")

    def test_default_timeout_applied_when_omitted(self):
        """Case 3: wait=True with no timeout key uses DEFAULT_WAIT_TIMEOUT (3600.0)."""
        pending = {"id": 1, "status": "pending", "finished": None, "event_processing_finished": False}
        finished = {"id": 1, "status": "successful", "finished": "now", "event_processing_finished": True}

        with patch.object(self.svc, "_create_resource", return_value=dict(pending)):
            with patch.object(self.svc, "_find_resource", return_value=dict(finished)):
                with patch.object(self.svc, "_wait_for_resource_completion", wraps=self.svc._wait_for_resource_completion) as spy:
                    self.svc.execute(
                        operation="create",
                        module_name="ad_hoc_command",
                        ansible_data_dict={**_ansible_data(), "wait": True, "interval": 0},
                    )

        self.assertEqual(spy.call_args.args[-1], DEFAULT_WAIT_TIMEOUT)

    def test_wait_flags_popped_before_dataclass_construction(self):
        """Case 5: wait/interval/timeout must not reach AnsibleAdHocCommand(**...)."""
        finished = {"id": 1, "status": "successful", "finished": "now", "event_processing_finished": True}

        with patch.object(self.svc, "_create_resource", return_value=dict(finished)):
            # No TypeError means wait/interval/timeout were popped before AnsibleClass(**ansible_data_dict).
            result = self.svc.execute(
                operation="create",
                module_name="ad_hoc_command",
                ansible_data_dict={**_ansible_data(), "wait": False, "interval": 2.0, "timeout": 30},
            )

        self.assertEqual(result["status"], "successful")


class TestLookupResourceIdControllerPath(unittest.TestCase):
    """Regression test for #10: passing a full Controller path must not be
    silently rewritten to a Gateway path by _build_url."""

    def setUp(self):
        self.svc = _make_platform_service()

    def test_full_api_path_is_not_gateway_prefixed(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"id": 42}]}
        self.svc.session.get.return_value = mock_response

        rid = self.svc.lookup_resource_id("/api/controller/v2/inventories/", "name", "Demo Inventory")

        self.assertEqual(rid, 42)
        called_url = self.svc.session.get.call_args.args[0]
        self.assertIn("/api/controller/v2/inventories/", called_url)
        self.assertNotIn("/api/gateway/", called_url)


if __name__ == "__main__":
    unittest.main()
