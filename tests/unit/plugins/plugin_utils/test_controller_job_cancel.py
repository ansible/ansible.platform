# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for controller_job_cancel ansible model and transform mixin."""

from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_job_cancel import AnsibleControllerJobCancel
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_job_cancel import (
    APIControllerJobCancel_v2,
    ControllerJobCancelTransformMixin_v2,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext

__metaclass__ = type


class TestAnsibleControllerJobCancel(unittest.TestCase):
    """Tests for the AnsibleControllerJobCancel dataclass."""

    def test_defaults(self):
        model = AnsibleControllerJobCancel()
        self.assertEqual(model.job_id, 0)
        self.assertFalse(model.fail_if_not_running)
        self.assertIsNone(model.id)

    def test_construction(self):
        model = AnsibleControllerJobCancel(job_id=42, fail_if_not_running=True)
        self.assertEqual(model.job_id, 42)
        self.assertTrue(model.fail_if_not_running)

    def test_round_trip_dict(self):
        from dataclasses import asdict

        model = AnsibleControllerJobCancel(job_id=99, fail_if_not_running=False)
        d = asdict(model)
        self.assertEqual(d["job_id"], 99)
        self.assertFalse(d["fail_if_not_running"])
        reconstructed = AnsibleControllerJobCancel(**d)
        self.assertEqual(reconstructed, model)


class TestControllerJobCancelTransformMixin(unittest.TestCase):
    """Tests for the ControllerJobCancelTransformMixin_v2."""

    def _context(self, operation="find"):
        return TransformContext(
            manager=MagicMock(),
            session=MagicMock(),
            cache={},
            api_version="2",
            service="controller",
            operation=operation,
        )

    def test_from_ansible_data(self):
        ansible_data = AnsibleControllerJobCancel(job_id=42, fail_if_not_running=True)
        ctx = self._context()
        api_data = ControllerJobCancelTransformMixin_v2.from_ansible_data(ansible_data, ctx)

        self.assertIsInstance(api_data, APIControllerJobCancel_v2)
        self.assertEqual(api_data.job_id, 42)
        self.assertTrue(api_data.fail_if_not_running)

    def test_from_api(self):
        api_response = {"id": 42, "name": "some-job", "status": "running"}
        ctx = self._context()
        ansible_data = ControllerJobCancelTransformMixin_v2.from_api(api_response, ctx)

        self.assertIsInstance(ansible_data, AnsibleControllerJobCancel)
        self.assertEqual(ansible_data.job_id, 42)
        self.assertEqual(ansible_data.id, 42)

    def test_get_lookup_field(self):
        self.assertEqual(ControllerJobCancelTransformMixin_v2.get_lookup_field(), "job_id")

    def test_endpoint_operations_have_list_and_get(self):
        ops = ControllerJobCancelTransformMixin_v2.get_endpoint_operations()
        self.assertIn("list", ops)
        self.assertIn("get", ops)
        self.assertEqual(ops["list"].method, "GET")
        self.assertEqual(ops["get"].method, "GET")
        self.assertIn("controller", ops["list"].path)


if __name__ == "__main__":
    unittest.main()
