# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests that persistent-manager socket identity includes TLS trust policy.

The CA bundle and verify_ssl flag are baked into the manager subprocess at
spawn time. If they are omitted from the socket-path hash, a later task that
changes aap_ca_bundle or aap_validate_certs reuses a stale manager and the new
trust policy silently does not apply.
"""

from __future__ import absolute_import, division, print_function

import tempfile
import unittest
from pathlib import Path

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import ProcessManager
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig


class TestManagerIdentityHash(unittest.TestCase):
    def _config(self, **kwargs):
        defaults = {
            "base_url": "https://gw.example",
            "username": "user",
            "password": "pass",
            "oauth_token": None,
            "verify_ssl": True,
            "ca_bundle": None,
        }
        defaults.update(kwargs)
        return GatewayConfig(**defaults)

    def _socket_path(self, socket_dir, **kwargs):
        info = ProcessManager.generate_connection_info(
            identifier="testhost",
            socket_dir=socket_dir,
            gateway_config=self._config(**kwargs),
        )
        return info.socket_path

    def test_same_identity_reuses_socket_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            socket_dir = Path(tmp)
            first = self._socket_path(socket_dir, ca_bundle="/ca.pem")
            second = self._socket_path(socket_dir, ca_bundle="/ca.pem")
            self.assertEqual(first, second)

    def test_different_ca_bundle_yields_different_socket(self):
        with tempfile.TemporaryDirectory() as tmp:
            socket_dir = Path(tmp)
            with_a = self._socket_path(socket_dir, ca_bundle="/ca-a.pem")
            with_b = self._socket_path(socket_dir, ca_bundle="/ca-b.pem")
            self.assertNotEqual(with_a, with_b)

    def test_ca_bundle_vs_none_yields_different_socket(self):
        with tempfile.TemporaryDirectory() as tmp:
            socket_dir = Path(tmp)
            with_bundle = self._socket_path(socket_dir, ca_bundle="/ca.pem")
            without_bundle = self._socket_path(socket_dir, ca_bundle=None)
            self.assertNotEqual(with_bundle, without_bundle)

    def test_different_verify_ssl_yields_different_socket(self):
        with tempfile.TemporaryDirectory() as tmp:
            socket_dir = Path(tmp)
            verified = self._socket_path(socket_dir, ca_bundle="/ca.pem", verify_ssl=True)
            skipped = self._socket_path(socket_dir, ca_bundle="/ca.pem", verify_ssl=False)
            self.assertNotEqual(verified, skipped)

    def test_different_password_still_yields_different_socket(self):
        with tempfile.TemporaryDirectory() as tmp:
            socket_dir = Path(tmp)
            first = self._socket_path(socket_dir, password="a")
            second = self._socket_path(socket_dir, password="b")
            self.assertNotEqual(first, second)

    def test_identity_hash_includes_bundle_and_verify(self):
        baseline = ProcessManager.manager_identity_hash(self._config())
        different_bundle = ProcessManager.manager_identity_hash(self._config(ca_bundle="/other.pem"))
        different_verify = ProcessManager.manager_identity_hash(self._config(verify_ssl=False))
        same = ProcessManager.manager_identity_hash(self._config())

        self.assertEqual(baseline, same)
        self.assertNotEqual(baseline, different_bundle)
        self.assertNotEqual(baseline, different_verify)
        self.assertNotEqual(different_bundle, different_verify)
        self.assertEqual(len(baseline), 8)


if __name__ == "__main__":
    unittest.main()
