# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the notification_template v1 transform mixin (AAP-91391)."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.notification_template import (  # noqa: E402
    AnsibleNotificationTemplate,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.notification_template import (  # noqa: E402
    APINotificationTemplate_v1,
    NotificationTemplateTransformMixin_v1,
)


def _make_context(lookup_returns=None, default=1):
    manager = MagicMock()
    if lookup_returns is not None:

        def _side_effect(endpoint, field, value):
            return lookup_returns.get((endpoint, value), default)

        manager.lookup_resource_id.side_effect = _side_effect
    else:
        manager.lookup_resource_id.return_value = default
    context = MagicMock()
    context.manager = manager
    return context


class TestNotificationTemplateTransform(unittest.TestCase):
    def test_from_ansible_data_resolves_organization(self):
        ansible = AnsibleNotificationTemplate(name="nt", organization="Default")
        context = _make_context(lookup_returns={("/api/controller/v2/organizations/", "Default"): 10})

        api = NotificationTemplateTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.organization, 10)

    def test_from_ansible_data_uses_new_name_when_set(self):
        ansible = AnsibleNotificationTemplate(name="old", new_name="new")
        context = _make_context()

        api = NotificationTemplateTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.name, "new")

    def test_from_ansible_data_passes_notification_configuration_and_messages(self):
        ansible = AnsibleNotificationTemplate(
            name="nt",
            notification_type="webhook",
            notification_configuration={"url": "http://example.invalid"},
            messages={"started": {"message": "hi"}},
        )
        context = _make_context()

        api = NotificationTemplateTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.notification_type, "webhook")
        self.assertEqual(api.notification_configuration, {"url": "http://example.invalid"})
        self.assertEqual(api.messages, {"started": {"message": "hi"}})

    def test_from_api_maps_fields(self):
        ansible = NotificationTemplateTransformMixin_v1.from_api(
            {"id": 1, "name": "nt", "organization": 10, "notification_type": "webhook"},
            _make_context(),
        )

        self.assertEqual(ansible.organization, "10")
        self.assertEqual(ansible.notification_type, "webhook")

    def test_get_endpoint_operations_use_controller_paths(self):
        ops = NotificationTemplateTransformMixin_v1.get_endpoint_operations()
        for op_name in ("create", "list"):
            self.assertTrue(ops[op_name].path.startswith("/api/controller/v2/notification_templates"))

    def test_get_find_list_query_params_scopes_by_organization(self):
        api_data = APINotificationTemplate_v1(name="nt", organization=10)
        params = NotificationTemplateTransformMixin_v1.get_find_list_query_params(api_data)
        self.assertEqual(params, {"organization": 10})


if __name__ == "__main__":
    unittest.main()
