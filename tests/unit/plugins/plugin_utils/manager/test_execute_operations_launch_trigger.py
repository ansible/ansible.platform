# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Regression tests for PlatformService._execute_operations (AAP-91390).

Covers two bugs found migrating inventory_source_update and job_launch, both
launch-trigger sub-actions:
  1. A *primary* operation (no depends_on) must always fire, even when its
     computed request body is empty — either because it's deliberately
     declared with fields=[] (a no-body trigger, e.g. inventory_source_update's
     POST .../update/), or because it has optional fields that all happen to
     be unset on this call (e.g. job_launch with no prompt overrides — the
     launch must still happen). Only a *secondary* operation (depends_on set,
     e.g. an optional survey_spec sub-endpoint) is skipped when it has nothing
     to send — matching DirectHTTPClient's already-correct behavior.
  2. path_params entries other than the literal name "id" must be resolved
     from the matching attribute on api_data, not silently left unsubstituted.
"""

from __future__ import absolute_import, division, print_function

import unittest
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import EndpointOperation


@dataclass
class _FakeLaunchAPIData:
    resource_id: Optional[int] = None
    id: Optional[int] = None


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


def _resp(payload, status_code=202):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


class TestNoBodyLaunchTrigger(unittest.TestCase):
    def setUp(self):
        self.svc = _make_platform_service()

    def test_fields_empty_operation_still_calls_the_api(self):
        """A launch trigger with fields=[] must not be skipped for "having no data"."""
        operations = {
            "create": EndpointOperation(
                path="/api/controller/v2/inventory_sources/{resource_id}/update/",
                method="POST",
                fields=[],
                path_params=["resource_id"],
                required_for="create",
                order=1,
            ),
        }
        api_data = _FakeLaunchAPIData(resource_id=42)
        launched = {"id": 100, "status": "pending"}

        with patch.object(self.svc.session, "request", return_value=_resp(launched)) as mock_request:
            result = self.svc._execute_operations(operations, api_data, context={}, required_for="create")

        mock_request.assert_called_once()
        called_url = mock_request.call_args[0][1]
        self.assertIn("/api/controller/v2/inventory_sources/42/update/", called_url)
        self.assertEqual(result, launched)

    def test_custom_path_param_name_is_substituted(self):
        """path_params entries other than "id" must resolve from the matching api_data attribute."""
        operations = {
            "create": EndpointOperation(
                path="/api/controller/v2/inventory_sources/{resource_id}/update/",
                method="POST",
                fields=[],
                path_params=["resource_id"],
                required_for="create",
                order=1,
            ),
        }
        api_data = _FakeLaunchAPIData(resource_id=7)

        with patch.object(self.svc.session, "request", return_value=_resp({"id": 1})) as mock_request:
            self.svc._execute_operations(operations, api_data, context={}, required_for="create")

        called_url = mock_request.call_args[0][1]
        self.assertNotIn("{resource_id}", called_url)
        self.assertIn("/7/update/", called_url)

    def test_dependent_secondary_endpoint_with_no_data_is_still_skipped(self):
        """A secondary op (depends_on set) with nothing populated is skipped — e.g. an unused optional survey_spec sub-endpoint."""
        operations = {
            "create": EndpointOperation(
                path="/api/controller/v2/widgets/",
                method="POST",
                fields=["name"],
                required_for="create",
                order=1,
            ),
            "survey_spec": EndpointOperation(
                path="/api/controller/v2/widgets/{id}/survey_spec/",
                method="POST",
                fields=["survey_spec"],
                path_params=["id"],
                required_for="create",
                depends_on="create",
                order=2,
            ),
        }

        @dataclass
        class _WidgetData:
            name: Optional[str] = "demo"
            survey_spec: Optional[dict] = None
            id: Optional[int] = None

        with patch.object(self.svc.session, "request", return_value=_resp({"id": 1, "name": "demo"})) as mock_request:
            result = self.svc._execute_operations(operations, _WidgetData(), context={}, required_for="create")

        # Only the primary "create" call fires; the dependent "survey_spec" op is
        # skipped because it has no data and depends_on a prior op.
        mock_request.assert_called_once()
        self.assertEqual(result, {"id": 1, "name": "demo"})

    def test_primary_operation_with_no_optional_fields_set_still_fires(self):
        """job_launch with no prompt overrides: fields is non-empty but all unset — the launch must still happen."""
        operations = {
            "create": EndpointOperation(
                path="/api/controller/v2/job_templates/{job_template_id}/launch/",
                method="POST",
                fields=["extra_vars", "limit"],
                path_params=["job_template_id"],
                required_for="create",
                order=1,
            ),
        }

        @dataclass
        class _LaunchData:
            job_template_id: Optional[int] = None
            extra_vars: Optional[dict] = None
            limit: Optional[str] = None

        api_data = _LaunchData(job_template_id=9)

        with patch.object(self.svc.session, "request", return_value=_resp({"id": 100, "status": "pending"})) as mock_request:
            result = self.svc._execute_operations(operations, api_data, context={}, required_for="create")

        mock_request.assert_called_once()
        self.assertEqual(result, {"id": 100, "status": "pending"})


if __name__ == "__main__":
    unittest.main()
