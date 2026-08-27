# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for DirectHTTPClient wait/poll and Controller-path lookups (ad_hoc_command)."""

from __future__ import absolute_import, division, print_function

import json
import unittest
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import DEFAULT_WAIT_TIMEOUT, WaitTimeoutError
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import EndpointOperation


def _make_direct_client(base_url="https://gw.example.com"):
    """DirectHTTPClient with credential storage mocked; auth/version pre-set so
    execute() skips its lazy first-request auth/version-detection HTTP calls."""
    mock_store = MagicMock()
    mock_store.get_auth_credentials.return_value = ("admin", "admin", None)
    mock_store.namespace.namespace_id = "test-namespace"
    with patch("ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client.get_credential_manager") as mock_cred:
        mock_cred.return_value.get_or_create_store.return_value = mock_store
        config = GatewayConfig(base_url=base_url, username="admin", password="admin")
        client = DirectHTTPClient(config)
    client._authenticated = True
    client.api_version = "1"
    return client


def _ansible_data():
    return {
        "inventory": "Demo Inventory",
        "credential": "Demo Credential",
        "module_name": "ping",
    }


class TestExecuteWait(unittest.TestCase):
    def setUp(self):
        self.client = _make_direct_client()

    def test_poll_to_completion(self):
        pending = {"id": 1, "status": "pending", "finished": None, "event_processing_finished": False}
        finished = {"id": 1, "status": "successful", "finished": "2026-01-01T00:00:00Z", "event_processing_finished": True}

        with patch.object(self.client, "_create_resource", return_value=dict(pending)):
            with patch.object(self.client, "_find_resource", side_effect=[dict(pending), dict(finished)]) as mock_find:
                with patch("ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client.time.sleep"):
                    result = self.client.execute(
                        operation="create",
                        module_name="ad_hoc_command",
                        ansible_data_dict={**_ansible_data(), "wait": True, "interval": 0, "timeout": 5},
                    )

        self.assertEqual(result["status"], "successful")
        self.assertEqual(mock_find.call_count, 2)

    def test_timeout_raises_and_preserves_id(self):
        pending = {"id": 7, "status": "pending", "finished": None, "event_processing_finished": False}

        with patch.object(self.client, "_create_resource", return_value=dict(pending)):
            with patch.object(self.client, "_find_resource", return_value=dict(pending)) as mock_find:
                with patch("ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client.time.sleep"):
                    with self.assertRaises(ValueError) as ctx:
                        self.client.execute(
                            operation="create",
                            module_name="ad_hoc_command",
                            ansible_data_dict={**_ansible_data(), "wait": True, "interval": 0, "timeout": 0},
                        )

        self.assertEqual(mock_find.call_count, 1)
        self.assertIsInstance(ctx.exception, WaitTimeoutError)
        self.assertEqual(ctx.exception.last_result.get("id"), 7)
        self.assertEqual(ctx.exception.last_result.get("status"), "pending")

    def test_default_timeout_applied_when_omitted(self):
        pending = {"id": 1, "status": "pending", "finished": None, "event_processing_finished": False}
        finished = {"id": 1, "status": "successful", "finished": "now", "event_processing_finished": True}

        with patch.object(self.client, "_create_resource", return_value=dict(pending)):
            with patch.object(self.client, "_find_resource", return_value=dict(finished)):
                with patch.object(self.client, "_wait_for_resource_completion", wraps=self.client._wait_for_resource_completion) as spy:
                    self.client.execute(
                        operation="create",
                        module_name="ad_hoc_command",
                        ansible_data_dict={**_ansible_data(), "wait": True, "interval": 0},
                    )

        self.assertEqual(spy.call_args.args[-1], DEFAULT_WAIT_TIMEOUT)

    def test_wait_flags_popped_before_dataclass_construction(self):
        finished = {"id": 1, "status": "successful", "finished": "now", "event_processing_finished": True}

        with patch.object(self.client, "_create_resource", return_value=dict(finished)):
            # No TypeError means wait/interval/timeout were popped before AnsibleClass(**ansible_data_dict).
            result = self.client.execute(
                operation="create",
                module_name="ad_hoc_command",
                ansible_data_dict={**_ansible_data(), "wait": False, "interval": 2.0, "timeout": 30},
            )

        self.assertEqual(result["status"], "successful")


@dataclass
class _LaunchOnlyAnsibleModel:
    """Minimal launch-style resource: only create+get, no list — the exact
    shape that triggered #7 (DirectHTTPClient required a list op before it
    would even attempt a GET-by-id)."""

    name: str = "x"
    id: Optional[int] = None
    status: Optional[str] = None
    finished: Optional[str] = None


@dataclass
class _LaunchOnlyAPIModel:
    name: str = "x"
    id: Optional[int] = None
    status: Optional[str] = None


class _LaunchOnlyMixin:
    """Transform mixin with create+get only — deliberately no 'list' op."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context):
        return _LaunchOnlyAPIModel(name=ansible_instance.name)

    @classmethod
    def from_api(cls, api_data, context):
        return _LaunchOnlyAnsibleModel(
            id=api_data.get("id"),
            status=api_data.get("status"),
            finished=api_data.get("finished"),
        )

    @classmethod
    def get_endpoint_operations(cls):
        return {
            "create": EndpointOperation(path="/api/controller/v2/launch_only/", method="POST", fields=["name"], required_for="create", order=1),
            "get": EndpointOperation(path="/api/controller/v2/launch_only/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls):
        return "id"


class TestFindResourceWithoutListOp(unittest.TestCase):
    """Regression test for #7: GET-by-id must work for a mixin that only
    defines create+get, without requiring a list operation."""

    def setUp(self):
        self.client = _make_direct_client()

    def test_get_by_id_does_not_require_list_op(self):
        ansible_data = _LaunchOnlyAnsibleModel(id=42)
        response_body = json.dumps({"id": 42, "status": "successful", "finished": "now"}).encode("utf-8")
        mock_response = MagicMock()
        mock_response.read.return_value = response_body

        with patch.object(self.client, "_make_request", return_value=mock_response) as mock_req:
            result = self.client._find_resource(ansible_data, _LaunchOnlyMixin, context=MagicMock())

        self.assertEqual(result["status"], "successful")
        called_url = mock_req.call_args.args[1]
        self.assertIn("/api/controller/v2/launch_only/42/", called_url)


class TestLookupResourceIdControllerPath(unittest.TestCase):
    """Regression test for #10: a full Controller path passed to
    lookup_resource_id must not be rewritten to a Gateway path."""

    def setUp(self):
        self.client = _make_direct_client()

    def test_full_api_path_is_not_gateway_prefixed(self):
        response_body = json.dumps({"results": [{"id": 99}]}).encode("utf-8")
        mock_response = MagicMock()
        mock_response.read.return_value = response_body

        with patch.object(self.client, "_make_request", return_value=mock_response) as mock_req:
            rid = self.client.lookup_resource_id("/api/controller/v2/inventories/", "name", "Demo Inventory")

        self.assertEqual(rid, 99)
        called_url = mock_req.call_args.args[1]
        self.assertIn("/api/controller/v2/inventories/", called_url)
        self.assertNotIn("/api/gateway/", called_url)


if __name__ == "__main__":
    unittest.main()
