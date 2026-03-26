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
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import shutil
import tempfile

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
        the PlatformService gracefully defaults to version '1'.
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
        # Explicitly default to '1' when an unsupported/future version is returned
        self.assertEqual(service.api_version, '1')

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


def _make_fake_api_root():
    """Create a temporary api/ directory with v1 and v2 module stubs."""
    root = Path(tempfile.mkdtemp())
    (root / "v1").mkdir()
    (root / "v2").mkdir()
    (root / "v1" / "user.py").write_text("# stub\n")
    (root / "v2" / "user.py").write_text("# stub\n")
    (root / "v2" / "org.py").write_text("# stub\n")
    # Dirs/files that should be ignored by discovery
    (root / "v2" / "__init__.py").write_text("# init\n")
    (root / "v2" / "generated").write_text("# not a .py, ignored by glob anyway\n")
    return root


def test_discover_versions_populates_versions_and_module_versions():
    """Discovery (run in __init__) populates versions and module_versions from filesystem."""
    api_root = _make_fake_api_root()
    try:
        registry = APIVersionRegistry(api_base_path=str(api_root))

        assert "1" in registry.versions
        assert "2" in registry.versions
        assert registry.versions["1"] == ["user"]
        assert sorted(registry.versions["2"]) == ["org", "user"]

        assert "user" in registry.module_versions
        assert "org" in registry.module_versions
        assert sorted(registry.module_versions["user"]) == ["1", "2"]
        assert registry.module_versions["org"] == ["2"]
    finally:
        shutil.rmtree(api_root, ignore_errors=True)


def test_find_best_version_exact_match():
    """find_best_version returns requested version when it exists for the module."""
    api_root = _make_fake_api_root()
    try:
        registry = APIVersionRegistry(api_base_path=str(api_root))

        assert registry.find_best_version("1", "user") == "1"
        assert registry.find_best_version("2", "user") == "2"
        assert registry.find_best_version("2", "org") == "2"
    finally:
        shutil.rmtree(api_root, ignore_errors=True)


def test_find_best_version_unknown_module_returns_none():
    """find_best_version returns None for a module not in any discovered version."""
    api_root = _make_fake_api_root()
    try:
        registry = APIVersionRegistry(api_base_path=str(api_root))

        assert registry.find_best_version("1", "nonexistent_module") is None
        assert registry.find_best_version("2", "nonexistent_module") is None
    finally:
        shutil.rmtree(api_root, ignore_errors=True)


def test_find_best_version_closest_lower():
    """find_best_version returns closest lower version when exact match missing."""
    api_root = _make_fake_api_root()
    try:
        registry = APIVersionRegistry(api_base_path=str(api_root))
        # user has versions 1 and 2; request 2.1 -> no exact, so closest lower is 2
        assert registry.find_best_version("2.1", "user") == "2"
    finally:
        shutil.rmtree(api_root, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
