"""Tests for resolving resource IDs from names, IDs, and scoped named keys."""

from __future__ import absolute_import, division, print_function

import json
import unittest
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import ValidationError

__metaclass__ = type


def _response(status=200, body=None):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = body or {}
    response.read.return_value = json.dumps(body or {}).encode("utf-8")
    response.raise_for_status.return_value = None
    return response


def _service():
    service = PlatformService.__new__(PlatformService)
    service.base_url = "https://gateway.example.com"
    service.session = MagicMock()
    service.api_versions = {"gateway": "2", "controller": "2", "eda": "2"}
    service.cache = {}
    service.request_timeout = 10
    service.verify_ssl = True
    service.ca_bundle = None
    service.get_api_version = MagicMock(return_value="2")
    service.record_activity = MagicMock()
    service._make_request = MagicMock()
    service.search_api = PlatformService.search_api.__get__(service, PlatformService)
    return service


def _direct_client():
    client = DirectHTTPClient.__new__(DirectHTTPClient)
    client.base_url = "https://gateway.example.com"
    client._authenticated = True
    client.api_versions = {"gateway": "2", "controller": "2", "eda": "2"}
    client.session = MagicMock()
    client.session.headers = {}
    client.cache = {}
    client.get_api_version = MagicMock(return_value="2")
    client._make_request = MagicMock()
    client.search_api = DirectHTTPClient.search_api.__get__(client, DirectHTTPClient)
    return client


def _lookup(client, endpoint="inventories", value="Shared", service="controller", **kwargs):
    return client.lookup_resource_id(endpoint, "name", value, service=service, **kwargs)


def _request_calls(client):
    return client._make_request.call_args_list


def _set_responses(client, *responses):
    client._make_request.side_effect = responses


def _request_filters(client, call):
    if isinstance(client, PlatformService):
        return {key: [str(value)] for key, value in call.kwargs.get("params", {}).items()}
    return parse_qs(urlparse(call.args[1]).query)


