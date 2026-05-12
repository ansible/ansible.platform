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

import shutil
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Dict, Optional
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_transform import BaseTransformMixin
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.loader import DynamicClassLoader
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry import APIVersionRegistry

# ---------------------------------------------------------------------------
# Fake v2 API module — injected into sys.modules during tests that exercise
# multi-version logic.  v2 does not exist in the real collection (only v1 is
# shipped); keeping the fixture here rather than in plugins/plugin_utils/api/
# avoids shipping test-only code.
# ---------------------------------------------------------------------------

_V2_PKG = "ansible_collections.ansible.platform.plugins.plugin_utils.api.v2"
_V2_MOD = "ansible_collections.ansible.platform.plugins.plugin_utils.api.v2.user"


def _make_fake_v2_module() -> types.ModuleType:
    """Return a minimal fake api.v2.user module used only in tests."""

    @dataclass
    class APIUser_v2:  # noqa: N801 – name mirrors real collection convention
        username: str
        email: Optional[str] = None

    class UserTransformMixin_v2(BaseTransformMixin):
        _field_mapping: ClassVar[Dict] = {"username": "username"}

        @classmethod
        def get_endpoint_operations(cls) -> Dict:
            return {}

        @classmethod
        def from_ansible_data(cls, instance, context):
            return {}

        @classmethod
        def from_api(cls, data, context):
            return data

        @classmethod
        def get_lookup_field(cls) -> str:
            return "username"

    mod = types.ModuleType(_V2_MOD)
    mod.APIUser_v2 = APIUser_v2
    mod.UserTransformMixin_v2 = UserTransformMixin_v2
    return mod


class TestAPIVersioning(unittest.TestCase):
    # ------------------------------------------------------------------
    # setUp / tearDown — create a temporary api dir containing a stub
    # v2/user.py so APIVersionRegistry can discover "2" via filesystem
    # scan, and inject the matching fake module into sys.modules so that
    # DynamicClassLoader's importlib.import_module call resolves it.
    # ------------------------------------------------------------------

    def setUp(self):
        # Temp dir: api/v2/user.py  (stub — registry only checks file existence)
        self._tmpdir = tempfile.mkdtemp()
        v2_dir = Path(self._tmpdir) / "v2"
        v2_dir.mkdir()
        (v2_dir / "__init__.py").write_text("")
        (v2_dir / "user.py").write_text("# v2 stub for unit tests")

        # Inject fake v2 into sys.modules before every test so importlib
        # finds it without touching the filesystem.
        self._fake_pkg = types.ModuleType(_V2_PKG)
        self._fake_mod = _make_fake_v2_module()
        sys.modules[_V2_PKG] = self._fake_pkg
        sys.modules[_V2_MOD] = self._fake_mod

    def tearDown(self):
        sys.modules.pop(_V2_MOD, None)
        sys.modules.pop(_V2_PKG, None)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _registry_with_v2(self) -> APIVersionRegistry:
        """Registry that scans the temp dir (contains v2/user.py stub)."""
        return APIVersionRegistry(api_base_path=self._tmpdir)

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_filesystem_version_discovery_and_loading(self):
        """
        Validates APIVersionRegistry correctly scans the filesystem for versions,
        and DynamicClassLoader routes to the correct user module classes.
        """
        registry = self._registry_with_v2()
        supported = registry.get_supported_versions()
        self.assertIn("2", supported)
        self.assertTrue(len(supported) >= 1)

        latest = registry.get_latest_version()
        self.assertIsNotNone(latest)
        loader = DynamicClassLoader(registry)

        AnsibleClass, APIClass, MixinClass = loader.load_classes_for_module("user", "2")
        self.assertEqual(APIClass.__name__, "APIUser_v2")
        self.assertEqual(AnsibleClass.__name__, "AnsibleUser")
        self.assertTrue(hasattr(MixinClass, "get_endpoint_operations"))

    def test_loader_unsupported_version(self):
        """
        Validates loader gracefully degrades to the closest lower supported version
        if an unknown futuristic version is explicitly requested.
        """
        registry = self._registry_with_v2()
        loader = DynamicClassLoader(registry)
        AnsibleClass, APIClass, MixinClass = loader.load_classes_for_module("user", "12")
        self.assertEqual(APIClass.__name__, "APIUser_v2")
        self.assertEqual(AnsibleClass.__name__, "AnsibleUser")

    @patch("ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager.get_credential_manager")
    @patch("ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager._get_requests")
    def test_platform_service_version_fallback(self, mock_get_requests, mock_cred_manager):
        """
        Validates that when /v1/ping/ succeeds with no X-API-Version header,
        PlatformService conservatively returns '1' regardless of what the JSON
        body reports.

        Design intent (see _detect_api_version docstring): successfully reaching
        /api/gateway/v1/ping/ confirms that API v1 is available.  The
        implementation intentionally never falls back to get_latest_version() —
        a collection that ships v2 must not assume the server supports v2.
        """
        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"current_version": "/api/gateway/v3/", "available_versions": {"v3": "/api/gateway/v3/"}}
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
        # /v1/ping/ returned 200 with no X-API-Version header -> v1 confirmed.
        # The implementation does NOT fall back to get_latest_version().
        self.assertEqual(service.api_version, "1")

    @patch("ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry.logger")
    def test_loader_closest_higher_with_warning(self, mock_logger):
        """
        Validates the closest higher fallback strategy and ensures a warning is logged.
        """
        registry = APIVersionRegistry()
        registry.module_versions["user"] = ["2", "3"]
        best_version = registry.find_best_version("1", "user")
        self.assertEqual(best_version, "2")
        mock_logger.warning.assert_called()
        self.assertIn("closest higher version", mock_logger.warning.call_args[0][0])

    def test_loader_fail_when_no_versions(self):
        """
        Validates that a ValueError is raised when no compatible version is found.
        """
        registry = APIVersionRegistry()
        registry.module_versions["incomplete_module"] = []
        loader = DynamicClassLoader(registry)
        with self.assertRaises(ValueError) as context:
            loader.load_classes_for_module("incomplete_module", "1")
        self.assertIn("No compatible API version found for module 'incomplete_module'", str(context.exception))


if __name__ == "__main__":
    unittest.main()
