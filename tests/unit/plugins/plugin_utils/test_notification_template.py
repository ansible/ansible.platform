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


class T(unittest.TestCase):
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

    def test_paths(self):
        for op in NotificationTemplateTransformMixin_v2.get_endpoint_operations().values():
            self.assertTrue(op.path.startswith("/api/controller/v2/notification_templates"))

    def test_lookup(self):
        self.assertEqual(NotificationTemplateTransformMixin_v2.get_lookup_field(), "name")


if __name__ == "__main__":
    unittest.main()
