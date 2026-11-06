from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.action.workflow_job_template_node import ActionModule

__metaclass__ = type


class TestWorkflowNodeIdentifierResolution(unittest.TestCase):
    def test_resolves_identifiers_in_one_workflow_scoped_batch(self):
        manager = MagicMock()
        manager.lookup_resource_ids.return_value = {"123": 30, "child": 31}

        result = ActionModule._resolve_node_ids_in_workflow(manager, 77, ["123", "child", "123"])

        self.assertEqual(result, [30, 31, 30])
        manager.lookup_resource_ids.assert_called_once_with(
            "workflow_job_template_nodes",
            "identifier",
            ["123", "child", "123"],
            service="controller",
            extra_query_params={"workflow_job_template": 77},
            numeric_is_id=False,
            allow_missing=True,
        )

    def test_preserves_missing_identifier_error_with_workflow_scope(self):
        manager = MagicMock()
        manager.lookup_resource_ids.return_value = {"present": 30}

        with self.assertRaisesRegex(ValueError, "Workflow node with identifier 'missing' not found in workflow 77"):
            ActionModule._resolve_node_ids_in_workflow(manager, 77, ["present", "missing"])


if __name__ == "__main__":
    unittest.main()
