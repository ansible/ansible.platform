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
    """Verify transformed SDK operations recover from 401 without replaying other failures."""

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
        failure.raise_for_status.side_effect = requests.HTTPError("service unavailable")
        self.service.session.post.return_value = failure
        operations = {
            "create": EndpointOperation(path="config/", method="POST", fields=["manifest"], required_for="create", order=1),
        }

        with self.assertRaises(requests.HTTPError):
            self.service._execute_operations(operations, _FakeLicense(manifest="encoded"), self.context, required_for="create")

        self.service.session.post.assert_called_once()
