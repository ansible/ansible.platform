# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for paginated, credential-scoped input-source lookups."""

from __future__ import absolute_import, division, print_function

import json
import unittest
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.eda_credential_input_source import (
    AnsibleEdaCredentialInputSource,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_credential_input_source import (
    EdaCredentialInputSourceTransformMixin_v1,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext


def _page_response(payload, direct=False):
    response = MagicMock()
    response.json.return_value = payload
    response.read.return_value = json.dumps(payload).encode() if direct else b""
    return response


def _context(manager):
    return TransformContext(manager=manager, session=MagicMock(), cache={}, api_version="1", service="eda", operation="find")


def _ansible_input_source():
    return AnsibleEdaCredentialInputSource(input_field_name="password", target_credential="10", source_credential="20")


def _pages():
    second_page = "/api/eda/v1/credential-input-sources/?target_credential=10&source_credential=20&page=2"
    return (
        {
            "count": 1001,
            "next": second_page,
            "results": [{"id": item_id, "input_field_name": "field-%s" % item_id} for item_id in range(1000)],
        },
        {
            "count": 1001,
            "next": None,
            "results": [{"id": 1001, "input_field_name": "password", "target_credential": 10, "source_credential": 20}],
        },
        {"id": 1001, "input_field_name": "password", "target_credential": 10, "source_credential": 20, "description": ""},
    )


class TestEdaCredentialInputSourceFind(unittest.TestCase):
    """Both client modes select matches from all credential-scoped pages."""

    def test_platform_service_finds_match_on_later_scoped_page(self):
        service = PlatformService.__new__(PlatformService)
        service.base_url = "https://gateway.example"
        service.record_activity = MagicMock()
        first_page, second_page, detail = _pages()
        service._make_request = MagicMock(side_effect=[_page_response(first_page), _page_response(second_page), _page_response(detail)])

        result = service._find_resource(_ansible_input_source(), EdaCredentialInputSourceTransformMixin_v1, _context(service))

        self.assertEqual(result["id"], 1001)
        self.assertEqual(result["description"], "")
        first_request, second_request, detail_request = service._make_request.call_args_list
        self.assertEqual(first_request.kwargs["params"]["target_credential"], 10)
        self.assertEqual(first_request.kwargs["params"]["source_credential"], 20)
        next_query = parse_qs(urlparse(second_request.args[1]).query)
        self.assertEqual(next_query["target_credential"], ["10"])
        self.assertEqual(next_query["source_credential"], ["20"])
        self.assertIn("/credential-input-sources/1001/", detail_request.args[1])

    def test_direct_client_finds_match_on_later_scoped_page(self):
        client = DirectHTTPClient.__new__(DirectHTTPClient)
        client._authenticated = True
        client.base_url = "https://gateway.example"
        client.api_versions = {"gateway": "1"}
        client.session = MagicMock()
        client.session.headers = {}
        first_page, second_page, detail = _pages()
        client._make_request = MagicMock(
            side_effect=[_page_response(first_page, direct=True), _page_response(second_page, direct=True), _page_response(detail, direct=True)]
        )

        result = client._find_resource(_ansible_input_source(), EdaCredentialInputSourceTransformMixin_v1, _context(client))

        self.assertEqual(result["id"], 1001)
        self.assertEqual(result["description"], "")
        first_request, second_request, detail_request = client._make_request.call_args_list
        first_query = parse_qs(urlparse(first_request.args[1]).query)
        self.assertEqual(first_query["target_credential"], ["10"])
        self.assertEqual(first_query["source_credential"], ["20"])
        next_query = parse_qs(urlparse(second_request.args[1]).query)
        self.assertEqual(next_query["target_credential"], ["10"])
        self.assertEqual(next_query["source_credential"], ["20"])
        self.assertIn("/credential-input-sources/1001/", detail_request.args[1])


if __name__ == "__main__":
    unittest.main()
