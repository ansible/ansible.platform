# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Regression tests for DirectHTTPClient.lookup_resource_id absolute-path handling (AAP-91390).

PlatformService.lookup_resource_id already supports being called with either a
bare resource name (e.g. "organizations", Gateway-prefixed) or a full API path
(e.g. "/api/controller/v2/organizations/", used as-is) — every FK lookup added
in this batch (inventory's organization, host's inventory, etc.) relies on the
latter. DirectHTTPClient.lookup_resource_id previously always applied the
Gateway prefix regardless, silently producing a malformed double-prefixed URL
for every Controller-routed lookup in direct connection mode.
"""

from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient


def _make_direct_client(base_url="https://gw.example.com"):
    """DirectHTTPClient with credential storage mocked; no real network access."""
    mock_store = MagicMock()
    mock_store.namespace.namespace_id = "ns"
    mock_store.get_auth_credentials.return_value = ("admin", "admin", None)
    with patch("ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client.get_credential_manager") as mock_cred:
        mock_cred.return_value.get_or_create_store.return_value = mock_store
        config = GatewayConfig(base_url=base_url, username="admin", password="admin", idle_timeout=30.0)
        return DirectHTTPClient(config)


def _fake_response(payload):
    resp = MagicMock()
    resp.read.return_value = __import__("json").dumps(payload).encode("utf-8")
    return resp


class TestDirectClientLookupResourceId(unittest.TestCase):
    def setUp(self):
        self.client = _make_direct_client()
        self.client.api_version = "1"  # skip version detection

    def test_bare_resource_name_gets_gateway_prefix(self):
        with patch.object(self.client, "_make_request", return_value=_fake_response({"results": [{"id": 5}]})) as mock_request:
            rid = self.client.lookup_resource_id("organizations", "name", "Default")

        called_url = mock_request.call_args[0][1]
        self.assertIn("/api/gateway/v1/organizations/", called_url)
        self.assertEqual(rid, 5)

    def test_absolute_controller_path_is_used_as_is(self):
        with patch.object(self.client, "_make_request", return_value=_fake_response({"results": [{"id": 7}]})) as mock_request:
            rid = self.client.lookup_resource_id("/api/controller/v2/organizations/", "name", "Default")

        called_url = mock_request.call_args[0][1]
        self.assertIn("/api/controller/v2/organizations/", called_url)
        self.assertNotIn("/api/gateway/", called_url)
        self.assertEqual(rid, 7)

    def test_absolute_path_without_trailing_slash_gets_one_added(self):
        with patch.object(self.client, "_make_request", return_value=_fake_response({"results": [{"id": 9}]})) as mock_request:
            self.client.lookup_resource_id("/api/controller/v2/inventories", "name", "Demo")

        called_url = mock_request.call_args[0][1]
        self.assertIn("/api/controller/v2/inventories/", called_url)


if __name__ == "__main__":
    unittest.main()
