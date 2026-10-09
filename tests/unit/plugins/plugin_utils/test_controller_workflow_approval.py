# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for controller_workflow_approval module components.

Tests the Ansible dataclass, API dataclass, transform mixin, and registry
discovery for the controller_workflow_approval module.
"""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_workflow_approval import (  # noqa: E402
    AnsibleControllerWorkflowApproval,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_workflow_approval import (  # noqa: E402
    APIControllerWorkflowApproval_v2,
    ControllerWorkflowApprovalTransformMixin_v2,
)


class TestAnsibleControllerWorkflowApprovalDataclass(unittest.TestCase):
    """Tests for the stable Ansible-facing dataclass."""

    def test_defaults(self):
        model = AnsibleControllerWorkflowApproval()
        self.assertEqual(model.workflow_job_id, 0)
        self.assertEqual(model.name, "")
        self.assertEqual(model.action, "approve")
        self.assertEqual(model.interval, 1.0)
        self.assertEqual(model.timeout, 10)
        self.assertIsNone(model.id)

    def test_custom_values(self):
        model = AnsibleControllerWorkflowApproval(
            workflow_job_id=42,
            name="my_approval",
            action="deny",
            interval=5.0,
            timeout=60,
        )
        self.assertEqual(model.workflow_job_id, 42)
        self.assertEqual(model.name, "my_approval")
        self.assertEqual(model.action, "deny")
        self.assertEqual(model.interval, 5.0)
        self.assertEqual(model.timeout, 60)


class TestAPIControllerWorkflowApprovalDataclass(unittest.TestCase):
    """Tests for the API v2 dataclass."""

    def test_defaults(self):
        api = APIControllerWorkflowApproval_v2()
        self.assertIsNone(api.workflow_job_id)
        self.assertIsNone(api.name)
        self.assertIsNone(api.action)
        self.assertIsNone(api.interval)
        self.assertIsNone(api.timeout)
        self.assertIsNone(api.id)


class TestControllerWorkflowApprovalTransformMixin(unittest.TestCase):
    """Tests for the transform mixin."""

    def test_from_ansible_data(self):
        ansible_data = AnsibleControllerWorkflowApproval(
            workflow_job_id=99,
            name="approval_node",
            action="approve",
            interval=2.0,
            timeout=30,
        )
        context = {"operation": "find"}
        api_data = ControllerWorkflowApprovalTransformMixin_v2.from_ansible_data(ansible_data, context)
        self.assertEqual(api_data.workflow_job_id, 99)
        self.assertEqual(api_data.name, "approval_node")
        self.assertEqual(api_data.action, "approve")
        self.assertEqual(api_data.interval, 2.0)
        self.assertEqual(api_data.timeout, 30)

    def test_get_endpoint_operations_has_list_and_get(self):
        ops = ControllerWorkflowApprovalTransformMixin_v2.get_endpoint_operations()
        self.assertIn("list", ops)
        self.assertIn("get", ops)
        self.assertEqual(ops["list"].path, "/api/controller/v2/workflow_approvals/")
        self.assertEqual(ops["list"].method, "GET")
        self.assertEqual(ops["get"].path, "/api/controller/v2/workflow_approvals/{id}/")
        self.assertEqual(ops["get"].method, "GET")

    def test_get_lookup_field(self):
        self.assertEqual(ControllerWorkflowApprovalTransformMixin_v2.get_lookup_field(), "name")

    def test_from_api(self):
        api_response = {
            "id": 123,
            "name": "approval_node",
            "workflow_job_id": 42,
            "action": "deny",
        }
        context = {"operation": "find"}
        ansible_instance = ControllerWorkflowApprovalTransformMixin_v2.from_api(api_response, context)
        self.assertIsInstance(ansible_instance, AnsibleControllerWorkflowApproval)
        self.assertEqual(ansible_instance.id, 123)
        self.assertEqual(ansible_instance.name, "approval_node")
        self.assertEqual(ansible_instance.workflow_job_id, 42)


class TestRegistryDiscovery(unittest.TestCase):
    """Tests that the registry discovers the module under 'controller' service."""

    def test_module_is_discovered_under_controller_service(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry import (
            APIVersionRegistry,
        )

        registry = APIVersionRegistry()
        service = registry.get_service_for_module("controller_workflow_approval")
        self.assertEqual(service, "controller")

    def test_module_supports_version_2(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry import (
            APIVersionRegistry,
        )

        registry = APIVersionRegistry()
        self.assertTrue(registry.module_supports_version("controller_workflow_approval", "2"))

    def test_loader_can_load_classes(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.loader import (
            DynamicClassLoader,
        )
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry import (
            APIVersionRegistry,
        )

        registry = APIVersionRegistry()
        loader = DynamicClassLoader(registry)
        ansible_cls, api_cls, mixin_cls = loader.load_classes_for_module("controller_workflow_approval", "2")
        self.assertEqual(ansible_cls.__name__, "AnsibleControllerWorkflowApproval")
        self.assertEqual(api_cls.__name__, "APIControllerWorkflowApproval_v2")
        self.assertEqual(mixin_cls.__name__, "ControllerWorkflowApprovalTransformMixin_v2")


class TestModuleDocumentation(unittest.TestCase):
    """Tests that the module documentation is valid."""

    def test_documentation_is_parseable(self):
        import yaml
        from ansible_collections.ansible.platform.plugins.modules.controller_workflow_approval import (
            DOCUMENTATION,
        )

        doc = yaml.safe_load(DOCUMENTATION)
        self.assertEqual(doc["module"], "controller_workflow_approval")
        self.assertIn("workflow_job_id", doc["options"])
        self.assertIn("name", doc["options"])
        self.assertIn("action", doc["options"])
        self.assertIn("interval", doc["options"])
        self.assertIn("timeout", doc["options"])

    def test_action_choices(self):
        import yaml
        from ansible_collections.ansible.platform.plugins.modules.controller_workflow_approval import (
            DOCUMENTATION,
        )

        doc = yaml.safe_load(DOCUMENTATION)
        action_opt = doc["options"]["action"]
        self.assertEqual(action_opt["choices"], ["approve", "deny"])
        self.assertEqual(action_opt["default"], "approve")

    def test_extends_auth_fragment(self):
        import yaml
        from ansible_collections.ansible.platform.plugins.modules.controller_workflow_approval import (
            DOCUMENTATION,
        )

        doc = yaml.safe_load(DOCUMENTATION)
        fragments = doc.get("extends_documentation_fragment", [])
        self.assertIn("ansible.platform.auth", fragments)


if __name__ == "__main__":
    unittest.main()
