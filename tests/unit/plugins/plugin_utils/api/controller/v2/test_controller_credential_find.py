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
        client._authenticated = True
        client.api_versions = {"controller": "2"}
        client.api_version = "2"
    else:
        client = PlatformService.__new__(PlatformService)
        client.cache = {}
        client.record_activity = MagicMock()

    client.base_url = "https://gateway.example"
    client.api_versions = {"controller": "2"}
    client.session = MagicMock()
    client._make_request = MagicMock(return_value=_response(payload, direct=client_mode == "direct"))
    return client


def _context(client):
    return TransformContext(manager=client, session=client.session, cache={}, api_version="2", service="controller", operation="find")


def _query_params(client, client_mode):
    request = client._make_request.call_args
    if client_mode != "direct" and "params" in request.kwargs:
        return {key: [str(value)] for key, value in request.kwargs["params"].items()}
    return parse_qs(urlparse(request.args[1]).query)


class TestControllerCredentialFind(unittest.TestCase):
    """Credential matches use their name, type, and supplied owner scope."""

    def test_owner_scope_selects_matching_duplicate_before_uniqueness_check(self):
        owner_cases = (("team", "team", "31", "32"), ("user", "user", "41", "42"))

        for owner_field, owner_type, requested_id, other_id in owner_cases:
            payload = {
                "count": 2,
                "results": [
                    {"id": 101, "name": "Shared", "credential_type": 2, "summary_fields": {"owners": [{"id": requested_id, "type": owner_type}]}},
                    {"id": 102, "name": "Shared", "credential_type": 2, "summary_fields": {"owners": [{"id": other_id, "type": owner_type}]}},
                ],
            }
            ansible = AnsibleControllerCredential(name="Shared", credential_type="2", **{owner_field: requested_id})

            for client_mode in ("direct", "persistent"):
                with self.subTest(owner=owner_field, client=client_mode):
                    client = _client(client_mode, payload)

                    result = client._find_resource(ansible, ControllerCredentialTransformMixin_v2, _context(client))

                    self.assertEqual(result["id"], 101)
                    self.assertEqual(result[owner_field], requested_id)
                    query = _query_params(client, client_mode)
                    self.assertNotIn(owner_field, query)

    def test_owner_scope_is_applied_across_all_result_pages(self):
        first_page = {
            "count": 2,
            "next": "/api/controller/v2/credentials/?page=2",
            "results": [{"id": 102, "name": "Shared", "credential_type": 2, "summary_fields": {"owners": [{"id": 32, "type": "team"}]}}],
        }
        second_page = {
            "count": 2,
            "next": None,
            "results": [{"id": 101, "name": "Shared", "credential_type": 2, "summary_fields": {"owners": [{"id": 31, "type": "team"}]}}],
        }
        ansible = AnsibleControllerCredential(name="Shared", credential_type="2", team="31")

        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode, first_page)
                client._make_request.side_effect = [
                    _response(first_page, direct=client_mode == "direct"),
                    _response(second_page, direct=client_mode == "direct"),
                ]

                result = client._find_resource(ansible, ControllerCredentialTransformMixin_v2, _context(client))

                self.assertEqual(result["id"], 101)
                self.assertEqual(client._make_request.call_count, 2)

    def test_multiple_credentials_with_same_requested_owner_remain_ambiguous(self):
        payload = {
            "count": 2,
            "results": [
                {"id": 101, "name": "Shared", "credential_type": 2, "summary_fields": {"owners": [{"id": 31, "type": "team"}]}},
                {"id": 102, "name": "Shared", "credential_type": 2, "summary_fields": {"owners": [{"id": 31, "type": "team"}]}},
            ],
        }
        ansible = AnsibleControllerCredential(name="Shared", credential_type="2", team="31")

        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode, payload)

                with self.assertRaisesRegex(ValueError, "matched multiple resources"):
                    client._find_resource(ansible, ControllerCredentialTransformMixin_v2, _context(client))

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
                query = _query_params(client, client_mode)
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
