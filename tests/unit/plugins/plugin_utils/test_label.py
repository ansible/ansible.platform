# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for label v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.label import AnsibleLabel  # noqa: E402
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.label import LabelTransformMixin_v2  # noqa: E402


class TestLabelTransform(unittest.TestCase):
    """Ansible <-> API round-trip tests for label."""

    def test_create_includes_name_and_org(self):
        ansible = AnsibleLabel(name="Production", organization="1")
        api = LabelTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "Production")
        self.assertEqual(api.organization, 1)

    def test_create_with_org_name_resolves_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 42
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleLabel(name="Test", organization="Default")
        api = LabelTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_called_once_with("organizations", "name", "Default")
        self.assertEqual(api.organization, 42)

    def test_create_with_org_id_skips_lookup(self):
        ansible = AnsibleLabel(name="Test", organization="42")
        api = LabelTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.organization, 42)

    def test_update_with_new_name(self):
        ansible = AnsibleLabel(name="old", organization="1", new_name="new")
        api = LabelTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "new")

    def test_update_without_new_name_echoes(self):
        ansible = AnsibleLabel(name="keep", organization="1")
        api = LabelTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "keep")

    def test_update_numeric_name_not_echoed(self):
        ansible = AnsibleLabel(name="42", organization="1")
        api = LabelTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertIsNone(api.name)

    def test_from_api_returns_ansible_instance(self):
        api_data = {"id": 99, "name": "Production", "organization": 5}
        ansible = LabelTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleLabel)
        self.assertEqual(ansible.id, 99)
        self.assertEqual(ansible.name, "Production")
        self.assertEqual(ansible.organization, "5")

    def test_from_api_handles_missing_fields(self):
        ansible = LabelTransformMixin_v2.from_api({"name": "bare", "organization": 1}, {})
        self.assertEqual(ansible.name, "bare")
        self.assertIsNone(ansible.id)

    def test_endpoint_operations_use_controller_paths(self):
        ops = LabelTransformMixin_v2.get_endpoint_operations()
        for op_name, op in ops.items():
            self.assertTrue(
                op.path.startswith("/api/controller/v2/labels"),
                f"{op_name} path should start with /api/controller/v2/labels, got {op.path}",
            )

    def test_no_delete_operation(self):
        ops = LabelTransformMixin_v2.get_endpoint_operations()
        self.assertNotIn("delete", ops)

    def test_lookup_field_is_name(self):
        self.assertEqual(LabelTransformMixin_v2.get_lookup_field(), "name")

    def test_id_passthrough_for_update(self):
        ansible = AnsibleLabel(name="lbl", organization="1", id=99)
        api = LabelTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 99)


if __name__ == "__main__":
    unittest.main()
