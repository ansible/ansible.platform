# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the workflow_job_template v1 transform mixin (AAP-91391)."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.workflow_job_template import (  # noqa: E402
    AnsibleWorkflowJobTemplate,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.workflow_job_template import (  # noqa: E402
    APIWorkflowJobTemplate_v1,
    WorkflowJobTemplateTransformMixin_v1,
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


class TestWorkflowJobTemplateTransform(unittest.TestCase):
    def test_from_ansible_data_resolves_fk_fields(self):
        ansible = AnsibleWorkflowJobTemplate(
            name="wfjt",
            organization="Default",
            inventory="Demo Inventory",
            webhook_credential="Some Cred",
        )
        lookups = {
            ("/api/controller/v2/organizations/", "Default"): 10,
            ("/api/controller/v2/inventories/", "Demo Inventory"): 20,
            ("/api/controller/v2/credentials/", "Some Cred"): 30,
        }
        context = _make_context(lookup_returns=lookups)

        api = WorkflowJobTemplateTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.organization, 10)
        self.assertEqual(api.inventory, 20)
        self.assertEqual(api.webhook_credential, 30)

    def test_from_ansible_data_uses_new_name_when_set(self):
        ansible = AnsibleWorkflowJobTemplate(name="old", new_name="new")
        context = _make_context()

        api = WorkflowJobTemplateTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.name, "new")

    def test_from_ansible_data_serializes_extra_vars_dict_to_json(self):
        ansible = AnsibleWorkflowJobTemplate(name="wfjt", extra_vars={"foo": "bar"})
        context = _make_context()

        api = WorkflowJobTemplateTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.extra_vars, '{"foo": "bar"}')

    def test_from_api_maps_fields_and_parses_extra_vars(self):
        ansible = WorkflowJobTemplateTransformMixin_v1.from_api(
            {"id": 1, "name": "wfjt", "organization": 10, "inventory": 20, "extra_vars": '{"foo": "bar"}'},
            _make_context(),
        )

        self.assertEqual(ansible.organization, "10")
        self.assertEqual(ansible.inventory, "20")
        self.assertEqual(ansible.extra_vars, {"foo": "bar"})

    def test_get_endpoint_operations_use_controller_paths(self):
        ops = WorkflowJobTemplateTransformMixin_v1.get_endpoint_operations()
        for op_name in ("create", "list"):
            self.assertTrue(ops[op_name].path.startswith("/api/controller/v2/workflow_job_templates"))

    def test_get_find_list_query_params_scopes_by_organization(self):
        api_data = APIWorkflowJobTemplate_v1(name="wfjt", organization=10)
        params = WorkflowJobTemplateTransformMixin_v1.get_find_list_query_params(api_data)
        self.assertEqual(params, {"organization": 10})


if __name__ == "__main__":
    unittest.main()
