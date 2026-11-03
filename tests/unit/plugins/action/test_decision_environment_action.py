# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the decision_environment action plugin."""

import unittest
from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.decision_environment import ActionModule


class TestDecisionEnvironmentAction(unittest.TestCase):
    """Test decision_environment action plugin CRUD behavior."""

    def _make_action(self, check_mode=False):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.check_mode = check_mode
        action._task.args = {}
        action._task.environment = []
        action._display = MagicMock()
        action._display.verbosity = 0
        action._connection = MagicMock()
        action._templar = MagicMock()
        return action

    def _make_manager(self, find_result=None, create_result=None, update_result=None, delete_error=None):
        manager = MagicMock()

        def execute_side_effect(operation, module_name, ansible_data):
            if operation == "find":
                if find_result:
                    return find_result
                raise ValueError("Not found")
            if operation == "delete":
                if delete_error:
                    raise delete_error
                return {}
            if operation == "create":
                return create_result or {"id": 100, "name": ansible_data.get("name", ""), "changed": True}
            if operation == "update":
                return update_result or {"id": find_result.get("id", 100) if find_result else 100, "changed": True, **ansible_data}
            return {}

        manager.execute.side_effect = execute_side_effect
        return manager

    def _run_action(self, action, manager, task_args):
        action._task.args = task_args.copy()

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                return action.run(task_vars={})

    def test_create_new_decision_environment(self):
        """Create decision environment when none exists."""
        action = self._make_action()
        manager = self._make_manager(
            find_result=None,
            create_result={
                "id": 100,
                "name": "test-de",
                "description": "test",
                "image_url": "quay.io/test",
                "pull_policy": "always",
                "changed": True,
            },
        )
        result = self._run_action(
            action,
            manager,
            {
                "name": "test-de",
                "description": "test",
                "image_url": "quay.io/test",
                "pull_policy": "always",
                "state": "present",
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        self.assertEqual(result["id"], 100)

    def test_update_existing_decision_environment(self):
        """Update decision environment when it exists and fields differ."""
        action = self._make_action()
        manager = self._make_manager(
            find_result={
                "id": 100,
                "name": "test-de",
                "description": "old desc",
                "image_url": "quay.io/old",
                "pull_policy": "always",
            },
            update_result={
                "id": 100,
                "name": "test-de",
                "description": "new desc",
                "image_url": "quay.io/new",
                "pull_policy": "always",
                "changed": True,
            },
        )
        result = self._run_action(
            action,
            manager,
            {
                "name": "test-de",
                "description": "new desc",
                "image_url": "quay.io/new",
                "pull_policy": "always",
                "state": "present",
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])

    def test_idempotent_no_change(self):
        """No update when all fields match (idempotency)."""
        action = self._make_action()
        manager = self._make_manager(
            find_result={
                "id": 100,
                "name": "test-de",
                "description": "test",
                "image_url": "quay.io/test",
                "pull_policy": "always",
            },
        )
        result = self._run_action(
            action,
            manager,
            {
                "name": "test-de",
                "description": "test",
                "image_url": "quay.io/test",
                "pull_policy": "always",
                "state": "present",
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])

    def test_delete_existing(self):
        """Delete decision environment when it exists."""
        action = self._make_action()
        manager = self._make_manager(
            find_result={"id": 100, "name": "test-de"},
        )
        result = self._run_action(
            action,
            manager,
            {
                "name": "test-de",
                "state": "absent",
            },
        )

        self.assertFalse(result.get("failed", False))

    def test_delete_nonexistent(self):
        """No-op when deleting decision environment that does not exist."""
        action = self._make_action()
        manager = self._make_manager(find_result=None)
        result = self._run_action(
            action,
            manager,
            {
                "name": "ghost-de",
                "state": "absent",
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])
        self.assertIn("already absent", result["msg"])

    def test_check_mode_present(self):
        """Check mode reports changed without calling API for mutations."""
        action = self._make_action(check_mode=True)
        manager = self._make_manager(find_result=None)
        result = self._run_action(
            action,
            manager,
            {
                "name": "test-de",
                "image_url": "quay.io/test",
                "state": "present",
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])

    def test_check_mode_absent_existing(self):
        """Check mode for absent with existing decision environment."""
        action = self._make_action(check_mode=True)
        manager = self._make_manager(
            find_result={"id": 100, "name": "test-de"},
        )
        result = self._run_action(
            action,
            manager,
            {
                "name": "test-de",
                "state": "absent",
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])

    def test_rename_with_new_name(self):
        """Rename via new_name triggers update."""
        action = self._make_action()
        manager = self._make_manager(
            find_result={
                "id": 100,
                "name": "old-name",
                "image_url": "quay.io/test",
                "pull_policy": "always",
            },
            update_result={
                "id": 100,
                "name": "new-name",
                "image_url": "quay.io/test",
                "pull_policy": "always",
                "changed": True,
            },
        )
        result = self._run_action(
            action,
            manager,
            {
                "name": "old-name",
                "new_name": "new-name",
                "image_url": "quay.io/test",
                "state": "present",
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])


class TestDecisionEnvironmentModel(unittest.TestCase):
    """Test the Ansible dataclass for decision_environment."""

    def test_dataclass_defaults(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.decision_environment import AnsibleDecisionEnvironment

        de = AnsibleDecisionEnvironment(name="test")
        self.assertEqual(de.name, "test")
        self.assertIsNone(de.new_name)
        self.assertIsNone(de.description)
        self.assertIsNone(de.image_url)
        self.assertIsNone(de.credential)
        self.assertIsNone(de.pull_policy)
        self.assertIsNone(de.organization_name)
        self.assertEqual(de.state, "present")
        self.assertIsNone(de.id)

    def test_dataclass_full(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.decision_environment import AnsibleDecisionEnvironment

        de = AnsibleDecisionEnvironment(
            name="test",
            description="desc",
            image_url="quay.io/test",
            credential="my-cred",
            pull_policy="missing",
            organization_name="Default",
            state="present",
            id=42,
        )
        self.assertEqual(de.image_url, "quay.io/test")
        self.assertEqual(de.credential, "my-cred")
        self.assertEqual(de.pull_policy, "missing")
        self.assertEqual(de.organization_name, "Default")


class TestDecisionEnvironmentTransform(unittest.TestCase):
    """Test the transform mixin for decision_environment."""

    def test_from_api(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.decision_environment import DecisionEnvironmentTransformMixin_v1

        api_data = {
            "id": 42,
            "name": "test-de",
            "description": "test desc",
            "image_url": "quay.io/test",
            "pull_policy": "always",
            "eda_credential_id": 10,
            "organization_id": 5,
        }
        result = DecisionEnvironmentTransformMixin_v1.from_api(api_data, {})
        self.assertEqual(result.name, "test-de")
        self.assertEqual(result.id, 42)
        self.assertEqual(result.credential, "10")
        self.assertEqual(result.organization_name, "5")
        self.assertEqual(result.image_url, "quay.io/test")
        self.assertEqual(result.pull_policy, "always")

    def test_from_api_null_fks(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.decision_environment import DecisionEnvironmentTransformMixin_v1

        api_data = {
            "id": 42,
            "name": "test-de",
            "eda_credential_id": None,
            "organization_id": None,
        }
        result = DecisionEnvironmentTransformMixin_v1.from_api(api_data, {})
        self.assertIsNone(result.credential)
        self.assertIsNone(result.organization_name)

    def test_from_ansible_data_create(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.decision_environment import AnsibleDecisionEnvironment
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.decision_environment import DecisionEnvironmentTransformMixin_v1

        ansible_obj = AnsibleDecisionEnvironment(
            name="test-de",
            description="test",
            image_url="quay.io/test",
            pull_policy="always",
        )
        context = {"operation": "create", "manager": None}
        result = DecisionEnvironmentTransformMixin_v1.from_ansible_data(ansible_obj, context)
        self.assertEqual(result.name, "test-de")
        self.assertEqual(result.image_url, "quay.io/test")
        self.assertEqual(result.pull_policy, "always")

    def test_from_ansible_data_with_numeric_credential(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.decision_environment import AnsibleDecisionEnvironment
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.decision_environment import DecisionEnvironmentTransformMixin_v1

        ansible_obj = AnsibleDecisionEnvironment(
            name="test-de",
            credential="42",
            organization_name="5",
        )
        context = {"operation": "create", "manager": None}
        result = DecisionEnvironmentTransformMixin_v1.from_ansible_data(ansible_obj, context)
        self.assertEqual(result.eda_credential_id, 42)
        self.assertEqual(result.organization_id, 5)

    def test_get_lookup_field(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.decision_environment import DecisionEnvironmentTransformMixin_v1

        self.assertEqual(DecisionEnvironmentTransformMixin_v1.get_lookup_field(), "name")

    def test_get_endpoint_operations(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.decision_environment import DecisionEnvironmentTransformMixin_v1

        ops = DecisionEnvironmentTransformMixin_v1.get_endpoint_operations()
        self.assertIn("create", ops)
        self.assertIn("update", ops)
        self.assertIn("delete", ops)
        self.assertIn("get", ops)
        self.assertIn("list", ops)
        self.assertEqual(ops["create"].path, "/api/eda/v1/decision-environments/")
        self.assertEqual(ops["create"].method, "POST")
        self.assertEqual(ops["update"].method, "PATCH")
        self.assertEqual(ops["delete"].method, "DELETE")


if __name__ == "__main__":
    unittest.main()
