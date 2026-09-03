# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for inventory CA bundle forwarding in manager subprocess environment."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import ProcessManager  # noqa: E402
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig  # noqa: E402


class TestMergeManagerEnvironment(unittest.TestCase):
    def _config(self, **kwargs):
        defaults = {
            "base_url": "https://gw.example",
            "verify_ssl": True,
            "ca_bundle": None,
        }
        defaults.update(kwargs)
        return GatewayConfig(**defaults)

    @patch.dict("os.environ", {}, clear=True)
    def test_inventory_ca_bundle_sets_requests_ca_bundle(self):
        env = ProcessManager.merge_manager_environment(
            self._config(ca_bundle="/tmp/inventory-ca.pem"),
        )
        self.assertEqual(env["REQUESTS_CA_BUNDLE"], "/tmp/inventory-ca.pem")

    @patch.dict("os.environ", {}, clear=True)
    def test_task_env_overrides_inventory_ca_bundle(self):
        env = ProcessManager.merge_manager_environment(
            self._config(ca_bundle="/tmp/inventory-ca.pem"),
            task_env={"REQUESTS_CA_BUNDLE": "/tmp/task-ca.pem"},
        )
        self.assertEqual(env["REQUESTS_CA_BUNDLE"], "/tmp/task-ca.pem")

    @patch.dict("os.environ", {"REQUESTS_CA_BUNDLE": "/tmp/shell-ca.pem"}, clear=True)
    def test_existing_shell_env_overrides_inventory_ca_bundle(self):
        env = ProcessManager.merge_manager_environment(
            self._config(ca_bundle="/tmp/inventory-ca.pem"),
        )
        self.assertEqual(env["REQUESTS_CA_BUNDLE"], "/tmp/shell-ca.pem")

    @patch.dict("os.environ", {"REQUESTS_CA_BUNDLE": "/tmp/shell-ca.pem"}, clear=True)
    def test_existing_shell_env_overrides_task_env_for_requests_ca_bundle(self):
        env = ProcessManager.merge_manager_environment(
            self._config(ca_bundle="/tmp/inventory-ca.pem"),
            task_env={"REQUESTS_CA_BUNDLE": "/tmp/task-ca.pem"},
        )
        self.assertEqual(env["REQUESTS_CA_BUNDLE"], "/tmp/shell-ca.pem")

    @patch.dict("os.environ", {}, clear=True)
    def test_ca_bundle_not_applied_when_verify_disabled(self):
        env = ProcessManager.merge_manager_environment(
            self._config(ca_bundle="/tmp/inventory-ca.pem", verify_ssl=False),
        )
        self.assertNotIn("REQUESTS_CA_BUNDLE", env)

    @patch.dict("os.environ", {"SSL_CERT_FILE": "/tmp/legacy-ca.pem"}, clear=True)
    def test_ssl_cert_file_shim_still_applies(self):
        env = ProcessManager.merge_manager_environment(self._config())
        self.assertEqual(env["REQUESTS_CA_BUNDLE"], "/tmp/legacy-ca.pem")


if __name__ == "__main__":
    unittest.main()
