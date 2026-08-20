# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests that CA bundle auth params are stripped before model instantiation."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin  # noqa: E402


class TestAuthParamsCaBundle(unittest.TestCase):
    _CA_BUNDLE_KEYS = frozenset(
        {
            "aap_ca_bundle",
            "gateway_ca_bundle",
            "ansible_platform_ca_bundle",
        }
    )

    def test_ca_bundle_keys_are_auth_params(self):
        self.assertTrue(self._CA_BUNDLE_KEYS.issubset(BaseResourceActionPlugin._AUTH_PARAMS))

    def test_ca_bundle_keys_stripped_from_resource_data(self):
        validated_params = {
            "name": "ssl-env-test-org",
            "aap_ca_bundle": "/tmp/aap-ca.pem",
            "gateway_ca_bundle": "/tmp/gateway-ca.pem",
            "ansible_platform_ca_bundle": "/tmp/platform-ca.pem",
            "gateway_hostname": "https://gateway.example",
        }
        resource_data = {k: v for k, v in validated_params.items() if v is not None and k not in BaseResourceActionPlugin._AUTH_PARAMS}

        self.assertEqual(resource_data, {"name": "ssl-env-test-org"})
        for key in self._CA_BUNDLE_KEYS:
            self.assertNotIn(key, resource_data)


if __name__ == "__main__":
    unittest.main()
