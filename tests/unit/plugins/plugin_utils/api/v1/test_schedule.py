# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the schedule v1 transform mixin (AAP-91390)."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.schedule import (  # noqa: E402
    AnsibleSchedule,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.schedule import (  # noqa: E402
    APISchedule_v1,
    ScheduleTransformMixin_v1,
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


class TestScheduleTransform(unittest.TestCase):
    def test_from_ansible_data_resolves_all_fk_fields(self):
        ansible = AnsibleSchedule(
            name="sched",
            rrule="DTSTART:20191219T130551Z RRULE:FREQ=WEEKLY;INTERVAL=1;COUNT=1",
            unified_job_template="Demo Job Template",
            inventory="Demo Inventory",
            execution_environment="Default EE",
        )
        lookups = {
            ("/api/controller/v2/unified_job_templates/", "Demo Job Template"): 10,
            ("/api/controller/v2/inventories/", "Demo Inventory"): 20,
            ("/api/controller/v2/execution_environments/", "Default EE"): 30,
        }
        context = _make_context(lookup_returns=lookups)

        api = ScheduleTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.unified_job_template, 10)
        self.assertEqual(api.inventory, 20)
        self.assertEqual(api.execution_environment, 30)
        self.assertEqual(api.rrule, "DTSTART:20191219T130551Z RRULE:FREQ=WEEKLY;INTERVAL=1;COUNT=1")

    def test_from_ansible_data_uses_new_name_when_set(self):
        ansible = AnsibleSchedule(name="old", new_name="new")
        context = _make_context()

        api = ScheduleTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.name, "new")

    def test_from_ansible_data_passes_extra_data_dict_through(self):
        ansible = AnsibleSchedule(name="sched", extra_data={"foo": "bar"})
        context = _make_context()

        api = ScheduleTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.extra_data, {"foo": "bar"})

    def test_from_ansible_data_includes_id_for_update_url(self):
        ansible = AnsibleSchedule(name="sched", id=55)
        context = _make_context()

        api = ScheduleTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.id, 55)

    def test_from_api_maps_fields(self):
        ansible = ScheduleTransformMixin_v1.from_api(
            {"id": 1, "name": "sched", "unified_job_template": 10, "inventory": 20},
            _make_context(),
        )

        self.assertEqual(ansible.unified_job_template, "10")
        self.assertEqual(ansible.inventory, "20")

    def test_get_endpoint_operations_use_controller_paths(self):
        ops = ScheduleTransformMixin_v1.get_endpoint_operations()
        for op_name in ("create", "list"):
            self.assertTrue(ops[op_name].path.startswith("/api/controller/v2/schedules"))

    def test_get_find_list_query_params_scopes_by_unified_job_template(self):
        api_data = APISchedule_v1(name="sched", unified_job_template=10)
        params = ScheduleTransformMixin_v1.get_find_list_query_params(api_data)
        self.assertEqual(params, {"unified_job_template": 10})


if __name__ == "__main__":
    unittest.main()
