# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the JobWait transform mixin."""

from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.job_wait import AnsibleJobWait
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.job_wait import JobWaitTransformMixin_v2
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import EndpointOperation, TransformContext

__metaclass__ = type


class TestJobWaitFind(unittest.TestCase):
    def test_find_operations_select_resource_for_each_job_type(self):
        for job_type, resource in (
            ("jobs", "jobs"),
            ("project_updates", "project_updates"),
            ("inventory_updates", "inventory_updates"),
            ("workflow_jobs", "workflow_jobs"),
        ):
            with self.subTest(job_type=job_type):
                operations = JobWaitTransformMixin_v2.get_find_endpoint_operations(AnsibleJobWait(job_id=42, job_type=job_type))

                self.assertEqual(
                    operations["get"],
                    EndpointOperation(
                        path="/%s/{id}/" % resource,
                        method="GET",
                        fields=[],
                        path_params=["id"],
                        required_for="find",
                        order=1,
                    ),
                )

    def test_find_rejects_unknown_job_type(self):
        with self.assertRaisesRegex(ValueError, "Unsupported job_type 'unknown'"):
            JobWaitTransformMixin_v2.get_find_endpoint_operations(AnsibleJobWait(job_id=42, job_type="unknown"))

    def test_resolve_uses_standard_sdk_find_flow(self):
        manager = MagicMock()
        manager._find_resource.return_value = {"id": 42, "status": "running"}
        instance = AnsibleJobWait(job_id=42, job_type="jobs")
        context = TransformContext(manager=manager, session=MagicMock(), cache={}, api_version="2", service="controller")

        result = JobWaitTransformMixin_v2.resolve(instance, context)

        self.assertEqual(result, {"id": 42, "status": "running"})
        manager._find_resource.assert_called_once_with(instance, JobWaitTransformMixin_v2, context)
