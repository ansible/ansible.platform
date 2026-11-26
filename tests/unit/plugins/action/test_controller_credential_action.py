# (c) 2026 Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for controller credential secret-update idempotency."""

from __future__ import absolute_import, division, print_function

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.action.controller_credential import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.api.gateway.v1.team import TeamTransformMixin_v1


class TestControllerCredentialSecretUpdates(unittest.TestCase):
    def _make_action(self, update_secrets, manager=None):
        action = ActionModule.__new__(ActionModule)
        action._task = SimpleNamespace(args={"update_secrets": update_secrets})
        action._client = manager
        return action

    def test_update_secrets_is_an_ansible_directive(self):
        self.assertIn("update_secrets", ActionModule._ANSIBLE_DIRECTIVES)

    def test_gateway_team_id_resolves_linked_controller_team(self):
        action = ActionModule.__new__(ActionModule)
        manager = MagicMock()
        manager.search_api.return_value = {"summary_fields": {"resource": {"ansible_id": "team-uuid"}}}
        manager.lookup_resource_id.return_value = 31
        prepared = {
            "validated_params": {"name": "credential", "gateway_team_id": 17},
            "resource_data": {"name": "credential", "credential_type": "1"},
            "write_only_data": {"gateway_team_id": 17},
            "manager": manager,
        }

        with patch.object(BaseResourceActionPlugin, "_prepare_action", return_value=prepared):
            result = action._prepare_action()

        self.assertEqual(result["resource_data"]["team"], "31")
        self.assertNotIn("gateway_team_id", result["resource_data"])
        manager.search_api.assert_called_once_with(
            TeamTransformMixin_v1.get_endpoint_operations()["get"].path.format(id=17),
            service="gateway",
        )
        manager.lookup_resource_id.assert_called_once_with(
            "teams",
            "resource__ansible_id",
            "team-uuid",
            service="controller",
            require_unique=True,
            numeric_is_id=False,
        )

    def test_gateway_team_id_is_mutually_exclusive_with_other_owners(self):
        self.assertEqual(ActionModule._MUTUALLY_EXCLUSIVE, [["organization", "user", "team", "gateway_team_id"]])

    def test_update_secrets_false_resolves_relationship_names_before_comparison(self):
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = [7, 1]
        action = self._make_action(False, manager)
        desired = {"name": "credential", "credential_type": "Machine", "organization": "Default"}
        current = {"name": "credential", "credential_type": 7, "organization": 1}

        self.assertFalse(action._should_update(desired, current))
        manager.lookup_resource_id.assert_any_call("credential_types", "name", "Machine", service="controller")
        manager.lookup_resource_id.assert_any_call("organizations", "name", "Default", service="controller")

    def test_update_secrets_false_detects_different_relationship(self):
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = [7, 9]
        action = self._make_action(False, manager)
        desired = {"name": "credential", "credential_type": "Machine", "organization": "Other"}
        current = {"name": "credential", "credential_type": 7, "organization": 1}

        self.assertTrue(action._should_update(desired, current))

    def test_update_secrets_false_omits_inputs_on_update(self):
        action = self._make_action(False)
        ansible_data = {"name": "credential"}

        action._pre_execute_hook(ansible_data, {"inputs": {"username": "new-user"}}, {"update_secrets": False}, "update")

        self.assertNotIn("inputs", ansible_data)

    def test_update_secrets_false_preserves_inputs_on_create(self):
        action = self._make_action(False)
        ansible_data = {"name": "credential"}
        inputs = {"username": "new-user"}

        action._pre_execute_hook(ansible_data, {"inputs": inputs}, {"update_secrets": False}, "create")

        self.assertEqual(ansible_data["inputs"], inputs)

    def test_update_secrets_true_includes_inputs_on_update(self):
        action = self._make_action(True)
        ansible_data = {"name": "credential"}
        inputs = {"username": "new-user"}

        action._pre_execute_hook(ansible_data, {"inputs": inputs}, {"update_secrets": True}, "update")

        self.assertEqual(ansible_data["inputs"], inputs)

    def test_update_secrets_false_still_detects_regular_field_changes(self):
        action = self._make_action(False)
        desired = {"name": "credential", "description": "new description", "inputs": {"username": "new-user"}}
        current = {"name": "credential", "description": "old description", "inputs": {"username": "old-user"}}

        self.assertTrue(action._should_update(desired, current))

    def test_update_secrets_true_detects_input_changes(self):
        action = self._make_action(True)
        action._task.args["inputs"] = {"username": "new-user"}
        desired = {"name": "credential"}
        current = {"name": "credential"}

        self.assertTrue(action._should_update(desired, current))


if __name__ == "__main__":
    unittest.main()
