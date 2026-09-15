# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the job_wait v1 transform mixin (AAP-91391)."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.job_wait import AnsibleJobWait  # noqa: E402
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.job_wait import (  # noqa: E402
    JobWaitTransformMixin_v1,
)


def _make_context():
    context = MagicMock()
    context.manager = MagicMock()
    return context


class TestJobWaitTransform(unittest.TestCase):
    def test_from_ansible_data_uses_job_id_on_first_call(self):
        ansible = AnsibleJobWait(job_id=123, job_type="jobs")

        api = JobWaitTransformMixin_v1.from_ansible_data(ansible, _make_context())

        self.assertEqual(api.id, 123)
        self.assertEqual(api.job_type, "jobs")

    def test_from_ansible_data_prefers_id_over_job_id_once_set(self):
        """Second call, during a wait poll, reuses the resolved id (replace() sets it)."""
        ansible = AnsibleJobWait(job_id=123, job_type="jobs", id=123)

        api = JobWaitTransformMixin_v1.from_ansible_data(ansible, _make_context())

        self.assertEqual(api.id, 123)

    def test_from_ansible_data_defaults_job_type_to_jobs(self):
        ansible = AnsibleJobWait(job_id=5)

        api = JobWaitTransformMixin_v1.from_ansible_data(ansible, _make_context())

        self.assertEqual(api.job_type, "jobs")

    def test_from_api_maps_fields(self):
        ansible = JobWaitTransformMixin_v1.from_api(
            {"id": 99, "status": "successful", "started": "2026-01-01T00:00:00Z", "finished": "2026-01-01T00:00:10Z", "elapsed": 10.0},
            _make_context(),
        )

        self.assertEqual(ansible.id, 99)
        self.assertEqual(ansible.job_id, 99)
        self.assertEqual(ansible.status, "successful")
        self.assertEqual(ansible.elapsed, 10.0)

    def test_get_endpoint_operations_target_job_type_scoped_path(self):
        ops = JobWaitTransformMixin_v1.get_endpoint_operations()
        self.assertEqual(ops["create"].path, "/api/controller/v2/{job_type}/{id}/")
        self.assertEqual(ops["get"].path, "/api/controller/v2/{job_type}/{id}/")
        self.assertEqual(set(ops["get"].path_params), {"job_type", "id"})
        self.assertNotIn("list", ops)


if __name__ == "__main__":
    unittest.main()
