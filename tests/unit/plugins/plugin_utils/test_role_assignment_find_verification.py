# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""A list-based assignment find must not accept a row it did not ask for."""

from __future__ import absolute_import, division, print_function

import json
import unittest
from threading import Lock
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.role_team_assignment import AnsibleRoleTeamAssignment
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.role_user_assignment import AnsibleRoleUserAssignment
from ansible_collections.ansible.platform.plugins.plugin_utils.api.gateway.v1.role_team_assignment import RoleTeamAssignmentTransformMixin_v1
from ansible_collections.ansible.platform.plugins.plugin_utils.api.gateway.v1.role_user_assignment import RoleUserAssignmentTransformMixin_v1
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext

ROLE_DEFS = {"Organization Admin": 10, "Organization Member": 11, "custom_org_admin": 90}
USERS = {"UserA": 7}
TEAMS = {"TeamA": 4}
ORGS = {"OrgA": 3}


def _client(client_mode, list_payload):
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
    client._authenticated = True

    def search_api(endpoint, query_params=None, **kwargs):
        # Some assignment mixins page through every result instead of issuing a
        # single GET, and resolve their principal by name through the same call.
        if str(endpoint).strip("/") == "teams":
            name = (query_params or {}).get("name")
            if name in TEAMS:
                return {"count": 1, "results": [{"id": TEAMS[name], "name": name}], "next": None}
            return {"count": 0, "results": [], "next": None}
        return list_payload

    client.search_api = MagicMock(side_effect=search_api)

    def lookup_resource_id(endpoint, lookup_field, value, **kwargs):
        table = {"role_definitions": ROLE_DEFS, "users": USERS, "teams": TEAMS, "organizations": ORGS}[endpoint]
        if str(value).isdigit():
            return int(value)
        if value not in table:
            raise ValueError("Resource '%s' with %s=%s not found" % (endpoint, lookup_field, value))
        return table[value]

    client.lookup_resource_id = MagicMock(side_effect=lookup_resource_id)

    def _make_request(method, url, operation=None, resource=None, **kwargs):
        response = MagicMock()
        response.json.return_value = list_payload
        response.read.return_value = json.dumps(list_payload).encode()
        response.ok = True
        return response

    client._make_request = MagicMock(side_effect=_make_request)
    return client


def _context(client):
    return TransformContext(manager=client, session=client.session, cache={}, api_version="1", service="gateway", operation="find")


class TestRoleUserAssignmentFindVerification(unittest.TestCase):
    def test_unrelated_role_in_list_response_is_not_treated_as_a_match(self):
        """A row for a different role must not satisfy the find (AAP-74089).

        Accepting it makes the caller skip the create, so the task reports
        success while the requested role was never assigned.
        """
        # Same user and object, but Organization Member (11), not the custom role (90).
        payload = {"count": 1, "results": [{"id": 500, "role_definition": 11, "user": 7, "object_id": 3}], "next": None}
        ansible = AnsibleRoleUserAssignment(role_definition="custom_org_admin", user="UserA", object_id=3)

        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode, payload)
                with self.assertRaisesRegex(ValueError, "not found"):
                    client._find_resource(ansible, RoleUserAssignmentTransformMixin_v1, _context(client))

    def test_matching_row_is_still_returned(self):
        """The genuine assignment must still be found, so creates stay idempotent."""
        payload = {"count": 1, "results": [{"id": 501, "role_definition": 90, "user": 7, "object_id": 3}], "next": None}
        ansible = AnsibleRoleUserAssignment(role_definition="custom_org_admin", user="UserA", object_id=3)

        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode, payload)
                found = client._find_resource(ansible, RoleUserAssignmentTransformMixin_v1, _context(client))
                self.assertEqual(found["id"], 501)

    def test_matching_row_is_selected_from_a_mixed_response(self):
        """The right row must win even when the API returns several."""
        payload = {
            "count": 3,
            "results": [
                {"id": 500, "role_definition": 11, "user": 7, "object_id": 3},
                {"id": 501, "role_definition": 10, "user": 7, "object_id": 3},
                {"id": 502, "role_definition": 90, "user": 7, "object_id": 3},
            ],
            "next": None,
        }
        ansible = AnsibleRoleUserAssignment(role_definition="custom_org_admin", user="UserA", object_id=3)

        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode, payload)
                found = client._find_resource(ansible, RoleUserAssignmentTransformMixin_v1, _context(client))
                self.assertEqual(found["id"], 502)

    def test_nested_foreign_key_objects_compare_by_id(self):
        """Serializers that expand a foreign key must still match."""
        payload = {"count": 1, "results": [{"id": 503, "role_definition": {"id": 90}, "user": {"id": 7}, "object_id": 3}], "next": None}
        ansible = AnsibleRoleUserAssignment(role_definition="custom_org_admin", user="UserA", object_id=3)

        client = _client("persistent", payload)
        found = client._find_resource(ansible, RoleUserAssignmentTransformMixin_v1, _context(client))
        self.assertEqual(found["id"], 503)


class TestRoleTeamAssignmentFindVerification(unittest.TestCase):
    def test_unrelated_role_in_list_response_is_not_treated_as_a_match(self):
        """role_team_assignment shares the find path and the same exposure."""
        payload = {"count": 1, "results": [{"id": 600, "role_definition": 11, "team": 4, "object_id": 3}], "next": None}
        ansible = AnsibleRoleTeamAssignment(role_definition="custom_org_admin", team="TeamA", object_id=3)

        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode, payload)
                with self.assertRaisesRegex(ValueError, "not found"):
                    client._find_resource(ansible, RoleTeamAssignmentTransformMixin_v1, _context(client))

    def test_matching_row_is_still_returned(self):
        payload = {"count": 1, "results": [{"id": 601, "role_definition": 90, "team": 4, "object_id": 3}], "next": None}
        ansible = AnsibleRoleTeamAssignment(role_definition="custom_org_admin", team="TeamA", object_id=3)

        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode, payload)
                found = client._find_resource(ansible, RoleTeamAssignmentTransformMixin_v1, _context(client))
                self.assertEqual(found["id"], 601)


if __name__ == "__main__":
    unittest.main()
