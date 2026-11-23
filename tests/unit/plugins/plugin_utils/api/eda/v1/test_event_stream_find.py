# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for organization-scoped, unique event stream lookups."""

import json
import threading
import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.event_stream import AnsibleEventStream
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.event_stream import EventStreamTransformMixin_v1
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext


class TestEventStreamFind(unittest.TestCase):
    """Both client paths reject duplicate matches instead of selecting one."""

    def test_idempotency_uses_returned_relationship_ids_without_name_lookup(self):
        manager = MagicMock()
        context = TransformContext(manager=manager, session=MagicMock(), cache={}, api_version="1", service="eda", operation="update")
        current = EventStreamTransformMixin_v1.from_api(
            {
                "id": 42,
                "name": "stream",
                "eda_credential": {"id": 7, "name": "Events Credential"},
                "organization": {"id": 3, "name": "7"},
            },
            context,
        )

        value = EventStreamTransformMixin_v1.get_idempotency_value_from_current_data(
            "eda_credential_id",
            {"credential_name": current.credential_name, "organization_name": current.organization_name},
            context,
        )

        self.assertEqual(value, 7)
        organization_id = EventStreamTransformMixin_v1.get_idempotency_value_from_current_data(
            "organization_id",
            {"credential_name": current.credential_name, "organization_name": current.organization_name},
            context,
        )

        self.assertEqual(current.organization_name, "7")
        self.assertEqual(organization_id, 3)
        manager.lookup_resource_id.assert_not_called()

    def test_organization_idempotency_falls_back_to_name_resolution_without_retained_id(self):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 3
        context = TransformContext(manager=manager, session=MagicMock(), cache={}, api_version="1", service="eda", operation="update")

        value = EventStreamTransformMixin_v1.get_idempotency_value_from_current_data(
            "organization_id",
            {"organization_name": "Events"},
            context,
        )

        self.assertEqual(value, 3)
        manager.lookup_resource_id.assert_called_once_with("organizations", "name", "Events", service="eda", extra_query_params=None, require_unique=True)

    def test_platform_service_rejects_multiple_matches(self):
        service = PlatformService.__new__(PlatformService)
        service.base_url = "https://gateway.example"
        service.api_versions = {"eda": "1"}
        service.session = MagicMock()
        service.cache = {}
        response = MagicMock()
        response.json.return_value = {"count": 2, "results": [{"id": 1}]}
        service._make_request = MagicMock(return_value=response)
        context = TransformContext(manager=service, session=service.session, cache={}, api_version="1", service="eda", operation="find")

        with self.assertRaisesRegex(ValueError, "matched multiple resources"):
            service._find_resource(AnsibleEventStream(name="same", organization_name="7"), EventStreamTransformMixin_v1, context)

        request_url = service._make_request.call_args.args[1]
        self.assertIn("organization_id=7", request_url)

    def test_direct_client_rejects_multiple_matches(self):
        client = DirectHTTPClient.__new__(DirectHTTPClient)
        client.base_url = "https://gateway.example"
        client.api_versions = {"eda": "1"}
        client._lock = threading.Lock()
        client._http_request_count = 0
        response = MagicMock()
        response.read.return_value = json.dumps({"count": 2, "results": [{"id": 1}]}).encode()
        client._make_request = MagicMock(return_value=response)
        context = TransformContext(manager=client, session=MagicMock(), cache={}, api_version="1", service="eda", operation="find")

        with self.assertRaisesRegex(ValueError, "matched multiple resources"):
            client._find_resource(AnsibleEventStream(name="same", organization_name="7"), EventStreamTransformMixin_v1, context)

        request_url = client._make_request.call_args.args[1]
        self.assertIn("organization_id=7", request_url)


if __name__ == "__main__":
    unittest.main()
