from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_CP = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _CP not in sys.path:
    sys.path.insert(0, _CP)
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.notification_template import AnsibleNotificationTemplate  # noqa: E402
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.notification_template import (  # noqa: E402
    NotificationTemplateTransformMixin_v2,
)


class TestNotificationTemplateTransform(unittest.TestCase):
    def test_create(self):
        a = AnsibleNotificationTemplate(name="W", organization="1", notification_type="webhook", notification_configuration={"url": "x"})
        api = NotificationTemplateTransformMixin_v2.from_ansible_data(a, {"operation": "create"})
        self.assertEqual(api.name, "W")
        self.assertEqual(api.organization, 1)

    def test_omits(self):
        api = NotificationTemplateTransformMixin_v2.from_ansible_data(AnsibleNotificationTemplate(name="m", organization="1"), {"operation": "create"})
        self.assertIsNone(api.notification_type)

    def test_org(self):
        m = MagicMock()
        m.lookup_resource_id.return_value = 42
        NotificationTemplateTransformMixin_v2.from_ansible_data(
            AnsibleNotificationTemplate(name="n", organization="Default"), {"operation": "create", "manager": m}
        )
        m.lookup_resource_id.assert_called_once_with("organizations", "name", "Default")

    def test_new_name(self):
        api = NotificationTemplateTransformMixin_v2.from_ansible_data(
            AnsibleNotificationTemplate(name="o", organization="1", new_name="n"), {"operation": "update"}
        )
        self.assertEqual(api.name, "n")

    def test_from_api(self):
        r = NotificationTemplateTransformMixin_v2.from_api({"id": 99, "name": "W", "organization": 5, "notification_type": "webhook"}, {})
        self.assertEqual(r.id, 99)
        self.assertEqual(r.organization, "5")

    def test_from_api_resolves_org_name(self):
        mock_manager = MagicMock()
        mock_manager.lookup_organization_names.return_value = ["Default"]
        r = NotificationTemplateTransformMixin_v2.from_api({"name": "W", "organization": 5, "notification_type": "webhook"}, {"manager": mock_manager})
        mock_manager.lookup_organization_names.assert_called_once_with([5])
        self.assertEqual(r.organization, "Default")

    def test_from_api_null_organization(self):
        r = NotificationTemplateTransformMixin_v2.from_api({"name": "W", "organization": None}, {})
        self.assertIsNone(r.organization)

    def test_paths(self):
        for op in NotificationTemplateTransformMixin_v2.get_endpoint_operations().values():
            self.assertTrue(op.path.startswith("/api/controller/v2/notification_templates"))

    def test_lookup(self):
        self.assertEqual(NotificationTemplateTransformMixin_v2.get_lookup_field(), "name")

    def test_get_find_list_query_params_with_org(self):
        a = AnsibleNotificationTemplate(name="W", organization="1")
        api = NotificationTemplateTransformMixin_v2.from_ansible_data(a, {"operation": "create"})
        params = NotificationTemplateTransformMixin_v2.get_find_list_query_params(api)
        self.assertEqual(params, {"organization": 1})

    def test_get_find_list_query_params_without_org(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.notification_template import APINotificationTemplate_v2

        api = APINotificationTemplate_v2(name="W")
        params = NotificationTemplateTransformMixin_v2.get_find_list_query_params(api)
        self.assertEqual(params, {})

    def test_organization_is_optional(self):
        a = AnsibleNotificationTemplate(name="W", notification_type="webhook")
        self.assertIsNone(a.organization)


if __name__ == "__main__":
    unittest.main()
