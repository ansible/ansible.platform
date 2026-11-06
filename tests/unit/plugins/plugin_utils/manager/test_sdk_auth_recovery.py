# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for authentication recovery on SDK endpoint operations."""

from __future__ import absolute_import, division, print_function

from dataclasses import dataclass
from unittest import TestCase
from unittest.mock import MagicMock, patch

import requests
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.retry import RetryConfig
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import EndpointOperation, TransformContext


@dataclass
class _FakeLicense:
    manifest: str = None
    license_info: dict = None


class _SingletonLicenseMixin:
    is_singleton = True

    @classmethod
    def get_endpoint_operations(cls):
        return {"get": EndpointOperation(path="config/", method="GET", fields=[], required_for="find", order=1)}

    @classmethod
    def from_api(cls, api_data, context):
        return _FakeLicense(license_info=api_data.get("license_info", {}))


@dataclass
class _FakeResource:
    id: int = 42


class _FakeDeleteMixin:
    @classmethod
    def get_endpoint_operations(cls):
        return {"delete": EndpointOperation(path="/api/controller/v2/resources/{id}/", method="DELETE", fields=[], required_for="delete", order=1)}


def _make_platform_service():
    """Create a PlatformService with its network and credentials mocked."""
    session = MagicMock()
    requests_module = MagicMock()
    requests_module.Session.return_value = session
    credential_store = MagicMock()
    credential_store.get_auth_credentials.return_value = ("user", "password", None)

    with patch("ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager.get_credential_manager") as get_credential_manager:
        get_credential_manager.return_value.get_or_create_store.return_value = credential_store
        with patch("ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager._get_requests", return_value=requests_module):
            config = GatewayConfig(base_url="https://controller.example", username="user", password="password")
            return PlatformService(config)


def _response(status_code, body=None):
    response = MagicMock()
    response.status_code = status_code
    response.text = "Unauthorized" if status_code == 401 else ""
    response.content = b"{}" if body is not None else b""
    response.json.return_value = body or {}
    response.raise_for_status.return_value = None
    return response


