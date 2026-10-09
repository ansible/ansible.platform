# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for schedule v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.schedule import AnsibleSchedule  # noqa: E402
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.schedule import ScheduleTransformMixin_v2  # noqa: E402


class TestScheduleTransform(unittest.TestCase):
    def test_create_includes_all_fields(self):
        ansible = AnsibleSchedule(name="Weekly", rrule="DTSTART:20261007T120000Z RRULE:FREQ=WEEKLY", unified_job_template="5", enabled=True)
        api = ScheduleTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "Weekly")
        self.assertEqual(api.rrule, "DTSTART:20261007T120000Z RRULE:FREQ=WEEKLY")
        self.assertEqual(api.unified_job_template, 5)
        self.assertIs(api.enabled, True)

    def test_create_omits_unset_fields(self):
        ansible = AnsibleSchedule(name="minimal")
        api = ScheduleTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "minimal")
        self.assertIsNone(api.rrule)
        self.assertIsNone(api.unified_job_template)

    def test_ujt_name_resolves_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 42
        ansible = AnsibleSchedule(name="s", unified_job_template="Demo Job Template")
        api = ScheduleTransformMixin_v2.from_ansible_data(ansible, {"operation": "create", "manager": mock_manager})
        mock_manager.lookup_resource_id.assert_called_once_with("unified_job_templates", "name", "Demo Job Template", service="controller")
        self.assertEqual(api.unified_job_template, 42)

    def test_ujt_id_skips_lookup(self):
        ansible = AnsibleSchedule(name="s", unified_job_template="42")
        api = ScheduleTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.unified_job_template, 42)

    def test_update_with_new_name(self):
        ansible = AnsibleSchedule(name="old", new_name="new")
        api = ScheduleTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "new")

    def test_update_without_new_name_echoes(self):
        ansible = AnsibleSchedule(name="keep")
        api = ScheduleTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "keep")

    def test_from_api_returns_ansible_instance(self):
        api_data = {"id": 99, "name": "Weekly", "rrule": "DTSTART:20261007T120000Z", "unified_job_template": 5, "enabled": True}
        ansible = ScheduleTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleSchedule)
        self.assertEqual(ansible.id, 99)
        self.assertEqual(ansible.unified_job_template, "5")

    def test_from_api_handles_missing_fields(self):
        ansible = ScheduleTransformMixin_v2.from_api({"name": "bare"}, {})
        self.assertIsNone(ansible.rrule)
        self.assertIsNone(ansible.id)

    def test_endpoint_operations_use_controller_paths(self):
        ops = ScheduleTransformMixin_v2.get_endpoint_operations()
        for op_name, op in ops.items():
            self.assertTrue(op.path.startswith("/api/controller/v2/schedules"), f"{op_name}: {op.path}")

    def test_lookup_field_is_name(self):
        self.assertEqual(ScheduleTransformMixin_v2.get_lookup_field(), "name")

    def test_id_passthrough(self):
        ansible = AnsibleSchedule(name="s", id=99)
        api = ScheduleTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 99)


if __name__ == "__main__":
    unittest.main()
