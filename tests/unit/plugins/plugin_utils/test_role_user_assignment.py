# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for fail-closed RoleUserAssignment identity resolution."""

from __future__ import absolute_import, division, print_function

import unittest
from threading import Lock
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.role_user_assignment import AnsibleRoleUserAssignment
from ansible_collections.ansible.platform.plugins.plugin_utils.api.gateway.v1.role_user_assignment import RoleUserAssignmentTransformMixin_v1
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext


def _client(client_mode):
    if client_mode == "direct":
        client = DirectHTTPClient.__new__(DirectHTTPClient)
        client._lock = Lock()
        client._http_request_count = 0
    else:
        client = PlatformService.__new__(PlatformService)
        client.cache = {}

    client.base_url = "https://gateway.example"
    client.api_versions = {"gateway": "1"}
    client.session = MagicMock()
    client._make_request = MagicMock()
    return client


def _context(client):
    return TransformContext(manager=client, session=client.session, cache={}, api_version="1", service="gateway", operation="find")


class TestRoleUserAssignmentIdentityResolution(unittest.TestCase):
    """A failed supplied selector must stop a find before it can broaden."""

    def test_missing_user_fails_before_request_in_both_client_modes(self):
        ansible = AnsibleRoleUserAssignment(role_definition="Organization Admin", user="missing-user", object_id=30)

        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode)

                def lookup_resource(endpoint, lookup_field, value):
                    if endpoint == "role_definitions":
                        return 10
                    raise ValueError("Resource 'users' with username=missing-user not found")

                client.lookup_resource_id = MagicMock(side_effect=lookup_resource)

                with self.assertRaisesRegex(ValueError, "users.*missing-user.*not found"):
                    client._find_resource(ansible, RoleUserAssignmentTransformMixin_v1, _context(client))

                client._make_request.assert_not_called()

    def test_object_name_lookup_continues_only_after_not_found(self):
        ansible = AnsibleRoleUserAssignment(role_definition="Team Admin", user="alice", object_id="Ops Team")
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = [
            10,
            20,
            ValueError("Resource 'teams' with name=Ops Team not found"),
            30,
        ]

        api_data = RoleUserAssignmentTransformMixin_v1.from_ansible_data(ansible, {"manager": manager})

        self.assertEqual(api_data.role_definition, 10)
        self.assertEqual(api_data.user, 20)
        self.assertEqual(api_data.object_id, 30)

    def test_ambiguous_user_lookup_propagates(self):
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = ValueError("Resource 'users' username=alice matched multiple resources")
        ansible = AnsibleRoleUserAssignment(role_definition="Organization Admin", user="alice", object_id=30)

        with self.assertRaisesRegex(ValueError, "matched multiple resources"):
            RoleUserAssignmentTransformMixin_v1.from_ansible_data(ansible, {"manager": manager})


if __name__ == "__main__":
    unittest.main()
