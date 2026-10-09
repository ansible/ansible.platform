# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for DirectHTTPClient.manage_associations/manage_sub_resource/copy_resource."""

from __future__ import absolute_import, division, print_function

import json
import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError

__metaclass__ = type


def _client(base_url="https://gw.example.com"):
    client = DirectHTTPClient.__new__(DirectHTTPClient)
    client._authenticated = True
    client.base_url = base_url
    client.cache = {}
    client.lookup_resource_id = MagicMock()
    client.search_api = MagicMock()
    return client


def _http_resp(status=200, body=None):
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = json.dumps(body or {}).encode("utf-8")
    return resp


class TestManageAssociations(unittest.TestCase):
    def setUp(self):
        self.client = _client()

    def test_associates_and_disassociates_to_reconcile(self):
        self.client.lookup_resource_id.side_effect = lambda endpoint, field, value, service: {"cred-a": 3}[value]
        self.client.search_api.return_value = {"results": [{"id": 1}, {"id": 2}]}

        with unittest.mock.patch.object(self.client, "_make_request") as mock_request:
            changed = self.client.manage_associations(
                "/api/controller/v2/job_templates",
                42,
                "credentials",
                ["cred-a", 1],
                "credentials",
                "name",
                service="controller",
            )

        self.assertTrue(changed)
        post_calls = [c for c in mock_request.call_args_list if c.args[0] == "POST"]
        payloads = [c.kwargs["json"] for c in post_calls]
        self.assertIn({"id": 3, "associate": True}, payloads)
        self.assertIn({"id": 2, "disassociate": True}, payloads)

    def test_no_change_when_already_in_sync(self):
        self.client.search_api.return_value = {"results": [{"id": 1}]}

        with unittest.mock.patch.object(self.client, "_make_request") as mock_request:
            changed = self.client.manage_associations("/api/controller/v2/job_templates", 42, "credentials", [1], "credentials", "name")

        self.assertFalse(changed)
        mock_request.assert_not_called()

    def test_current_associations_are_paginated(self):
        """Regression test: associations beyond page 1 must not be treated as absent."""
        self.client.search_api.return_value = {"results": [{"id": i} for i in range(1, 31)]}

        with unittest.mock.patch.object(self.client, "_make_request") as mock_request:
            changed = self.client.manage_associations("/api/controller/v2/job_templates", 42, "credentials", list(range(1, 31)), "credentials", "name")

        self.assertFalse(changed)
        mock_request.assert_not_called()
        self.client.search_api.assert_called_once_with("/api/controller/v2/job_templates/42/credentials/", return_all=True, max_objects=100000)

    def test_relative_association_path_uses_requested_service(self):
        self.client.get_api_version = MagicMock(return_value="2")
        self.client.search_api.return_value = {"results": []}

        with unittest.mock.patch.object(self.client, "_make_request") as mock_request:
            self.client.manage_associations("job_templates", 42, "credentials", [5], "credentials", "name", service="controller")

        self.client.search_api.assert_called_once_with("/api/controller/v2/job_templates/42/credentials/", return_all=True, max_objects=100000)
        mock_request.assert_called_once_with(
            "POST",
            "https://gw.example.com/api/controller/v2/job_templates/42/credentials/",
            operation="associate",
            resource="credentials",
            json={"id": 5, "associate": True},
        )


