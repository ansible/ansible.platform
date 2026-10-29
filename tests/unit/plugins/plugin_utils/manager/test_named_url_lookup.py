"""Tests for resolving AWX-style named resource URLs."""

from __future__ import absolute_import, division, print_function

import json
import unittest
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError

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
    service.cache = {}
    service.request_timeout = 10
    service.verify_ssl = True
    service.ca_bundle = None
    service.get_api_version = MagicMock(return_value="2")
    service.record_activity = MagicMock()
    return service


def _direct_client():
    client = DirectHTTPClient.__new__(DirectHTTPClient)
    client.base_url = "https://gateway.example.com"
    client.session = MagicMock()
    client.session.headers = {}
    client.cache = {}
    client.get_api_version = MagicMock(return_value="2")
    client._make_request = MagicMock()
    return client


class TestNamedURLLookup(unittest.TestCase):
    def test_platform_service_resolves_named_url_before_name_search(self):
        service = _service()
        service.session.get.return_value = _response(body={"id": 71, "name": "Shared Inventory"})

        result = PlatformService.lookup_resource_id(service, "inventories", "name", "Default++Shared Inventory", service="controller")

        self.assertEqual(result, 71)
        service.session.get.assert_called_once_with(
            "https://gateway.example.com/api/controller/v2/inventories/Default++Shared%20Inventory/", timeout=10, verify=True
        )

    def test_platform_service_applies_scope_to_named_url_lookup(self):
        service = _service()
        service.session.get.return_value = _response(body={"count": 1, "results": [{"id": 72, "name": "Shared Inventory"}]})

        result = PlatformService.lookup_resource_id(
            service,
            "inventories",
            "name",
            "Default++Shared Inventory",
            service="controller",
            extra_query_params={"organization": 9},
        )

        self.assertEqual(result, 72)
        service.session.get.assert_called_once()
        request_url = urlparse(service.session.get.call_args.args[0])
        self.assertEqual(request_url.path, "/api/controller/v2/inventories/")
        self.assertEqual(parse_qs(request_url.query), {"name": ["Default++Shared Inventory"], "organization": ["9"]})

    def test_platform_service_falls_back_to_name_search_when_named_url_is_missing(self):
        service = _service()
        service.session.get.side_effect = [
            _response(status=404),
            _response(body={"count": 1, "results": [{"id": 71, "name": "Default++Shared Inventory"}]}),
        ]

        result = PlatformService.lookup_resource_id(service, "inventories", "name", "Default++Shared Inventory", service="controller")

        self.assertEqual(result, 71)
        self.assertEqual(service.session.get.call_count, 2)

    def test_direct_client_resolves_named_url_before_name_search(self):
        client = _direct_client()
        client._make_request.return_value = _response(body={"id": 71, "name": "Shared Inventory"})

        result = DirectHTTPClient.lookup_resource_id(client, "inventories", "name", "Default++Shared Inventory", service="controller")

        self.assertEqual(result, 71)
        client._make_request.assert_called_once_with(
            "GET", "https://gateway.example.com/api/controller/v2/inventories/Default++Shared%20Inventory/", operation="lookup", resource="inventories"
        )

    def test_direct_client_applies_scope_to_named_url_lookup(self):
        client = _direct_client()
        client._make_request.return_value = _response(body={"count": 1, "results": [{"id": 72, "name": "Shared Inventory"}]})

        result = DirectHTTPClient.lookup_resource_id(
            client,
            "inventories",
            "name",
            "Default++Shared Inventory",
            service="controller",
            extra_query_params={"organization": 9},
        )

        self.assertEqual(result, 72)
        client._make_request.assert_called_once()
        request_url = urlparse(client._make_request.call_args.args[1])
        self.assertEqual(request_url.path, "/api/controller/v2/inventories/")
        self.assertEqual(parse_qs(request_url.query), {"name": ["Default++Shared Inventory"], "organization": ["9"]})

    def test_direct_client_falls_back_to_name_search_when_named_url_is_missing(self):
        client = _direct_client()
        client._make_request.side_effect = [
            APIError("Not found", status_code=404),
            _response(body={"count": 1, "results": [{"id": 71, "name": "Default++Shared Inventory"}]}),
        ]

        result = DirectHTTPClient.lookup_resource_id(client, "inventories", "name", "Default++Shared Inventory", service="controller")

        self.assertEqual(result, 71)
        self.assertEqual(client._make_request.call_count, 2)


if __name__ == "__main__":
    unittest.main()
