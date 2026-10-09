# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for workflow_job_template_node v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.workflow_job_template_node import (  # noqa: E402
    AnsibleWorkflowJobTemplateNode,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.workflow_job_template_node import (  # noqa: E402
    WorkflowJobTemplateNodeTransformMixin_v2,
)


class TestWorkflowJobTemplateNodeTransform(unittest.TestCase):
    """Ansible <-> API round-trip tests for workflow_job_template_node."""

    def test_create_includes_all_fields(self):
        ansible = AnsibleWorkflowJobTemplateNode(
            identifier="node_101",
            workflow_job_template="5",
            unified_job_template="10",
            all_parents_must_converge=True,
        )
        api = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.identifier, "node_101")
        self.assertEqual(api.workflow_job_template, 5)
        self.assertEqual(api.unified_job_template, 10)
        self.assertIs(api.all_parents_must_converge, True)

    def test_create_omits_unset_fields(self):
        ansible = AnsibleWorkflowJobTemplateNode(identifier="node_1", workflow_job_template="1")
        api = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.identifier, "node_1")
        self.assertEqual(api.workflow_job_template, 1)
        self.assertIsNone(api.unified_job_template)
        self.assertIsNone(api.all_parents_must_converge)

    def test_wfjt_name_resolves_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 42
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleWorkflowJobTemplateNode(identifier="n1", workflow_job_template="My Workflow")
        api = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("workflow_job_templates", "name", "My Workflow", service="controller")
        self.assertEqual(api.workflow_job_template, 42)

    def test_ujt_name_resolves_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 99
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleWorkflowJobTemplateNode(identifier="n1", workflow_job_template="1", unified_job_template="Demo Job Template")
        api = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("unified_job_templates", "name", "Demo Job Template", service="controller")
        self.assertEqual(api.unified_job_template, 99)

    def test_wfjt_id_skips_lookup(self):
        ansible = AnsibleWorkflowJobTemplateNode(identifier="n1", workflow_job_template="42")
        api = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.workflow_job_template, 42)

    def test_from_api_returns_ansible_instance(self):
        api_data = {
            "id": 77,
            "identifier": "node_101",
            "workflow_job_template": 5,
            "unified_job_template": 10,
            "all_parents_must_converge": False,
        }
        ansible = WorkflowJobTemplateNodeTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleWorkflowJobTemplateNode)
        self.assertEqual(ansible.id, 77)
        self.assertEqual(ansible.identifier, "node_101")
        self.assertEqual(ansible.workflow_job_template, "5")
        self.assertEqual(ansible.unified_job_template, "10")
        self.assertIs(ansible.all_parents_must_converge, False)

    def test_from_api_handles_missing_fields(self):
        ansible = WorkflowJobTemplateNodeTransformMixin_v2.from_api({"identifier": "n1", "workflow_job_template": 1}, {})
        self.assertEqual(ansible.identifier, "n1")
        self.assertIsNone(ansible.unified_job_template)
        self.assertIsNone(ansible.all_parents_must_converge)
        self.assertIsNone(ansible.id)

    def test_endpoint_operations_use_controller_paths(self):
        ops = WorkflowJobTemplateNodeTransformMixin_v2.get_endpoint_operations()
        for op_name, op in ops.items():
            self.assertTrue(
                op.path.startswith("/api/controller/v2/workflow_job_template_nodes"),
                f"{op_name} path should start with /api/controller/v2/workflow_job_template_nodes, got {op.path}",
            )

    def test_lookup_field_is_identifier(self):
        self.assertEqual(WorkflowJobTemplateNodeTransformMixin_v2.get_lookup_field(), "identifier")

    def test_id_passthrough_for_update(self):
        ansible = AnsibleWorkflowJobTemplateNode(identifier="n1", workflow_job_template="1", id=99)
        api = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 99)


if __name__ == "__main__":
    unittest.main()
