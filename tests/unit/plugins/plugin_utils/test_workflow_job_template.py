# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for workflow_job_template v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.workflow_job_template import (  # noqa: E402
    AnsibleWorkflowJobTemplate,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.workflow_job_template import (  # noqa: E402
    WorkflowJobTemplateTransformMixin_v2,
)


class TestWorkflowJobTemplateTransform(unittest.TestCase):
    """Ansible <-> API round-trip tests for workflow_job_template."""

    def test_post_init_normalizes_extra_vars_dict(self):
        ansible = AnsibleWorkflowJobTemplate(name="wf", extra_vars={"foo": "bar"})
        self.assertIsInstance(ansible.extra_vars, str)
        self.assertEqual(json.loads(ansible.extra_vars), {"foo": "bar"})

    def test_post_init_preserves_extra_vars_string(self):
        ansible = AnsibleWorkflowJobTemplate(name="wf", extra_vars='{"foo": "bar"}')
        self.assertEqual(ansible.extra_vars, '{"foo": "bar"}')

    def test_create_includes_all_fields(self):
        ansible = AnsibleWorkflowJobTemplate(
            name="My Workflow",
            description="Test",
            organization="1",
            survey_enabled=True,
            allow_simultaneous=False,
            ask_variables_on_launch=True,
        )
        api = WorkflowJobTemplateTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "My Workflow")
        self.assertEqual(api.description, "Test")
        self.assertEqual(api.organization, 1)
        self.assertIs(api.survey_enabled, True)
        self.assertIs(api.allow_simultaneous, False)
        self.assertIs(api.ask_variables_on_launch, True)

    def test_create_omits_unset_fields(self):
        ansible = AnsibleWorkflowJobTemplate(name="minimal")
        api = WorkflowJobTemplateTransformMixin_v2.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "minimal")
        self.assertIsNone(api.description)
        self.assertIsNone(api.organization)
        self.assertIsNone(api.extra_vars)

    def test_org_fk_uses_default_service(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 42
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleWorkflowJobTemplate(name="wf", organization="Default")
        api = WorkflowJobTemplateTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("organizations", "name", "Default")
        self.assertEqual(api.organization, 42)

    def test_inventory_fk_uses_controller_service(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 10
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleWorkflowJobTemplate(name="wf", inventory="Prod")
        WorkflowJobTemplateTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("inventories", "name", "Prod", service="controller")

    def test_webhook_credential_fk_uses_controller_service(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 5
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleWorkflowJobTemplate(name="wf", webhook_credential="GH Token")
        WorkflowJobTemplateTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("credentials", "name", "GH Token", service="controller")

    def test_update_with_new_name(self):
        ansible = AnsibleWorkflowJobTemplate(name="old", new_name="new")
        api = WorkflowJobTemplateTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "new")

    def test_update_without_new_name_echoes(self):
        ansible = AnsibleWorkflowJobTemplate(name="keep")
        api = WorkflowJobTemplateTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "keep")

    def test_from_api_returns_ansible_instance(self):
        api_data = {
            "id": 99,
            "name": "My Workflow",
            "description": "Test",
            "organization": 5,
            "extra_vars": '{"key": "val"}',
            "survey_enabled": True,
            "allow_simultaneous": False,
            "inventory": 10,
            "webhook_credential": None,
        }
        ansible = WorkflowJobTemplateTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleWorkflowJobTemplate)
        self.assertEqual(ansible.id, 99)
        self.assertEqual(ansible.name, "My Workflow")
        self.assertEqual(ansible.organization, "5")
        self.assertEqual(ansible.inventory, "10")
        self.assertEqual(ansible.extra_vars, '{"key": "val"}')

    def test_from_api_handles_missing_fields(self):
        ansible = WorkflowJobTemplateTransformMixin_v2.from_api({"name": "bare"}, {})
        self.assertEqual(ansible.name, "bare")
        self.assertIsNone(ansible.description)
        self.assertIsNone(ansible.organization)
        self.assertIsNone(ansible.id)

    def test_endpoint_operations_use_controller_paths(self):
        ops = WorkflowJobTemplateTransformMixin_v2.get_endpoint_operations()
        for op_name, op in ops.items():
            self.assertTrue(
                op.path.startswith("/api/controller/v2/workflow_job_templates"),
                f"{op_name} path should start with /api/controller/v2/workflow_job_templates, got {op.path}",
            )

    def test_lookup_field_is_name(self):
        self.assertEqual(WorkflowJobTemplateTransformMixin_v2.get_lookup_field(), "name")

    def test_id_passthrough_for_update(self):
        ansible = AnsibleWorkflowJobTemplate(name="wf", id=99)
        api = WorkflowJobTemplateTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 99)


if __name__ == "__main__":
    unittest.main()
