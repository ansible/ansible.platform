# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for workflow_job_template_node v2 transform mixin round-trips."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock

import pytest

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
        mock_manager.lookup_resource_id.assert_any_call("workflow_job_templates", "name", "My Workflow", service="controller", extra_query_params=None)
        self.assertEqual(api.workflow_job_template, 42)

    def test_ujt_name_resolves_via_manager(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 99
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleWorkflowJobTemplateNode(identifier="n1", workflow_job_template="1", unified_job_template="Demo Job Template")
        api = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call("unified_job_templates", "name", "Demo Job Template", service="controller", extra_query_params=None)
        self.assertEqual(api.unified_job_template, 99)

    def test_org_scoped_wfjt_lookup(self):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 42
        context = {"operation": "create", "manager": mock_manager}
        ansible = AnsibleWorkflowJobTemplateNode(identifier="n1", workflow_job_template="My Workflow", organization="My Org")
        WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(ansible, context)
        mock_manager.lookup_resource_id.assert_any_call(
            "workflow_job_templates", "name", "My Workflow", service="controller", extra_query_params={"organization": 42}
        )

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
            "scm_branch": "",
            "limit": "",
        }
        ansible = WorkflowJobTemplateNodeTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(ansible, AnsibleWorkflowJobTemplateNode)
        self.assertEqual(ansible.id, 77)
        self.assertEqual(ansible.identifier, "node_101")
        self.assertEqual(ansible.workflow_job_template, "5")
        self.assertEqual(ansible.unified_job_template, "10")
        self.assertIs(ansible.all_parents_must_converge, False)
        self.assertEqual(ansible.scm_branch, "")
        self.assertEqual(ansible.limit, "")

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

    def test_find_list_query_params_scope_to_workflow_when_present(self):
        ansible = AnsibleWorkflowJobTemplateNode(identifier="n1", workflow_job_template="42")
        api = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(ansible, {"operation": "find"})

        self.assertEqual(
            WorkflowJobTemplateNodeTransformMixin_v2.get_find_list_query_params(api),
            {"workflow_job_template": 42},
        )

    def test_find_list_query_params_are_empty_without_workflow(self):
        ansible = AnsibleWorkflowJobTemplateNode(identifier="n1", workflow_job_template=None)
        api = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(ansible, {"operation": "find"})

        self.assertEqual(WorkflowJobTemplateNodeTransformMixin_v2.get_find_list_query_params(api), {})

    def test_id_passthrough_for_update(self):
        ansible = AnsibleWorkflowJobTemplateNode(identifier="n1", workflow_job_template="1", id=99)
        api = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.id, 99)

    def test_fields_to_null_for_update_only_clears_associations_when_enforced(self):
        api = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(
            AnsibleWorkflowJobTemplateNode(identifier="n1", workflow_job_template="1"), {"operation": "update"}
        )
        expected = frozenset({"inventory", "execution_environment"})

        self.assertEqual(WorkflowJobTemplateNodeTransformMixin_v2.get_fields_to_null_for_update(api), frozenset())
        self.assertEqual(WorkflowJobTemplateNodeTransformMixin_v2.get_fields_to_null_for_update(api, context={}), frozenset())
        self.assertEqual(
            WorkflowJobTemplateNodeTransformMixin_v2.get_fields_to_null_for_update(api, context={"include_nulls_for_update": True}),
            expected,
        )

    def test_from_api_resolves_fk_names_from_summary_fields(self):
        api_data = {
            "id": 77,
            "identifier": "node_101",
            "workflow_job_template": 5,
            "unified_job_template": 10,
            "inventory": 3,
            "execution_environment": 7,
            "all_parents_must_converge": False,
            "summary_fields": {
                "workflow_job_template": {"id": 5, "name": "My Workflow"},
                "unified_job_template": {"id": 10, "name": "Demo Job Template", "unified_job_type": "job"},
                "inventory": {"id": 3, "name": "Demo Inventory"},
                "execution_environment": {"id": 7, "name": "Default EE"},
            },
        }
        ansible = WorkflowJobTemplateNodeTransformMixin_v2.from_api(api_data, {})
        self.assertEqual(ansible.workflow_job_template, "My Workflow")
        self.assertEqual(ansible.unified_job_template, "Demo Job Template")
        self.assertEqual(ansible.inventory, "Demo Inventory")
        self.assertEqual(ansible.execution_environment, "Default EE")

    def test_idempotency_uses_returned_api_fk_ids_without_name_lookup(self):
        manager = MagicMock()
        context = {"manager": manager}
        api_data = {
            "identifier": "node_101",
            "workflow_job_template": 5,
            "unified_job_template": 10,
            "summary_fields": {
                "workflow_job_template": {"id": 5, "name": "My Workflow"},
                "unified_job_template": {"id": 10, "name": "Demo Job Template"},
            },
        }

        current = asdict(WorkflowJobTemplateNodeTransformMixin_v2.from_api(api_data, context))

        self.assertEqual(
            WorkflowJobTemplateNodeTransformMixin_v2.get_idempotency_value_from_current_data("workflow_job_template", current, context),
            5,
        )
        self.assertEqual(
            WorkflowJobTemplateNodeTransformMixin_v2.get_idempotency_value_from_current_data("unified_job_template", current, context),
            10,
        )
        manager.lookup_resource_id.assert_not_called()

    def test_from_api_falls_back_to_manager_when_no_summary_fields(self):
        mock_manager = MagicMock()

        def _search_api(url):
            lookup = {
                "/api/controller/v2/workflow_job_templates/5/": {"id": 5, "name": "My Workflow"},
                "/api/controller/v2/inventories/3/": {"id": 3, "name": "Demo Inventory"},
            }
            return lookup.get(url, {})

        mock_manager.search_api.side_effect = _search_api

        api_data = {
            "identifier": "n1",
            "workflow_job_template": 5,
            "inventory": 3,
        }
        ansible = WorkflowJobTemplateNodeTransformMixin_v2.from_api(api_data, {"manager": mock_manager})
        self.assertEqual(ansible.workflow_job_template, "My Workflow")
        self.assertEqual(ansible.inventory, "Demo Inventory")

    def test_from_api_falls_back_to_string_id_without_manager(self):
        api_data = {
            "identifier": "n1",
            "workflow_job_template": 5,
            "unified_job_template": 10,
            "inventory": 3,
        }
        ansible = WorkflowJobTemplateNodeTransformMixin_v2.from_api(api_data, {})
        self.assertEqual(ansible.workflow_job_template, "5")
        self.assertEqual(ansible.unified_job_template, "10")
        self.assertEqual(ansible.inventory, "3")

    def test_get_update_value_blocks_fk_name_merge(self):
        current = {"workflow_job_template": "My Workflow", "unified_job_template": "Demo JT", "all_parents_must_converge": True}
        self.assertIsNone(WorkflowJobTemplateNodeTransformMixin_v2.get_update_value_from_current_data("workflow_job_template", current))
        self.assertIsNone(WorkflowJobTemplateNodeTransformMixin_v2.get_update_value_from_current_data("unified_job_template", current))
        self.assertTrue(WorkflowJobTemplateNodeTransformMixin_v2.get_update_value_from_current_data("all_parents_must_converge", current))

    def test_get_update_value_allows_fk_id_merge(self):
        current = {"workflow_job_template": "42", "unified_job_template": "10"}
        self.assertEqual(WorkflowJobTemplateNodeTransformMixin_v2.get_update_value_from_current_data("workflow_job_template", current), "42")
        self.assertEqual(WorkflowJobTemplateNodeTransformMixin_v2.get_update_value_from_current_data("unified_job_template", current), "10")

    def test_from_api_falls_back_on_api_error(self):
        mock_manager = MagicMock()
        mock_manager.search_api.side_effect = ValueError("Not found")

        api_data = {
            "identifier": "n1",
            "workflow_job_template": 999,
        }
        ansible = WorkflowJobTemplateNodeTransformMixin_v2.from_api(api_data, {"manager": mock_manager})
        self.assertEqual(ansible.workflow_job_template, "999")


