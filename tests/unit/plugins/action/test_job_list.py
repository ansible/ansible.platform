"""Unit tests for the job_list action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
from unittest.mock import MagicMock, patch

import pytest
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.job_list import (
    CONTROLLER_JOBS_ENDPOINT,
    build_query_params,
)

# ---------------------------------------------------------------------------
# Tests for build_query_params helper
# ---------------------------------------------------------------------------


class TestBuildQueryParams:
    """Tests for the build_query_params utility function."""

    def test_empty_params(self):
        result = build_query_params({})
        assert result == {}

    def test_status_only(self):
        result = build_query_params({"status": "running"})
        assert result == {"status": "running"}

    def test_page_only(self):
        result = build_query_params({"page": 3})
        assert result == {"page": 3}

    def test_query_dict(self):
        result = build_query_params({"query": {"playbook": "test.yml"}})
        assert result == {"playbook": "test.yml"}

    def test_status_and_page(self):
        result = build_query_params({"status": "failed", "page": 2})
        assert result == {"status": "failed", "page": 2}

    def test_status_and_query(self):
        result = build_query_params({"status": "successful", "query": {"playbook": "deploy.yml"}})
        assert result == {"status": "successful", "playbook": "deploy.yml"}

    def test_all_params(self):
        result = build_query_params(
            {
                "status": "running",
                "page": 1,
                "query": {"playbook": "site.yml"},
            }
        )
        assert result == {"status": "running", "page": 1, "playbook": "site.yml"}

    def test_none_status_excluded(self):
        result = build_query_params({"status": None, "page": 2})
        assert result == {"page": 2}

    def test_none_page_excluded(self):
        result = build_query_params({"status": "running", "page": None})
        assert result == {"status": "running"}

    def test_none_query_excluded(self):
        result = build_query_params({"query": None})
        assert result == {}

    def test_page_and_all_pages_are_mutually_exclusive(self):
        with pytest.raises(ValueError, match="page and all_pages are mutually exclusive"):
            build_query_params({"page": 2, "all_pages": True})

    def test_all_pages_with_page_in_query_are_mutually_exclusive(self):
        with pytest.raises(ValueError, match="page and all_pages are mutually exclusive"):
            build_query_params({"all_pages": True, "query": {"page": 5}})

    def test_endpoint_constant(self):
        assert CONTROLLER_JOBS_ENDPOINT == "/api/controller/v2/jobs/"


# ---------------------------------------------------------------------------
# Tests for the ActionModule
# ---------------------------------------------------------------------------


class TestJobListAction:
    """Tests for the job_list action plugin."""

    def _make_action_module(self, task_args):
        """Create a mock ActionModule instance for testing."""
        # Lazy import to avoid import-time failures in CI
        from ansible_collections.ansible.platform.plugins.action.job_list import ActionModule

        action = ActionModule.__new__(ActionModule)
        action._display = MagicMock()
        action._display.verbosity = 0
        action._task = MagicMock()
        action._task.args = task_args
        action._task.check_mode = False
        action._task.environment = []
        action._connection = MagicMock()
        action._templar = MagicMock()
        return action

    @patch.object(
        __import__("ansible_collections.ansible.platform.plugins.action.job_list", fromlist=["ActionModule"]).ActionModule,
        "_prepare_action",
    )
    def test_successful_query(self, mock_prepare):
        """Test that a successful query returns results with changed=False."""
        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {"id": 1, "status": "successful"},
                {"id": 2, "status": "successful"},
            ],
        }

        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"status": "successful", "page": None, "all_pages": False, "query": None},
            "resource_data": {"status": "successful"},
            "write_only_data": {},
            "manager": mock_manager,
            "argspec": {},
        }

        action = self._make_action_module({"status": "successful"})
        result = action.run(task_vars={})

        assert result == {"changed": False, "failed": False, **mock_manager.search_api.return_value}
        mock_manager.search_api.assert_called_once_with(
            endpoint=CONTROLLER_JOBS_ENDPOINT,
            query_params={"status": "successful"},
            return_all=False,
            max_objects=10000,
        )

    @patch.object(
        __import__("ansible_collections.ansible.platform.plugins.action.job_list", fromlist=["ActionModule"]).ActionModule,
        "_prepare_action",
    )
    def test_all_pages(self, mock_prepare):
        """Test that all_pages=True passes return_all=True to search_api."""
        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "count": 100,
            "next": None,
            "previous": None,
            "results": [{"id": i} for i in range(100)],
        }

        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"status": None, "page": None, "all_pages": True, "query": None},
            "resource_data": {},
            "write_only_data": {},
            "manager": mock_manager,
            "argspec": {},
        }

        action = self._make_action_module({"all_pages": True})
        result = action.run(task_vars={})

        assert result == {"changed": False, "failed": False, **mock_manager.search_api.return_value}
        mock_manager.search_api.assert_called_once_with(
            endpoint=CONTROLLER_JOBS_ENDPOINT,
            query_params=None,
            return_all=True,
            max_objects=10000,
        )

    @patch.object(
        __import__("ansible_collections.ansible.platform.plugins.action.job_list", fromlist=["ActionModule"]).ActionModule,
        "_prepare_action",
    )
    def test_with_query_dict(self, mock_prepare):
        """Test that the query dict merges into query_params."""
        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [{"id": 5, "status": "running"}],
        }

        mock_prepare.return_value = {
            "result": {},
            "validated_params": {
                "status": "running",
                "page": None,
                "all_pages": False,
                "query": {"playbook": "testing.yml"},
            },
            "resource_data": {"status": "running", "query": {"playbook": "testing.yml"}},
            "write_only_data": {},
            "manager": mock_manager,
            "argspec": {},
        }

        action = self._make_action_module({"status": "running", "query": {"playbook": "testing.yml"}})
        result = action.run(task_vars={})

        assert result == {"changed": False, "failed": False, **mock_manager.search_api.return_value}
        mock_manager.search_api.assert_called_once_with(
            endpoint=CONTROLLER_JOBS_ENDPOINT,
            query_params={"status": "running", "playbook": "testing.yml"},
            return_all=False,
            max_objects=10000,
        )

    @patch.object(
        __import__("ansible_collections.ansible.platform.plugins.action.job_list", fromlist=["ActionModule"]).ActionModule,
        "_prepare_action",
    )
    def test_empty_results(self, mock_prepare):
        """Test that empty results are handled correctly."""
        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "count": 0,
            "next": None,
            "previous": None,
            "results": [],
        }

        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"status": "running", "page": None, "all_pages": False, "query": None},
            "resource_data": {"status": "running"},
            "write_only_data": {},
            "manager": mock_manager,
            "argspec": {},
        }

        action = self._make_action_module({"status": "running"})
        result = action.run(task_vars={})

        assert result["changed"] is False
        assert result["count"] == 0
        assert result["results"] == []

    @patch.object(
        __import__("ansible_collections.ansible.platform.plugins.action.job_list", fromlist=["ActionModule"]).ActionModule,
        "_prepare_action",
    )
    def test_api_error_sets_failed(self, mock_prepare):
        """Test that API errors result in failed=True."""
        mock_manager = MagicMock()
        mock_manager.search_api.side_effect = Exception("Connection refused")

        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"status": None, "page": None, "all_pages": False, "query": None},
            "resource_data": {},
            "write_only_data": {},
            "manager": mock_manager,
            "argspec": {},
        }

        action = self._make_action_module({})
        result = action.run(task_vars={})

        assert result["failed"] is True
        assert "Connection refused" in result["msg"]

    @patch.object(
        __import__("ansible_collections.ansible.platform.plugins.action.job_list", fromlist=["ActionModule"]).ActionModule,
        "_prepare_action",
    )
    def test_page_param(self, mock_prepare):
        """Test that page parameter is passed to search_api."""
        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "count": 50,
            "next": 4,
            "previous": 2,
            "results": [{"id": i} for i in range(10)],
        }

        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"status": None, "page": 3, "all_pages": False, "query": None},
            "resource_data": {"page": 3},
            "write_only_data": {},
            "manager": mock_manager,
            "argspec": {},
        }

        action = self._make_action_module({"page": 3})
        result = action.run(task_vars={})

        assert result == {"changed": False, "failed": False, **mock_manager.search_api.return_value}
        mock_manager.search_api.assert_called_once_with(
            endpoint=CONTROLLER_JOBS_ENDPOINT,
            query_params={"page": 3},
            return_all=False,
            max_objects=10000,
        )


@pytest.mark.parametrize("persistent", [False, True])
def test_job_list_returns_more_than_one_thousand_jobs(persistent):
    """Retrieve multiple pages beyond the SDK's default safety cap."""
    from ansible_collections.ansible.platform.plugins.action.job_list import ActionModule
    from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
    from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient

    client_type = PlatformService if persistent else DirectHTTPClient
    client = client_type.__new__(client_type)
    client.base_url = "https://gateway.example"
    client.api_versions = {"gateway": "1", "controller": "2"}
    client.cache = {}
    client._authenticated = True
    client.record_activity = MagicMock()
    client.session = MagicMock()
    results = [{"id": i} for i in range(1001)]
    responses = []
    for page, next_url in [(results[:1000], "/api/controller/v2/jobs/?page=2"), (results[1000:], None)]:
        body = {"count": 1001, "results": page, "next": next_url, "previous": None}
        response = MagicMock()
        response.read.return_value = json.dumps(body).encode()
        response.json.return_value = body
        responses.append(response)
    client._make_request = MagicMock(side_effect=responses)
    action = ActionModule.__new__(ActionModule)
    action._display = MagicMock()
    action._prepare_action = MagicMock(return_value={"result": {}, "validated_params": {"all_pages": True}, "manager": client})
    result = action.run(task_vars={})
    assert result == {"changed": False, "failed": False, "count": 1001, "results": results, "next": None, "previous": None}
    assert client._make_request.call_count == 2
