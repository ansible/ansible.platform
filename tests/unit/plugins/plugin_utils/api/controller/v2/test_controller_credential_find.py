# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for scoped and unique Controller credential lookups."""

from __future__ import absolute_import, division, print_function

import json
import threading
import unittest
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_credential import AnsibleControllerCredential
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_credential import ControllerCredentialTransformMixin_v2
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext


def _response(payload, direct):
    response = MagicMock()
    response.json.return_value = payload
    response.read.return_value = json.dumps(payload).encode() if direct else b""
    return response


def _client(client_mode, payload):
    if client_mode == "direct":
        client = DirectHTTPClient.__new__(DirectHTTPClient)
        client._lock = threading.Lock()
        client._http_request_count = 0
    else:
        client = PlatformService.__new__(PlatformService)
        client.cache = {}

    client.base_url = "https://gateway.example"
    client.api_versions = {"controller": "2"}
    client.session = MagicMock()
    client._make_request = MagicMock(return_value=_response(payload, direct=client_mode == "direct"))
    return client


def _context(client):
    return TransformContext(manager=client, session=client.session, cache={}, api_version="2", service="controller", operation="find")


class TestControllerCredentialFind(unittest.TestCase):
    """Credential matches use their name, type, and supplied owner scope."""

    def test_find_query_is_scoped_in_both_client_modes(self):
        payload = {
            "count": 1,
            "results": [{"id": 101, "name": "Shared", "credential_type": 2, "organization": 20}],
        }
        ansible = AnsibleControllerCredential(name="Shared", credential_type="2", organization="20")

        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode, payload)
                result = client._find_resource(ansible, ControllerCredentialTransformMixin_v2, _context(client))

                self.assertEqual(result["id"], 101)
                query = parse_qs(urlparse(client._make_request.call_args.args[1]).query)
                self.assertEqual(query["name"], ["Shared"])
                self.assertEqual(query["credential_type"], ["2"])
                self.assertEqual(query["organization"], ["20"])

    def test_duplicate_matches_in_scope_fail_in_both_client_modes(self):
        payload = {
            "count": 2,
            "results": [
                {"id": 101, "name": "Shared", "credential_type": 2, "organization": 20},
                {"id": 102, "name": "Shared", "credential_type": 2, "organization": 20},
            ],
        }
        ansible = AnsibleControllerCredential(name="Shared", credential_type="2", organization="20")

        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode, payload)

                with self.assertRaisesRegex(ValueError, "matched multiple resources"):
                    client._find_resource(ansible, ControllerCredentialTransformMixin_v2, _context(client))


if __name__ == "__main__":
    unittest.main()
