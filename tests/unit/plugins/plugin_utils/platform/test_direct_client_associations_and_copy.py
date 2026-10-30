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
    client.api_versions = {"gateway": "2"}
    client.api_version = "2"
    client.session = MagicMock()
    client.session.headers = {}
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
        self.client.lookup_resource_id.side_effect = lambda endpoint, field, value, service, extra_query_params=None: {"cred-a": 3}[value]
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

    def test_current_associations_over_200_follow_multiple_pages(self):
        """All association pages are considered when reconciling more than 200 items."""
        association_path = "/api/controller/v2/job_templates/42/credentials/"
        page1 = {
            "count": 250,
            "results": [{"id": i} for i in range(1, 201)],
            "next": association_path + "?page=2",
        }
        page2 = {"count": 250, "results": [{"id": i} for i in range(201, 251)], "next": None}
        self.client.api_version = "2"
        self.client.search_api = DirectHTTPClient.search_api.__get__(self.client, DirectHTTPClient)

        with unittest.mock.patch.object(self.client, "_make_request", side_effect=[_http_resp(body=page1), _http_resp(body=page2)]) as mock_request:
            changed = self.client.manage_associations(
                "/api/controller/v2/job_templates",
                42,
                "credentials",
                list(range(1, 251)),
                "credentials",
                "name",
            )

        self.assertFalse(changed)
        self.assertEqual(mock_request.call_count, 2)
        self.assertEqual(mock_request.call_args_list[1].args[1], "https://gw.example.com" + association_path + "?page=2")

    def test_multiple_names_are_resolved_in_one_query(self):
        self.client.search_api.side_effect = [
            {"results": [{"id": 3, "name": "cred-a"}, {"id": 4, "name": "cred-b"}]},
            {"results": [{"id": 3}, {"id": 4}]},
        ]

        changed = self.client.manage_associations("/api/controller/v2/job_templates", 42, "credentials", ["cred-a", "cred-b"], "credentials", "name")

        self.assertFalse(changed)
        self.assertEqual(self.client.search_api.call_args_list[0].kwargs["query_params"], {"name__in": "cred-a,cred-b"})
        self.client.lookup_resource_id.assert_not_called()

    def test_long_name_list_is_split_to_fit_url_limit(self):
        names = [f"credential-{index:02d}-" + "x" * 340 for index in range(20)]
        ids_by_name = {name: index + 1 for index, name in enumerate(names)}

        def search_api(endpoint, query_params=None, **kwargs):
            if query_params:
                return {"results": [{"id": ids_by_name[name], "name": name} for name in query_params["name__in"].split(",")]}
            return {"results": [{"id": i + 1} for i in range(len(names))]}

        self.client.search_api.side_effect = search_api

        changed = self.client.manage_associations("/api/controller/v2/job_templates", 42, "credentials", names, "credentials", "name")

        self.assertFalse(changed)
        lookup_calls = [call for call in self.client.search_api.call_args_list if call.kwargs.get("query_params")]
        self.assertGreater(len(lookup_calls), 1)
        for call in lookup_calls:
            url = self.client._build_url(call.args[0], call.kwargs["query_params"])
            self.assertLessEqual(len(url.encode("utf-8")), self.client.MAX_BATCH_LOOKUP_URL_BYTES)

    def test_association_error_identifies_resource_id(self):
        self.client.search_api.return_value = {"results": []}
        error = APIError("API request failed: HTTP 404", operation="associate", resource="credentials", status_code=404)

        with unittest.mock.patch.object(self.client, "_make_request", side_effect=error):
            with self.assertRaisesRegex(APIError, "Failed to associate credentials ID 5"):
                self.client.manage_associations("/api/controller/v2/job_templates", 42, "credentials", [5], "credentials", "name")

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

    def test_search_api_follows_relative_next_link(self):
        self.client.api_version = "2"
        pages = [
            _http_resp(body={"count": 3, "next": "/api/controller/v2/job_templates/42/labels/?page=2", "results": [{"id": 1}, {"id": 2}]}),
            _http_resp(body={"count": 3, "next": None, "results": [{"id": 3}]}),
        ]
        with unittest.mock.patch.object(self.client, "_make_request", side_effect=pages) as mock_request:
            result = DirectHTTPClient.search_api(self.client, "/api/controller/v2/job_templates/42/labels/", return_all=True)

        self.assertEqual([item["id"] for item in result["results"]], [1, 2, 3])
        self.assertEqual(mock_request.call_args_list[1].args[1], "https://gw.example.com/api/controller/v2/job_templates/42/labels/?page=2")

    def test_invalid_association_response_is_not_treated_as_empty(self):
        self.client.search_api = DirectHTTPClient.search_api.__get__(self.client)
        response = _http_resp()
        response.read.return_value = b"not json"

        with unittest.mock.patch.object(self.client, "_make_request", return_value=response):
            with self.assertRaises(json.JSONDecodeError):
                self.client.manage_associations("/api/controller/v2/job_templates", 42, "labels", [1], "labels", "name")

    def test_extra_query_params_passed_to_lookup(self):
        self.client.lookup_resource_id.side_effect = lambda endpoint, field, value, service, extra_query_params=None: {"my-label": 7}[value]
        self.client.search_api.return_value = {"results": []}

        with unittest.mock.patch.object(self.client, "_make_request"):
            self.client.manage_associations(
                "/api/controller/v2/workflow_job_templates",
                10,
                "labels",
                ["my-label"],
                "labels",
                "name",
                service="controller",
                extra_query_params={"organization": 42},
            )

        self.client.lookup_resource_id.assert_called_once_with("labels", "name", "my-label", service="controller", extra_query_params={"organization": 42})

    def test_extra_query_params_in_batch_query(self):
        self.client.api_versions["controller"] = "2"
        self.client.search_api.side_effect = [
            {"results": [{"id": 7, "name": "label-a"}, {"id": 8, "name": "label-b"}]},
            {"results": []},
        ]

        with unittest.mock.patch.object(self.client, "_make_request"):
            self.client.manage_associations(
                "/api/controller/v2/workflow_job_templates",
                10,
                "labels",
                ["label-a", "label-b"],
                "labels",
                "name",
                service="controller",
                extra_query_params={"organization": 42},
            )

        batch_call = self.client.search_api.call_args_list[0]
        self.assertEqual(batch_call.kwargs["query_params"], {"name__in": "label-a,label-b", "organization": 42})

    def test_extra_query_params_separate_cache_keys(self):
        self.client.lookup_resource_id = DirectHTTPClient.lookup_resource_id.__get__(self.client, DirectHTTPClient)
        self.client.get_api_version = MagicMock(return_value="2")
        responses = [
            _http_resp(body={"results": [{"id": 10, "name": "shared"}]}),
            _http_resp(body={"results": [{"id": 20, "name": "shared"}]}),
        ]
        with unittest.mock.patch.object(self.client, "_make_request", side_effect=responses):
            id1 = self.client.lookup_resource_id("labels", "name", "shared", service="controller", extra_query_params={"organization": 1})
            id2 = self.client.lookup_resource_id("labels", "name", "shared", service="controller", extra_query_params={"organization": 2})

        self.assertEqual(id1, 10)
        self.assertEqual(id2, 20)


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
        self.client.api_versions = {}
        self.client.api_version = "2"
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

    def test_return_all_resolves_relative_next_link(self):
        first_page = _http_resp(
            body={
                "count": 2,
                "next": "/api/controller/v2/job_templates/42/credentials/?page=2",
                "results": [{"id": 1}],
            }
        )
        second_page = _http_resp(body={"count": 2, "next": None, "results": [{"id": 2}]})

        with unittest.mock.patch.object(self.client, "_make_request", side_effect=[first_page, second_page]) as mock_request:
            result = self.client.search_api("/api/controller/v2/job_templates/42/credentials/", return_all=True)

        self.assertEqual(mock_request.call_args_list[1].args[1], "https://gw.example.com/api/controller/v2/job_templates/42/credentials/?page=2")
        self.assertEqual(result["results"], [{"id": 1}, {"id": 2}])

    def test_return_all_raises_when_max_objects_is_exceeded(self):
        page1 = {
            "count": 3,
            "results": [{"id": 1}, {"id": 2}],
            "next": "/api/controller/v2/job_templates/42/credentials/?page=2",
        }
        with unittest.mock.patch.object(self.client, "_make_request", return_value=_http_resp(body=page1)) as mock_request:
            with self.assertRaisesRegex(ValueError, "max_objects=2"):
                self.client.search_api("/api/controller/v2/job_templates/42/credentials/", return_all=True, max_objects=2)
        mock_request.assert_called_once()

    def test_return_all_raises_when_pages_exceed_max_objects_with_stale_count(self):
        page1 = {"count": 1, "results": [{"id": 1}, {"id": 2}], "next": "/api/controller/v2/job_templates/42/credentials/?page=2"}
        page2 = {"count": 1, "results": [{"id": 3}, {"id": 4}], "next": None}
        with unittest.mock.patch.object(self.client, "_make_request", side_effect=[_http_resp(body=page1), _http_resp(body=page2)]):
            with self.assertRaisesRegex(ValueError, "max_objects=3"):
                self.client.search_api("/api/controller/v2/job_templates/42/credentials/", return_all=True, max_objects=3)


if __name__ == "__main__":
    unittest.main()