class TestSDKAuthRecovery(TestCase):
    """Verify transformed SDK operations recover auth and retry safe transient failures."""

    def setUp(self):
        self.service = _make_platform_service()
        self.context = TransformContext(
            manager=self.service,
            session=self.service.session,
            cache={},
            api_version="2",
            service="controller",
            operation="find",
        )

    def test_singleton_find_recovers_from_401(self):
        unauthorized = _response(401)
        success = _response(200, {"license_info": {"license_type": "enterprise"}})
        self.service.session.get.reset_mock()
        self.service.session.get.side_effect = [unauthorized, success]

        with patch.object(self.service, "_handle_auth_error", return_value=True) as recover_auth:
            result = self.service._find_resource(_FakeLicense(), _SingletonLicenseMixin, self.context)

        self.assertEqual(result["license_info"], {"license_type": "enterprise"})
        self.assertEqual(self.service.session.get.call_count, 2)
        recover_auth.assert_called_once_with(unauthorized)

    def test_singleton_find_retries_transient_server_error(self):
        failure = _response(503)
        failure.raise_for_status.side_effect = requests.HTTPError("service unavailable", response=failure)
        success = _response(200, {"license_info": {"license_type": "enterprise"}})
        self.service.retry_config = RetryConfig(max_attempts=2, initial_delay=0, jitter=False)
        self.service.session.get.reset_mock()
        self.service.session.get.side_effect = [failure, success]

        result = self.service._find_resource(_FakeLicense(), _SingletonLicenseMixin, self.context)

        self.assertEqual(result["license_info"], {"license_type": "enterprise"})
        self.assertEqual(self.service.session.get.call_count, 2)

    def test_delete_retries_transient_server_error(self):
        failure = _response(503)
        failure.raise_for_status.side_effect = requests.HTTPError("service unavailable", response=failure)
        success = _response(204)
        self.service.retry_config = RetryConfig(max_attempts=2, initial_delay=0, jitter=False)
        self.service.session.delete.side_effect = [failure, success]
        context = TransformContext(manager=self.service, session=self.service.session, cache={}, api_version="2", service="controller", operation="delete")

        result = self.service._delete_resource(_FakeResource(), _FakeDeleteMixin, context)

        self.assertEqual(result, {"changed": True, "id": 42})
        self.assertEqual(self.service.session.delete.call_count, 2)

    def test_delete_404_remains_idempotent(self):
        not_found = _response(404)
        not_found.raise_for_status.side_effect = requests.HTTPError("not found", response=not_found)
        self.service.session.delete.return_value = not_found
        context = TransformContext(manager=self.service, session=self.service.session, cache={}, api_version="2", service="controller", operation="delete")

        result = self.service._delete_resource(_FakeResource(), _FakeDeleteMixin, context)

        self.assertEqual(result, {"changed": False, "id": 42})
        self.service.session.delete.assert_called_once()

    def test_create_recovers_from_401_without_transient_retry(self):
        unauthorized = _response(401)
        success = _response(200, {"license_info": {"license_type": "enterprise"}})
        self.service.session.post.side_effect = [unauthorized, success]
        operations = {
            "create": EndpointOperation(path="config/", method="POST", fields=["manifest"], required_for="create", order=1),
        }

        with patch.object(self.service, "_handle_auth_error", return_value=True) as recover_auth:
            result = self.service._execute_operations(operations, _FakeLicense(manifest="encoded"), self.context, required_for="create")

        self.assertEqual(result, {"license_info": {"license_type": "enterprise"}})
        self.assertEqual(self.service.session.post.call_count, 2)
        recover_auth.assert_called_once_with(unauthorized)

    def test_create_does_not_retry_transient_server_error(self):
        failure = _response(503)
        failure.raise_for_status.side_effect = requests.HTTPError("service unavailable", response=failure)
        self.service.session.post.return_value = failure
        operations = {
            "create": EndpointOperation(path="config/", method="POST", fields=["manifest"], required_for="create", order=1),
        }

        with self.assertRaises(APIError):
            self.service._execute_operations(operations, _FakeLicense(manifest="encoded"), self.context, required_for="create")

        self.service.session.post.assert_called_once()

    def test_execute_operations_preserves_api_error_when_adding_response_body(self):
        original_error = APIError(
            "API request failed",
            operation="create",
            resource="license",
            details={"status_code": 503, "response_body": '{"detail": "service unavailable"}'},
            status_code=503,
        )
        original_error.retryable = True
        operations = {
            "create": EndpointOperation(path="config/", method="POST", fields=["manifest"], required_for="create", order=1),
        }

        with patch.object(self.service, "_make_request", side_effect=original_error):
            with self.assertRaises(APIError) as raised:
                self.service._execute_operations(operations, _FakeLicense(manifest="encoded"), self.context, required_for="create")

        self.assertEqual(raised.exception.status_code, 503)
        self.assertTrue(raised.exception.retryable)
        self.assertEqual(raised.exception.operation, "create")
        self.assertEqual(raised.exception.resource, "license")
        self.assertEqual(raised.exception.details["status_code"], 503)
        self.assertIn("service unavailable", str(raised.exception))
        self.assertIs(raised.exception.__cause__, original_error)

    def test_execute_operations_keeps_non_api_exception_handling(self):
        original_error = RuntimeError("request failed")
        original_error.response = MagicMock(text='{"detail": "service unavailable"}')
        operations = {
            "create": EndpointOperation(path="config/", method="POST", fields=["manifest"], required_for="create", order=1),
        }

        with patch.object(self.service, "_make_request", side_effect=original_error):
            with self.assertRaises(ValueError) as raised:
                self.service._execute_operations(operations, _FakeLicense(manifest="encoded"), self.context, required_for="create")

        self.assertIn("service unavailable", str(raised.exception))
        self.assertIs(raised.exception.__cause__, original_error)
