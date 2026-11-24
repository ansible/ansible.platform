"""Tests for Controller-side organization configuration transforms."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_organization import (  # noqa: E402
    AnsibleControllerOrganization,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_organization import (  # noqa: E402
    BASE_PATH,
    ControllerOrganizationTransformMixin_v2,
)


class TestControllerOrganizationTransform(unittest.TestCase):
    """Verify sparse updates use Controller-owned IDs and endpoints."""

    def test_omitted_fields_have_no_defaults(self):
        ansible = AnsibleControllerOrganization(name="Default")

        api = ControllerOrganizationTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})

        self.assertEqual(api.name, "Default")
        self.assertIsNone(api.default_environment)
        self.assertIsNone(api.max_hosts)
        self.assertIsNone(api.description)

    def test_description_is_preserved_in_update_payload(self):
        ansible = AnsibleControllerOrganization(name="Default", description="Managed by Controller")

        api = ControllerOrganizationTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})

        self.assertEqual(api.description, "Managed by Controller")

    def test_default_environment_name_resolves_in_controller(self):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 27
        ansible = AnsibleControllerOrganization(name="Default", default_environment="Python EE")

        api = ControllerOrganizationTransformMixin_v2.from_ansible_data(ansible, {"operation": "update", "manager": manager})

        manager.lookup_resource_id.assert_called_once_with("execution_environments", "name", "Python EE", service="controller")
        self.assertEqual(api.default_environment, 27)

    def test_numeric_default_environment_is_controller_id(self):
        manager = MagicMock()
        ansible = AnsibleControllerOrganization(name="Default", default_environment="27", max_hosts=100)

        api = ControllerOrganizationTransformMixin_v2.from_ansible_data(ansible, {"operation": "update", "manager": manager})

        manager.lookup_resource_id.assert_not_called()
        self.assertEqual(api.default_environment, 27)
        self.assertEqual(api.max_hosts, 100)

    def test_only_controller_update_endpoint_is_mutable(self):
        operations = ControllerOrganizationTransformMixin_v2.get_endpoint_operations()

        self.assertEqual(operations["update"].path, BASE_PATH + "/{id}/")
        self.assertEqual(operations["update"].method, "PATCH")
        self.assertEqual(operations["update"].fields, ["description", "default_environment", "max_hosts"])
        self.assertNotIn("create", operations)
        self.assertNotIn("delete", operations)

    def test_description_is_preserved_from_api(self):
        ansible = ControllerOrganizationTransformMixin_v2.from_api(
            {"id": 31, "name": "Default", "description": "Managed by Controller"},
            {},
        )

        self.assertEqual(ansible.description, "Managed by Controller")


if __name__ == "__main__":
    unittest.main()