def test_node_parent_and_target_use_independent_organization_scopes():
    """Resolve a target outside its parent workflow's organization."""
    manager = MagicMock()
    manager.lookup_resource_id.side_effect = [10, 20, 30, 40]
    model = AnsibleWorkflowJobTemplateNode(
        identifier="leaf", workflow_job_template="Parent", organization="Parent Org", unified_job_template="Job", lookup_organization="Job Org"
    )
    result = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(model, {"manager": manager, "operation": "create"})
    assert {"workflow_job_template": result.workflow_job_template, "unified_job_template": result.unified_job_template} == {
        "workflow_job_template": 20,
        "unified_job_template": 40,
    }
    manager.lookup_resource_id.assert_any_call("workflow_job_templates", "name", "Parent", service="controller", extra_query_params={"organization": 10})
    manager.lookup_resource_id.assert_any_call("unified_job_templates", "name", "Job", service="controller", extra_query_params={"organization": 30})


@pytest.mark.parametrize("operation", ["find", "delete"])
def test_node_lookup_ignores_unused_launch_references(operation):
    """Find and delete nodes without resolving unused update fields."""
    manager = MagicMock()
    model = AnsibleWorkflowJobTemplateNode(
        identifier="leaf", workflow_job_template="3", unified_job_template="Missing", inventory="Missing", execution_environment="Missing"
    )
    result = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(model, {"manager": manager, "operation": operation})
    assert result.workflow_job_template == 3
    manager.lookup_resource_id.assert_not_called()


def test_node_preserves_explicit_execution_environment_clear():
    """Send an explicit empty relationship value without looking up an empty name."""
    manager = MagicMock()
    model = AnsibleWorkflowJobTemplateNode(identifier="leaf", workflow_job_template="3", execution_environment="")
    result = WorkflowJobTemplateNodeTransformMixin_v2.from_ansible_data(model, {"manager": manager, "operation": "update"})
    assert result.execution_environment == ""
    manager.lookup_resource_id.assert_not_called()


if __name__ == "__main__":
    unittest.main()