class TestManageSubResource(unittest.TestCase):
    def setUp(self):
        self.client = _client()

    def test_none_data_is_noop(self):
        with unittest.mock.patch.object(self.client, "_make_request") as mock_request:
            changed = self.client.manage_sub_resource("/api/controller/v2/job_templates", 42, "survey_spec", None)
        self.assertFalse(changed)
        mock_request.assert_not_called()

    def test_empty_dict_deletes(self):
        with unittest.mock.patch.object(self.client, "_make_request", return_value=_http_resp(status=200)) as mock_request:
            changed = self.client.manage_sub_resource("/api/controller/v2/job_templates", 42, "survey_spec", {})
        self.assertTrue(changed)
        mock_request.assert_called_once_with(
            "DELETE", "https://gw.example.com/api/controller/v2/job_templates/42/survey_spec/", operation="delete_sub_resource", resource="survey_spec"
        )

    def test_empty_dict_delete_404_is_not_changed(self):
        not_found = APIError("API request failed: HTTP 404", operation="delete_sub_resource", resource="survey_spec", status_code=404)
        with unittest.mock.patch.object(self.client, "_make_request", side_effect=not_found):
            changed = self.client.manage_sub_resource("/api/controller/v2/job_templates", 42, "survey_spec", {})
        self.assertFalse(changed)

    def test_empty_dict_delete_non_404_error_propagates(self):
        server_error = APIError("API request failed: HTTP 500", operation="delete_sub_resource", resource="survey_spec", status_code=500)
        with unittest.mock.patch.object(self.client, "_make_request", side_effect=server_error):
            with self.assertRaises(APIError):
                self.client.manage_sub_resource("/api/controller/v2/job_templates", 42, "survey_spec", {})

    def test_same_data_is_noop(self):
        spec = {"name": "survey"}
        with unittest.mock.patch.object(self.client, "_make_request", return_value=_http_resp(body=spec)) as mock_request:
            changed = self.client.manage_sub_resource("/api/controller/v2/job_templates", 42, "survey_spec", spec)
        self.assertFalse(changed)
        self.assertEqual(mock_request.call_count, 1)

    def test_different_data_posts_update(self):
        with unittest.mock.patch.object(self.client, "_make_request", return_value=_http_resp(body={"name": "old"})) as mock_request:
            changed = self.client.manage_sub_resource("/api/controller/v2/job_templates", 42, "survey_spec", {"name": "new"})
        self.assertTrue(changed)
        self.assertEqual(mock_request.call_count, 2)
        self.assertEqual(mock_request.call_args_list[1].args[0], "POST")


class TestCopyResource(unittest.TestCase):
    def setUp(self):
        self.client = _client()

    def test_numeric_source_skips_lookup(self):
        with unittest.mock.patch.object(self.client, "_make_request", return_value=_http_resp(body={"id": 99})) as mock_request:
            result = self.client.copy_resource("job_template", "7", "copied", "/api/controller/v2/job_templates")

        self.assertEqual(mock_request.call_count, 1)
        mock_request.assert_called_once_with(
            "POST",
            "https://gw.example.com/api/controller/v2/job_templates/7/copy/",
            operation="copy_resource",
            resource="job_template",
            json={"name": "copied"},
        )
        self.assertEqual(result, {"id": 99})

    def test_name_source_resolves_then_copies(self):
        with unittest.mock.patch.object(
            self.client, "_make_request", side_effect=[_http_resp(body={"results": [{"id": 12}]}), _http_resp(body={"id": 99})]
        ) as mock_request:
            self.client.copy_resource("job_template", "source jt", "copied", "/api/controller/v2/job_templates")

        self.assertEqual(mock_request.call_count, 2)
        self.assertEqual(mock_request.call_args_list[1].args[0], "POST")
        self.assertEqual(
            mock_request.call_args_list[1].args[1],
            "https://gw.example.com/api/controller/v2/job_templates/12/copy/",
        )

    def test_source_not_found_raises(self):
        with unittest.mock.patch.object(self.client, "_make_request", return_value=_http_resp(body={"results": []})):
            with self.assertRaises(ValueError):
                self.client.copy_resource("job_template", "missing", "copied", "/api/controller/v2/job_templates")


class TestSearchApi(unittest.TestCase):
    def setUp(self):
        self.client = DirectHTTPClient.__new__(DirectHTTPClient)
        self.client._authenticated = True
        self.client.base_url = "https://gw.example.com"
        self.client.api_versions = {"gateway": "2"}
        self.client.cache = {}

    def _bad_json_response(self):
        resp = MagicMock()
        resp.read.return_value = b"not json"
        return resp

    def test_return_all_propagates_json_parse_failure(self):
        """manage_associations diffs this result against desired state, so a parse
        failure must fail the operation rather than be mistaken for an empty page."""
        with unittest.mock.patch.object(self.client, "_make_request", return_value=self._bad_json_response()):
            with self.assertRaises(json.JSONDecodeError):
                self.client.search_api("/api/controller/v2/job_templates/42/credentials/", return_all=True)

    def test_non_return_all_still_swallows_json_parse_failure(self):
        with unittest.mock.patch.object(self.client, "_make_request", return_value=self._bad_json_response()):
            result = self.client.search_api("/api/controller/v2/job_templates/42/credentials/")
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
