# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the service key API transform."""

import sys
import unittest
from pathlib import Path

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.service_key import (  # noqa: E402
    AnsibleServiceKey,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.service_key import (  # noqa: E402
    ServiceKeyTransformMixin_v1,
)


class TestServiceKeyTransform(unittest.TestCase):
    """Service key requests only send editable fields."""

    def test_endpoint_operations_only_include_editable_fields(self):
        operations = ServiceKeyTransformMixin_v1.get_endpoint_operations()

        self.assertEqual(operations["create"].method, "POST")
        self.assertEqual(operations["create"].fields, ["name", "is_active"])
        self.assertEqual(operations["update"].fields, ["name", "is_active"])

    def test_update_maps_name_and_active_state(self):
        service_key = AnsibleServiceKey(name="existing-key", new_name="renamed-key", is_active=False)

        api = ServiceKeyTransformMixin_v1.from_ansible_data(service_key, {"operation": "update"})

        self.assertEqual(api.name, "renamed-key")
        self.assertIs(api.is_active, False)

    def test_create_operation_builds_a_payload_with_editable_fields(self):
        service_key = AnsibleServiceKey(name="new-key", is_active=True)

        api = ServiceKeyTransformMixin_v1.from_ansible_data(service_key, {"operation": "create"})

        self.assertEqual(api.name, "new-key")
        self.assertIs(api.is_active, True)


if __name__ == "__main__":
    unittest.main()