class TestResourceLookup(unittest.TestCase):
    def test_plain_name_resolves_for_both_clients(self):
        for client in (_service(), _direct_client()):
            _set_responses(client, _response(body={"count": 1, "results": [{"id": 71, "name": "Shared"}]}))

            with self.subTest(client=type(client).__name__):
                self.assertEqual(_lookup(client), 71)
                calls = _request_calls(client)
                self.assertEqual(len(calls), 1)
                self.assertEqual(_request_filters(client, calls[0]), {"name": ["Shared"]})

    def test_numeric_id_resolves_without_request_for_both_clients(self):
        for client in (_service(), _direct_client()):
            with self.subTest(client=type(client).__name__):
                self.assertEqual(_lookup(client, value="71"), 71)
                self.assertEqual(_request_calls(client), [])

    def test_organization_name_lookup_uses_requested_service(self):
        for client in (_service(), _direct_client()):
            _set_responses(client, _response(body={"id": 900, "name": "Default"}))

            with self.subTest(client=type(client).__name__):
                self.assertEqual(client.lookup_organization_names([900], service="controller"), ["Default"])
                call = _request_calls(client)[0]
                self.assertEqual(urlparse(call.args[1]).path, "/api/controller/v2/organizations/900/")

    def test_other_services_keep_their_server_side_named_key_resolution(self):
        for client in (_service(), _direct_client()):
            _set_responses(client, _response(body={"id": 71, "name": "Vault"}))

            with self.subTest(client=type(client).__name__):
                self.assertEqual(_lookup(client, endpoint="eda-credentials", value="Vault++Default", service="eda"), 71)
                calls = _request_calls(client)
                self.assertEqual(len(calls), 1)
                url = calls[0].args[1]
                self.assertTrue(urlparse(url).path.rstrip("/").endswith("/api/eda/v2/eda-credentials/Vault++Default"))

    def test_named_key_resolves_to_name_and_organization_filter(self):
        for client in (_service(), _direct_client()):
            _set_responses(
                client,
                _response(body={"count": 1, "results": [{"id": 900, "name": "Default"}]}),
                _response(body={"count": 1, "results": [{"id": 71, "name": "Shared", "organization": 900}]}),
            )

            with self.subTest(client=type(client).__name__):
                self.assertEqual(_lookup(client, value="Shared++Default"), 71)
                calls = _request_calls(client)
                self.assertEqual(len(calls), 2)
                urls = [call.args[1] for call in calls]
                self.assertEqual(urlparse(urls[0]).path, "/api/controller/v2/organizations/")
                self.assertEqual(_request_filters(client, calls[0]), {"name": ["Default"]})
                self.assertEqual(urlparse(urls[1]).path, "/api/controller/v2/inventories/")
                self.assertEqual(_request_filters(client, calls[1]), {"name": ["Shared"], "organization": ["900"]})

    def test_trailing_named_url_separator_resolves_as_plain_name(self):
        for client in (_service(), _direct_client()):
            _set_responses(client, _response(body={"count": 1, "results": [{"id": 71, "name": "Shared"}]}))

            with self.subTest(client=type(client).__name__):
                self.assertEqual(_lookup(client, value="Shared++"), 71)
                calls = _request_calls(client)
                self.assertEqual(len(calls), 1)
                self.assertEqual(_request_filters(client, calls[0]), {"name": ["Shared"]})

    def test_named_key_must_match_explicit_organization_scope(self):
        for client in (_service(), _direct_client()):
            _set_responses(client, _response(body={"count": 1, "results": [{"id": 9, "name": "Default"}]}))

            with self.subTest(client=type(client).__name__), self.assertRaisesRegex(ValueError, "conflicts with organization scope"):
                _lookup(client, value="Shared++Default", extra_query_params={"organization": 10})
            self.assertEqual(len(_request_calls(client)), 1)

    def test_unscoped_duplicate_names_are_rejected_by_default(self):
        for client in (_service(), _direct_client()):
            _set_responses(
                client,
                _response(body={"count": 2, "results": [{"id": 1, "name": "Shared"}, {"id": 2, "name": "Shared"}]}),
            )

            with self.subTest(client=type(client).__name__), self.assertRaisesRegex(ValueError, "matched multiple resources"):
                _lookup(client)

    def test_duplicate_names_across_organizations_resolve_with_explicit_scope(self):
        inventories = [
            {"id": 10, "name": "Shared", "organization": 1},
            {"id": 20, "name": "Shared", "organization": 2},
        ]
        for client in (_service(), _direct_client()):

            def respond(*args, **kwargs):
                url = args[1]
                if isinstance(client, PlatformService):
                    filters = {key: [str(value)] for key, value in kwargs.get("params", {}).items()}
                else:
                    filters = parse_qs(urlparse(url).query)
                matches = [item for item in inventories if str(item["organization"]) == filters["organization"][0]]
                return _response(body={"count": len(matches), "results": matches})

            client._make_request.side_effect = respond

            with self.subTest(client=type(client).__name__):
                self.assertEqual(_lookup(client, value="Shared", extra_query_params={"organization": 1}), 10)
                self.assertEqual(_lookup(client, value="Shared", extra_query_params={"organization": 2}), 20)

    def test_organization_name_scope_is_resolved_before_resource_lookup(self):
        for client in (_service(), _direct_client()):
            _set_responses(
                client,
                _response(body={"count": 1, "results": [{"id": 900, "name": "Default"}]}),
                _response(body={"count": 1, "results": [{"id": 71, "name": "Shared", "organization": 900}]}),
            )

            with self.subTest(client=type(client).__name__):
                self.assertEqual(_lookup(client, value="Shared", extra_query_params={"organization": "Default"}), 71)
                calls = _request_calls(client)
                self.assertEqual(len(calls), 2)
                self.assertEqual(urlparse(calls[0].args[1]).path, "/api/controller/v2/organizations/")
                self.assertEqual(_request_filters(client, calls[1]), {"name": ["Shared"], "organization": ["900"]})

    def test_scope_is_part_of_each_clients_cache_key(self):
        for client in (_service(), _direct_client()):
            key_one = client._resource_lookup_cache_key("controller", "inventories", "name", "Shared", {"organization": 1})
            key_two = client._resource_lookup_cache_key("controller", "inventories", "name", "Shared", {"organization": 2})
            self.assertNotEqual(key_one, key_two)

    def test_unique_lookup_bypasses_first_match_cache(self):
        for client in (_service(), _direct_client()):
            _set_responses(
                client,
                _response(body={"count": 1, "results": [{"id": 71, "name": "Shared"}]}),
                _response(body={"count": 2, "results": [{"id": 71, "name": "Shared"}, {"id": 72, "name": "Shared"}]}),
            )

            with self.subTest(client=type(client).__name__):
                self.assertEqual(_lookup(client, value="Shared", require_unique=False), 71)
                self.assertEqual(_lookup(client, value="Shared", require_unique=False), 71)
                with self.assertRaisesRegex(ValueError, "matched multiple resources"):
                    _lookup(client, value="Shared", require_unique=True)
                self.assertEqual(len(_request_calls(client)), 2)

    def test_batch_lookup_rechecks_uniqueness_instead_of_caching_results(self):
        for client in (_service(), _direct_client()):
            _set_responses(
                client,
                _response(body={"count": 2, "results": [{"id": 71, "name": "Shared"}, {"id": 72, "name": "Other"}]}),
                _response(
                    body={
                        "count": 3,
                        "results": [
                            {"id": 71, "name": "Shared"},
                            {"id": 73, "name": "Shared"},
                            {"id": 72, "name": "Other"},
                        ],
                    }
                ),
            )

            with self.subTest(client=type(client).__name__):
                self.assertEqual(client._lookup_resource_ids("inventories", "name", ["Shared", "Other"], service="controller"), {"Shared": 71, "Other": 72})
                with self.assertRaisesRegex(ValidationError, "matched multiple resources"):
                    client._lookup_resource_ids("inventories", "name", ["Shared", "Other"], service="controller")
                self.assertEqual(len(_request_calls(client)), 2)


if __name__ == "__main__":
    unittest.main()
