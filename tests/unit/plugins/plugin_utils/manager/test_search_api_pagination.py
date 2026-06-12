# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for PlatformService.search_api pagination handling."""

from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig


def _make_platform_service(base_url="https://gw.example.com"):
    """PlatformService with network and credentials mocked."""
    mock_session = MagicMock()
    mock_requests = MagicMock()
    mock_requests.Session.return_value = mock_session
    mock_store = MagicMock()
    mock_store.get_auth_credentials.return_value = ("admin", "admin", None)
    with patch("ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager.get_credential_manager") as mock_cred:
        mock_cred.return_value.get_or_create_store.return_value = mock_store
        with patch("ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager._get_requests") as mock_get_requests:
            mock_get_requests.return_value = mock_requests
            config = GatewayConfig(base_url=base_url, username="admin", password="admin", idle_timeout=30.0)
            return PlatformService(config)


def _resp(payload):
    r = MagicMock()
    r.json.return_value = payload
    return r


class TestSearchApiPagination(unittest.TestCase):
    def setUp(self):
        self.svc = _make_platform_service(base_url="https://gw.example.com")

    def test_relative_next_url_is_resolved_to_absolute(self):
        """AAP returns 'next' as a relative path; it must be made absolute before GET."""
        page1 = {"count": 2, "results": [{"id": 1}], "next": "/api/controller/v2/job_templates/?page=2", "previous": None}
        page2 = {"count": 2, "results": [{"id": 2}], "next": None, "previous": None}

        with patch.object(self.svc, "_make_request", side_effect=[_resp(page1), _resp(page2)]) as mock_req:
            result = self.svc.search_api("job_templates", return_all=True, max_objects=100)

        # Second request (the pagination follow-up) must receive an absolute URL.
        paginate_call = mock_req.call_args_list[1]
        paginated_url = paginate_call.args[1]
        self.assertEqual(paginated_url, "https://gw.example.com/api/controller/v2/job_templates/?page=2")

        # All pages collected; trailing 'next' cleared.
        self.assertEqual(result["results"], [{"id": 1}, {"id": 2}])
        self.assertIsNone(result["next"])

    def test_absolute_next_url_passed_through_unchanged(self):
        """If 'next' is already absolute it must be used as-is."""
        page1 = {"count": 2, "results": [{"id": 1}], "next": "https://gw.example.com/api/controller/v2/job_templates/?page=2", "previous": None}
        page2 = {"count": 2, "results": [{"id": 2}], "next": None, "previous": None}

        with patch.object(self.svc, "_make_request", side_effect=[_resp(page1), _resp(page2)]) as mock_req:
            self.svc.search_api("job_templates", return_all=True, max_objects=100)

        paginated_url = mock_req.call_args_list[1].args[1]
        self.assertEqual(paginated_url, "https://gw.example.com/api/controller/v2/job_templates/?page=2")

    def test_max_objects_exceeded_raises(self):
        page1 = {"count": 5, "results": [{"id": 1}], "next": "/api/controller/v2/job_templates/?page=2"}
        with patch.object(self.svc, "_make_request", side_effect=[_resp(page1)]):
            with self.assertRaises(ValueError):
                self.svc.search_api("job_templates", return_all=True, max_objects=2)


if __name__ == "__main__":
    unittest.main()
