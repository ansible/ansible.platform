"""Tests for resolving resource IDs from names, IDs, and scoped named keys."""

from __future__ import absolute_import, division, print_function

import json
import unittest
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError, ValidationError

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

    def test_numeric_name_can_be_resolved_when_id_shortcut_is_disabled(self):
        for client in (_service(), _direct_client()):
            _set_responses(client, _response(body={"count": 1, "results": [{"id": 71, "name": "123"}]}))

            with self.subTest(client=type(client).__name__):
                self.assertEqual(_lookup(client, value="123", numeric_is_id=False), 71)
                self.assertEqual(_request_filters(client, _request_calls(client)[0]), {"name": ["123"]})

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
                APIError("Named URL not found", status_code=404),
                _response(body={"count": 1, "results": [{"id": 900, "name": "Default"}]}),
                _response(body={"count": 1, "results": [{"id": 71, "name": "Shared", "organization": 900}]}),
            )

            with self.subTest(client=type(client).__name__):
                self.assertEqual(_lookup(client, value="Shared++Default"), 71)
                calls = _request_calls(client)
                self.assertEqual(len(calls), 3)
                urls = [call.args[1] for call in calls]
                self.assertEqual(urlparse(urls[0]).path, "/api/controller/v2/inventories/Shared++Default/")
                self.assertEqual(urlparse(urls[1]).path, "/api/controller/v2/organizations/")
                self.assertEqual(_request_filters(client, calls[1]), {"name": ["Default"]})
                self.assertEqual(urlparse(urls[2]).path, "/api/controller/v2/inventories/")
                self.assertEqual(_request_filters(client, calls[2]), {"name": ["Shared"], "organization": ["900"]})

    def test_simple_controller_named_key_uses_server_resolution_first(self):
        for client in (_service(), _direct_client()):
            _set_responses(client, _response(body={"id": 71, "name": "Shared", "organization": 900}))

            with self.subTest(client=type(client).__name__):
                self.assertEqual(_lookup(client, value="Shared++Default"), 71)
                calls = _request_calls(client)
                self.assertEqual(len(calls), 1)
                self.assertEqual(urlparse(calls[0].args[1]).path, "/api/controller/v2/inventories/Shared++Default/")

    def test_numeric_organization_component_in_named_key_resolves_by_name(self):
        for client in (_service(), _direct_client()):
            _set_responses(
                client,
                APIError("Named URL not found", status_code=404),
                _response(body={"count": 1, "results": [{"id": 900, "name": "123"}]}),
                _response(body={"count": 1, "results": [{"id": 71, "name": "Shared", "organization": 900}]}),
            )

            with self.subTest(client=type(client).__name__):
                self.assertEqual(_lookup(client, value="Shared++123"), 71)
                calls = _request_calls(client)
                self.assertEqual(len(calls), 3)
                self.assertEqual(urlparse(calls[0].args[1]).path, "/api/controller/v2/inventories/Shared++123/")
                self.assertEqual(_request_filters(client, calls[1]), {"name": ["123"]})
                self.assertEqual(_request_filters(client, calls[2]), {"name": ["Shared"], "organization": ["900"]})

    def test_composite_controller_named_keys_use_server_resolution(self):
        named_keys = {
            "credentials": "My Credential++Source Control+scm++Default",
            "hosts": "my-host++Production Inventory++Default",
            "workflow_job_template_nodes": "node-identifier++Nightly Workflow++Default",
        }
        for client in (_service(), _direct_client()):
            for endpoint, named_key in named_keys.items():
                with self.subTest(client=type(client).__name__, endpoint=endpoint):
                    client._make_request.reset_mock()
                    _set_responses(client, _response(body={"id": 71, "name": named_key.split("++", 1)[0]}))

                    self.assertEqual(_lookup(client, endpoint=endpoint, value=named_key), 71)

                    calls = _request_calls(client)
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(
                        urlparse(calls[0].args[1]).path,
                        f"/api/controller/v2/{endpoint}/{named_key.replace(' ', '%20')}/",
                    )

    def test_credential_named_url_preserves_named_key_separators(self):
        named_key = "test_cred++Machine+ssh++"
        for client in (_service(), _direct_client()):
            _set_responses(client, _response(body={"id": 42, "name": "test_cred"}))

            with self.subTest(client=type(client).__name__):
                self.assertEqual(_lookup(client, endpoint="credentials", value=named_key), 42)
                calls = _request_calls(client)
                self.assertEqual(len(calls), 1)
                self.assertEqual(urlparse(calls[0].args[1]).path, "/api/controller/v2/credentials/test_cred++Machine+ssh++/")

    def test_credential_named_url_404_falls_back_to_full_key_lookup(self):
        named_key = "test_cred++Machine+ssh++"
        for client in (_service(), _direct_client()):
            _set_responses(
                client,
                APIError("Named URL not found", status_code=404),
                _response(body={"count": 1, "results": [{"id": 42, "name": named_key}]}),
            )

            with self.subTest(client=type(client).__name__):
                self.assertEqual(_lookup(client, endpoint="credentials", value=named_key), 42)
                calls = _request_calls(client)
                self.assertEqual(len(calls), 2)
                self.assertEqual(urlparse(calls[0].args[1]).path, "/api/controller/v2/credentials/test_cred++Machine+ssh++/")
                self.assertEqual(urlparse(calls[1].args[1]).path, "/api/controller/v2/credentials/")
                self.assertEqual(_request_filters(client, calls[1]), {"name": [named_key]})

    def test_composite_controller_key_fallback_does_not_treat_suffix_as_organization(self):
        named_key = "my-host++Production Inventory++Default"
        for client in (_service(), _direct_client()):
            _set_responses(
                client,
                APIError("Named URL not found", status_code=404),
                _response(body={"count": 0, "results": []}),
            )

            with self.subTest(client=type(client).__name__), self.assertRaisesRegex(ValueError, "not found"):
                _lookup(client, endpoint="hosts", value=named_key)

            calls = _request_calls(client)
            self.assertEqual(len(calls), 2)
            self.assertEqual(urlparse(calls[1].args[1]).path, "/api/controller/v2/hosts/")
            self.assertEqual(_request_filters(client, calls[1]), {"name": [named_key]})

    def test_trailing_named_url_separator_resolves_as_plain_name(self):
        for client in (_service(), _direct_client()):
            _set_responses(
                client,
                APIError("Named URL not found", status_code=404),
                _response(body={"count": 1, "results": [{"id": 71, "name": "Shared"}]}),
            )

            with self.subTest(client=type(client).__name__):
                self.assertEqual(_lookup(client, value="Shared++"), 71)
                calls = _request_calls(client)
                self.assertEqual(len(calls), 2)
                self.assertEqual(urlparse(calls[0].args[1]).path, "/api/controller/v2/inventories/Shared++/")
                self.assertEqual(_request_filters(client, calls[1]), {"name": ["Shared"]})

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

    def test_batch_lookup_url_budget_includes_scope_filters(self):
        endpoint = "/api/controller/v2/inventories/"
        filters = {"organization": int("9" * 50)}
        first_name = "a"
        second_name = "b" * 64
        first_query = {"name__in": first_name, **filters}

        for client in (_service(), _direct_client()):
            client.MAX_BATCH_LOOKUP_URL_BYTES = len(client._build_url(endpoint, first_query).encode("utf-8"))
            self.assertGreater(
                len(client._build_url(endpoint, {"name__in": f"{first_name},{second_name}"}).encode("utf-8")),
                client.MAX_BATCH_LOOKUP_URL_BYTES,
            )
            self.assertLessEqual(
                len(client._build_url(endpoint, {"name__in": second_name}).encode("utf-8")),
                client.MAX_BATCH_LOOKUP_URL_BYTES,
            )
            self.assertGreater(
                len(client._build_url(endpoint, {"name__in": second_name, **filters}).encode("utf-8")),
                client.MAX_BATCH_LOOKUP_URL_BYTES,
            )
            results = {
                first_name: {"id": 1, "name": first_name},
                second_name: {"id": 2, "name": second_name},
            }

            def search_api(_endpoint, query_params=None, **_kwargs):
                values = query_params.get("name__in", query_params.get("name")).split(",")
                return {"results": [results[value] for value in values]}

            client.search_api = MagicMock(side_effect=search_api)

            with self.subTest(client=type(client).__name__):
                self.assertEqual(
                    client._lookup_resource_ids(
                        "inventories",
                        "name",
                        [first_name, second_name],
                        service="controller",
                        extra_query_params=filters,
                    ),
                    {first_name: 1, second_name: 2},
                )
                queries = [call.kwargs["query_params"] for call in client.search_api.call_args_list]
                self.assertEqual(queries[0], {"name__in": first_name, "organization": filters["organization"]})
                self.assertEqual(queries[1], {"name": second_name, "organization": filters["organization"]})


if __name__ == "__main__":
    unittest.main()
