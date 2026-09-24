# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for authenticator user API v1 transformations."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.authenticator_user import (  # noqa: E402
    AnsibleAuthenticatorUser,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.authenticator_user import (  # noqa: E402
    AuthenticatorUserTransformMixin_v1,
)


class TestAuthenticatorUserTransform(unittest.TestCase):
    """Ansible-to-API mappings for authenticator users."""

    def test_from_ansible_data_maps_numeric_authenticator(self):
        ansible = AnsibleAuthenticatorUser(
            authenticator_user_id="42",
            authenticator="7",
        )

        api = AuthenticatorUserTransformMixin_v1.from_ansible_data(ansible, {})

        self.assertEqual(api.id, 42)
        self.assertEqual(api.new_authenticator, 7)

    def test_from_api_resolves_provider_slug_to_authenticator_id(self):
        manager = Mock()
        manager.lookup_resource_id.return_value = 7
        ansible = AuthenticatorUserTransformMixin_v1.from_api(
            {
                "id": 42,
                "provider": "example-authenticator",
                "uid": "example-user",
                "user": 10,
            },
            {"manager": manager},
        )

        self.assertEqual(ansible.authenticator_user_id, "42")
        self.assertEqual(ansible.authenticator, "7")
        manager.lookup_resource_id.assert_called_once_with("authenticators", "slug", "example-authenticator")
        self.assertEqual(ansible.uid, "example-user")
        self.assertEqual(ansible.user, 10)


if __name__ == "__main__":
    unittest.main()
