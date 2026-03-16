# (c) 2026 Red Hat Inc.
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import unittest
from unittest.mock import patch, MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry import APIVersionRegistry
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.loader import DynamicClassLoader
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService


class TestAPIVersioning(unittest.TestCase):

    def test_filesystem_version_discovery_and_loading(self):
        """
        Validates APIVersionRegistry correctly scans the filesystem for versions,
        and DynamicClassLoader routes to the correct user module classes.
        """
        registry = APIVersionRegistry()
        supported = registry.get_supported_versions()
        self.assertIn('2', supported)
        self.assertTrue(len(supported) >= 1)

        latest = registry.get_latest_version()
        self.assertIsNotNone(latest)
        loader = DynamicClassLoader(registry)

        AnsibleClass, APIClass, MixinClass = loader.load_classes_for_module('user', '2')
        self.assertEqual(APIClass.__name__, 'APIUser_v2')
        self.assertEqual(AnsibleClass.__name__, 'AnsibleUser')
        self.assertTrue(hasattr(MixinClass, 'get_endpoint_operations'))

    def test_loader_unsupported_version(self):
        """
        Validates loader gracefully degrades to the closest lower supported version
        if an unknown futuristic version is explicitly requested.
        """
        registry = APIVersionRegistry()
        loader = DynamicClassLoader(registry)
        AnsibleClass, APIClass, MixinClass = loader.load_classes_for_module('user', '12')
        self.assertEqual(APIClass.__name__, 'APIUser_v2')
        self.assertEqual(AnsibleClass.__name__, 'AnsibleUser')

    @patch('ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager.get_credential_manager')
    @patch('ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager._get_requests')
    def test_platform_service_version_fallback(self, mock_get_requests, mock_cred_manager):
        """
        Validates that if the Gateway API reports an unsupported future version,
        the PlatformService gracefully falls back to the highest locally supported version.
        """
        mock_response = MagicMock()
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.json.return_value = {
            "current_version": "/api/gateway/v3/",
            "available_versions": {"v3": "/api/gateway/v3/"}
        }
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_requests = MagicMock()
        mock_requests.Session.return_value = mock_session
        mock_get_requests.return_value = mock_requests
        mock_store = MagicMock()
        mock_store.get_auth_credentials.return_value = ("admin", "admin", None)
        mock_cred_manager.return_value.get_or_create_store.return_value = mock_store
        config = GatewayConfig(base_url="https://127.0.0.1", username="admin", password="admin")
        service = PlatformService(config)
        registry = APIVersionRegistry()
        expected_fallback = registry.get_latest_version()
        self.assertEqual(service.api_version, expected_fallback)

    @patch('ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry.logger')
    def test_loader_closest_higher_with_warning(self, mock_logger):
        """
        Validates the closest higher fallback strategy and ensures a warning is logged.
        """
        registry = APIVersionRegistry()
        registry.module_versions['user'] = ['2', '3']
        best_version = registry.find_best_version('1', 'user')
        self.assertEqual(best_version, '2')
        mock_logger.warning.assert_called()
        self.assertIn("closest higher version", mock_logger.warning.call_args[0][0])

    def test_loader_fail_when_no_versions(self):
        """
        Validates that a ValueError is raised when no compatible version is found.
        """
        registry = APIVersionRegistry()
        registry.module_versions['incomplete_module'] = []
        loader = DynamicClassLoader(registry)
        with self.assertRaises(ValueError) as context:
            loader.load_classes_for_module('incomplete_module', '1')
        self.assertIn("No compatible API version found for module 'incomplete_module'", str(context.exception))


if __name__ == '__main__':
    unittest.main()
