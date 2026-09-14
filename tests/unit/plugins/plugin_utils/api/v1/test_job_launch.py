# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the job_launch v1 transform mixin (AAP-91390)."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.job_launch import (  # noqa: E402
    AnsibleJobLaunch,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.job_launch import (  # noqa: E402
    JobLaunchTransformMixin_v1,
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


class TestJobLaunchTransform(unittest.TestCase):
    def test_from_ansible_data_resolves_job_template_via_unified_job_templates(self):
        ansible = AnsibleJobLaunch(name="Demo Job Template")
        context = _make_context(lookup_returns={("/api/controller/v2/unified_job_templates/", "Demo Job Template"): 9})

        api = JobLaunchTransformMixin_v1.from_ansible_data(ansible, context)

        context.manager.lookup_resource_id.assert_called_once_with("/api/controller/v2/unified_job_templates/", "name", "Demo Job Template")
        self.assertEqual(api.job_template_id, 9)

    def test_from_ansible_data_reuses_id_when_already_set(self):
        """Second call, during a wait poll, must skip the job_template lookup and just target {id}."""
        ansible = AnsibleJobLaunch(name="Demo Job Template", id=55)
        context = _make_context()

        api = JobLaunchTransformMixin_v1.from_ansible_data(ansible, context)

        context.manager.lookup_resource_id.assert_not_called()
        self.assertEqual(api.id, 55)
        self.assertIsNone(api.job_template_id)

    def test_from_ansible_data_resolves_fk_lists(self):
        ansible = AnsibleJobLaunch(
            name="Demo Job Template",
            credentials=["Demo Credential", "Second Credential"],
            labels=["Demo Label"],
            instance_groups=["Demo IG"],
        )
        lookups = {
            ("/api/controller/v2/unified_job_templates/", "Demo Job Template"): 9,
            ("/api/controller/v2/credentials/", "Demo Credential"): 20,
            ("/api/controller/v2/credentials/", "Second Credential"): 21,
            ("/api/controller/v2/labels/", "Demo Label"): 30,
            ("/api/controller/v2/instance_groups/", "Demo IG"): 40,
        }
        context = _make_context(lookup_returns=lookups)

        api = JobLaunchTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.credentials, [20, 21])
        self.assertEqual(api.labels, [30])
        self.assertEqual(api.instance_groups, [40])

    def test_from_ansible_data_converts_tag_lists_to_comma_strings(self):
        ansible = AnsibleJobLaunch(name="Demo Job Template", tags=["a", "b"], skip_tags=["c"])
        context = _make_context()

        api = JobLaunchTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.job_tags, "a,b")
        self.assertEqual(api.skip_tags, "c")

    def test_from_ansible_data_renames_job_timeout_to_timeout(self):
        ansible = AnsibleJobLaunch(name="Demo Job Template", job_timeout=600)
        context = _make_context()

        api = JobLaunchTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.timeout, 600)

    def test_from_ansible_data_raises_when_job_template_not_found(self):
        ansible = AnsibleJobLaunch(name="Missing Template")
        context = _make_context(default=None)

        with self.assertRaises(ValueError):
            JobLaunchTransformMixin_v1.from_ansible_data(ansible, context)

    def test_from_api_maps_launch_response(self):
        ansible = JobLaunchTransformMixin_v1.from_api(
            {"id": 86, "name": "Demo Job Template", "inventory": 5, "status": "pending"},
            _make_context(),
        )

        self.assertEqual(ansible.id, 86)
        self.assertEqual(ansible.status, "pending")
        self.assertEqual(ansible.inventory, "5")

    def test_get_endpoint_operations_target_launch_and_jobs_paths(self):
        ops = JobLaunchTransformMixin_v1.get_endpoint_operations()
        self.assertEqual(ops["create"].path, "/api/controller/v2/job_templates/{job_template_id}/launch/")
        self.assertEqual(ops["get"].path, "/api/controller/v2/jobs/{id}/")
        self.assertNotIn("list", ops)


if __name__ == "__main__":
    unittest.main()
