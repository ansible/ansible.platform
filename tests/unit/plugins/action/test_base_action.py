# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for reusable BaseResourceActionPlugin preparation helpers."""

from __future__ import absolute_import, division, print_function

import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.authenticator_user import ActionModule as AuthenticatorUserAction
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.action.host import ActionModule as HostAction
from ansible_collections.ansible.platform.plugins.action.role_team_assignment import ActionModule as RoleTeamAssignmentAction
from ansible_collections.ansible.platform.plugins.action.role_user_assignment import ActionModule as RoleUserAssignmentAction
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.authenticator_user import AnsibleAuthenticatorUser


@dataclass
class Resource:
    name: str
    value: int = 0


class ExampleAction(BaseResourceActionPlugin):
    MODULE_NAME = "example"
    MODEL_CLASS = Resource
    _WRITE_ONLY_FIELDS = frozenset({"write_only"})
    _DEPRECATED_FIELDS = {"old_value": ("old_value is deprecated", "2.0.0")}


class OverrideResourceAction(ExampleAction):
    def _build_resource(self, resource_data):
        return Resource(name=resource_data["name"], value=resource_data.get("value", 0) + 1)


class OutputFormattingAction(ExampleAction):
    _EXTRA_RETURN_FIELDS = frozenset({"client_id"})
    _SPACE_SEPARATED_LIST_FIELDS = frozenset({"labels"})


class TestActionPreparation(unittest.TestCase):
    def _make_action(self):
        action = ExampleAction.__new__(ExampleAction)
        action._task = MagicMock()
        action._task.args = {
            "name": "resource",
            "value": 3,
            "write_only": "secret",
            "old_value": "legacy",
        }
        action._display = MagicMock()
        action._display.verbosity = 0
        return action

    def _run_present_with_find_error(self, find_error):
        action = ExampleAction.__new__(ExampleAction)
        action._task = MagicMock()
        action._task.check_mode = False
        action._display = MagicMock()
        action._display.verbosity = 0
        manager = MagicMock()
        manager.execute.side_effect = [find_error, {"id": 1, "name": "resource", "value": 3, "changed": True}]
        prepared = {
            "result": {},
            "argspec": {"argument_spec": {"name": {}, "value": {}}},
            "validated_params": {"name": "resource", "value": 3, "state": "present"},
            "resource_data": {"name": "resource", "value": 3},
            "write_only_data": {},
            "manager": manager,
        }

        with patch.object(action, "_prepare_action", return_value=prepared):
            result = action.run(task_vars={})

        return result, manager

    def _run_lookup_state_with_find_error(self, state, find_error):
        action = ExampleAction.__new__(ExampleAction)
        action._task = MagicMock()
        action._task.check_mode = False
        action._display = MagicMock()
        action._display.verbosity = 0
        manager = MagicMock()
        manager.execute.side_effect = find_error
        prepared = {
            "result": {},
            "argspec": {"argument_spec": {"name": {}, "value": {}}},
            "validated_params": {"name": "resource", "value": 3, "state": state},
            "resource_data": {"name": "resource", "value": 3},
            "write_only_data": {},
            "manager": manager,
        }

        with patch.object(action, "_prepare_action", return_value=prepared):
            result = action.run(task_vars={})

        return result, manager

    def test_should_update_repeated_rename_is_idempotent(self):
        """A rename to the current name does not force another update."""
        action = self._make_action()

        self.assertFalse(
            action._should_update(
                {"name": "resource", "new_name": "resource", "value": 3},
                {"name": "resource", "value": 3},
            )
        )

    def test_should_update_detects_changed_rename(self):
        """A rename to a different name still forces an update."""
        action = self._make_action()

        self.assertTrue(
            action._should_update(
                {"name": "resource", "new_name": "renamed-resource", "value": 3},
                {"name": "resource", "value": 3},
            )
        )

    def test_prepare_action_reuses_documentation_validation_and_manager(self):
        action = self._make_action()
        manager = MagicMock()
        validation = SimpleNamespace(
            validated_parameters=dict(action._task.args),
        )

        with patch.object(ActionBase, "run", return_value={"initial": True}) as base_run:
            with patch.object(action, "_get_documentation", return_value="module: example") as get_doc:
                with patch.object(action, "_build_argspec_from_docs", return_value={"argument_spec": {}}) as build_argspec:
                    with patch.object(action, "_validate_data", return_value=validation) as validate:
                        with patch.object(action, "_get_or_spawn_manager", return_value=(manager, {"platform": "fact"})) as get_manager:
                            prepared = action._prepare_action(task_vars={"inventory_hostname": "localhost"})

        base_run.assert_called_once()
        get_doc.assert_called_once_with()
        build_argspec.assert_called_once_with("module: example")
        validate.assert_called_once_with(action._task.args.copy(), {"argument_spec": {}}, "input")
        get_manager.assert_called_once_with({"inventory_hostname": "localhost"})
        self.assertIs(prepared["manager"], manager)
        self.assertEqual(prepared["resource_data"], {"name": "resource", "value": 3})
        self.assertEqual(prepared["write_only_data"], {"write_only": "secret"})
        self.assertEqual(prepared["result"]["ansible_facts"], {"platform": "fact"})
        self.assertEqual(prepared["result"]["deprecations"][0]["version"], "2.0.0")

    def test_format_resource_output_uses_validated_parameters_and_preserves_flat_extras(self):
        action = OutputFormattingAction.__new__(OutputFormattingAction)
        argspec = {"argument_spec": {"name": {}, "labels": {}}}
        manager_result = {
            "id": 7,
            "name": "raw-name",
            "labels": "raw labels",
            "client_id": "client-123",
            "unexpected": "discarded",
        }
        validation_result = SimpleNamespace(validated_parameters={"name": "normalized-name", "labels": "one two"})

        with patch.object(action, "_validate_data", return_value=validation_result):
            resource_output, flat_extras = action._format_resource_output(manager_result, argspec)

        self.assertEqual(resource_output, {"id": 7, "name": "normalized-name", "labels": ["one", "two"]})
        self.assertEqual(flat_extras, {"client_id": "client-123"})

    def test_format_resource_output_fallback_keeps_argspec_filter_and_conversions(self):
        action = OutputFormattingAction.__new__(OutputFormattingAction)
        argspec = {"argument_spec": {"name": {}, "labels": {}}}
        manager_result = {
            "id": 7,
            "name": "raw-name",
            "labels": "one two",
            "client_id": "client-123",
            "unexpected": "discarded",
            "changed": True,
        }

        with patch.object(action, "_validate_data", side_effect=ValueError("output validation failed")):
            resource_output, flat_extras = action._format_resource_output(manager_result, argspec)

        self.assertEqual(resource_output, {"id": 7, "name": "raw-name", "labels": ["one", "two"]})
        self.assertEqual(flat_extras, {"client_id": "client-123"})

    def test_unchanged_host_result_preserves_instance_id(self):
        action = HostAction.__new__(HostAction)
        action._task = MagicMock()
        action._display = MagicMock()
        manager = MagicMock()
        manager.execute.return_value = {"id": 7, "name": "host-a", "inventory": 3, "instance_id": "i-abc123"}
        prepared = {
            "result": {},
            "argspec": {"argument_spec": {"name": {"type": "str"}, "inventory": {"type": "str"}, "instance_id": {"type": "str"}}},
            "validated_params": {"name": "host-a", "inventory": "3", "state": "present"},
            "resource_data": {"name": "host-a", "inventory": "3"},
            "write_only_data": {},
            "manager": manager,
        }

        with patch.object(action, "_prepare_action", return_value=prepared):
            with patch.object(action, "_should_update", return_value=False):
                result = action.run(task_vars={})

        self.assertFalse(result["changed"])
        self.assertEqual(result["instance_id"], "i-abc123")
        self.assertEqual(result["host"]["instance_id"], "i-abc123")

    def test_run_dispatches_to_build_resource_override(self):
        action = OverrideResourceAction.__new__(OverrideResourceAction)
        action._task = MagicMock()
        action._task.check_mode = False
        action._display = MagicMock()
        action._display.verbosity = 0
        manager = MagicMock()
        manager.execute.return_value = {"id": 1, "name": "resource", "value": 5, "changed": True}
        prepared = {
            "result": {},
            "argspec": {"argument_spec": {"name": {}, "value": {}}},
            "validated_params": {"name": "resource", "value": 4, "state": "present"},
            "resource_data": {"name": "resource", "value": 4},
            "write_only_data": {},
            "manager": manager,
        }

        with patch.object(action, "_prepare_action", return_value=prepared):
            with patch.object(action, "_resolve_lookup"):
                with patch.object(action, "_build_resource", wraps=action._build_resource) as build_resource:
                    result = action.run(task_vars={})

        build_resource.assert_called_once_with({"name": "resource", "value": 4})
        self.assertEqual(result["id"], 1)

    def test_run_creates_resource_after_not_found_lookup(self):
        result, manager = self._run_present_with_find_error(ValueError("Resource with name=resource not found"))

        self.assertFalse(result["failed"])
        self.assertTrue(result["changed"])
        self.assertEqual(manager.execute.call_count, 2)
        self.assertEqual(manager.execute.call_args_list[0].kwargs["operation"], "find")
        self.assertEqual(manager.execute.call_args_list[1].kwargs["operation"], "create")

    def test_qualified_resource_not_found_is_false_for_lookup_states(self):
        error = ValueError("Resource 'credential-types' with name=unknown not found")

        self.assertTrue(BaseResourceActionPlugin._is_resource_not_found(error))
        for state in ("find", "exists", "gathered"):
            with self.subTest(state=state):
                result, manager = self._run_lookup_state_with_find_error(state, error)

                self.assertFalse(result["failed"])
                self.assertFalse(result["exists"])
                manager.execute.assert_called_once()

    def test_run_does_not_create_after_lookup_error(self):
        result, manager = self._run_present_with_find_error(ValueError("503 Service Unavailable"))

        self.assertTrue(result["failed"])
        self.assertIn("503 Service Unavailable", result["msg"])
        manager.execute.assert_called_once_with(operation="find", module_name="example", ansible_data={"name": "resource", "value": 3})

    def test_role_team_assignment_preserves_scalar_object_id_in_results(self):
        action = RoleTeamAssignmentAction.__new__(RoleTeamAssignmentAction)
        action._task = MagicMock()
        action._task.args = {}
        action._task.check_mode = False
        action._display = MagicMock()
        action._display.verbosity = 0
        manager = MagicMock()
        manager_result = {"id": 1, "role_definition": "5", "team": "7", "object_id": 202, "changed": True}
        manager.execute.side_effect = [{}, manager_result]
        prepared = {
            "result": {},
            "argspec": {"argument_spec": {"role_definition": {}, "team": {}, "object_id": {}}},
            "validated_params": {"role_definition": "5", "team": "7", "object_id": 202, "state": "present"},
            "resource_data": {"role_definition": "5", "team": "7", "object_id": 202},
            "write_only_data": {},
            "manager": manager,
        }

        with patch.object(action, "_prepare_action", return_value=prepared):
            with patch.object(action, "_validate_data", return_value=SimpleNamespace(validated_parameters=manager_result)):
                result = action.run(task_vars={})

        self.assertEqual(result["role_team_assignment"]["object_id"], 202)
        self.assertEqual(result["object_id"], 202)

    def test_role_user_assignment_preserves_scalar_object_id_in_results(self):
        action = RoleUserAssignmentAction.__new__(RoleUserAssignmentAction)
        action._task = MagicMock()
        action._task.args = {}
        action._task.check_mode = False
        action._display = MagicMock()
        action._display.verbosity = 0
        manager = MagicMock()
        manager_result = {"id": 1, "role_definition": "5", "user": "alice", "object_id": 202, "changed": True}
        manager.execute.side_effect = [{}, manager_result]
        prepared = {
            "result": {},
            "argspec": {"argument_spec": {"role_definition": {}, "user": {}, "object_id": {}}},
            "validated_params": {"role_definition": "5", "user": "alice", "object_id": 202, "state": "present"},
            "resource_data": {"role_definition": "5", "user": "alice", "object_id": 202},
            "write_only_data": {},
            "manager": manager,
        }

        with patch.object(action, "_prepare_action", return_value=prepared):
            with patch.object(action, "_validate_data", return_value=SimpleNamespace(validated_parameters=manager_result)):
                result = action.run(task_vars={})

        self.assertEqual(result["role_user_assignment"]["object_id"], 202)
        self.assertEqual(result["object_id"], 202)

    def test_prepare_action_rejects_missing_documentation(self):
        action = self._make_action()

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_documentation", return_value=""):
                with self.assertRaisesRegex(Exception, "Could not load DOCUMENTATION"):
                    action._prepare_action()

    def test_run_preserves_preparation_error(self):
        action = self._make_action()

        with patch.object(action, "_prepare_action", side_effect=ValueError("invalid documentation")):
            result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertEqual(result["msg"], "invalid documentation")


class TestRoleTeamAssignmentMultiObject(unittest.TestCase):
    def _action(self, assignment_objects, manager):
        action = RoleTeamAssignmentAction.__new__(RoleTeamAssignmentAction)
        action._task = MagicMock()
        action._task.args = {"assignment_objects": assignment_objects}
        action._task.check_mode = False
        action._display = MagicMock()
        action._display.verbosity = 0
        prepared = {
            "result": {},
            "validated_params": {
                "role_definition": "404",
                "team": "7",
                "state": "absent",
                "assignment_objects": assignment_objects,
            },
            "manager": manager,
        }
        return action, prepared

    def test_deleted_numeric_role_does_not_block_object_id_cleanup(self):
        assignment_objects = [{"object_id": 202}]
        action, prepared = self._action(assignment_objects, MagicMock())

        def execute(**kwargs):
            if kwargs["operation"] == "find":
                return {"id": 11, "object_id": "202"}
            return {}

        prepared["manager"].execute.side_effect = execute
        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_validate_action_input", return_value=SimpleNamespace(validated_params=prepared["validated_params"])):
                with patch.object(action, "_get_or_spawn_manager", return_value=(prepared["manager"], None)):
                    result = action.run(task_vars={})

        self.assertFalse(result["failed"])
        self.assertTrue(result["changed"])
        self.assertEqual(
            [call.kwargs["module_name"] for call in prepared["manager"].execute.call_args_list],
            ["role_team_assignment", "role_team_assignment"],
        )

    def test_name_type_selector_preserves_role_lookup_errors(self):
        assignment_objects = [{"name": "target", "type": "organizations"}]
        action, prepared = self._action(assignment_objects, MagicMock())
        prepared["manager"].execute.side_effect = ValueError("503 Service Unavailable")

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_validate_action_input", return_value=SimpleNamespace(validated_params=prepared["validated_params"])):
                with patch.object(action, "_get_or_spawn_manager", return_value=(prepared["manager"], None)):
                    result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("503 Service Unavailable", result["msg"])
        prepared["manager"].execute.assert_called_once_with(
            operation="find",
            module_name="role_definition",
            ansible_data={"name": "404"},
        )

    def test_name_type_selector_keeps_content_type_validation(self):
        assignment_objects = [{"name": "target", "type": "teams"}]
        action, prepared = self._action(assignment_objects, MagicMock())
        prepared["manager"].execute.return_value = {"content_type": "shared.organization"}

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_validate_action_input", return_value=SimpleNamespace(validated_params=prepared["validated_params"])):
                with patch.object(action, "_get_or_spawn_manager", return_value=(prepared["manager"], None)):
                    result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("requires type 'organizations'", result["msg"])
        prepared["manager"].execute.assert_called_once_with(
            operation="find",
            module_name="role_definition",
            ansible_data={"name": "404"},
        )


class TestRoleUserAssignmentExistsMiss(unittest.TestCase):
    def test_scalar_and_list_selector_misses_share_failure_result(self):
        selectors = (
            {"object_id": 202},
            {"object_ansible_id": "object-uuid"},
            {"object_ids": [202]},
        )
        expected = {
            "changed": False,
            "failed": True,
            "exists": False,
            "role_user_assignment": {},
            "msg": "No role_user_assignment found matching the given criteria",
        }

        for selector in selectors:
            with self.subTest(selector=selector):
                action = RoleUserAssignmentAction.__new__(RoleUserAssignmentAction)
                action._task = MagicMock()
                action._task.args = dict(selector, state="exists")
                action._display = MagicMock()
                action._display.verbosity = 0
                manager = MagicMock()
                manager.execute.return_value = {}
                validated_params = dict(selector, role_definition="5", user="alice", state="exists")

                with patch.object(ActionBase, "run", return_value={}):
                    with patch.object(action, "_validate_action_input", return_value=SimpleNamespace(validated_params=validated_params)):
                        with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                            result = action.run(task_vars={})

                self.assertEqual(result, expected)


class TestAuthenticatorUserLookup(unittest.TestCase):
    """Tests for authenticator-user lookup resolution."""

    def test_numeric_authenticator_user_id_populates_resource_id(self):
        """A numeric module ID is copied to the generic resource ID."""
        action = AuthenticatorUserAction.__new__(AuthenticatorUserAction)
        resource = AnsibleAuthenticatorUser(authenticator_user_id="42", authenticator="7")
        resource_data = {"authenticator_user_id": "42", "authenticator": "7"}

        action._resolve_lookup(resource, resource_data, {})

        self.assertEqual(resource.id, 42)
        self.assertEqual(resource_data["id"], 42)

    def test_nonnumeric_authenticator_user_id_does_not_populate_resource_id(self):
        """An invalid nonnumeric module ID is left for normal validation."""
        action = AuthenticatorUserAction.__new__(AuthenticatorUserAction)
        resource = AnsibleAuthenticatorUser(authenticator_user_id="invalid", authenticator="7")
        resource_data = {"authenticator_user_id": "invalid", "authenticator": "7"}

        action._resolve_lookup(resource, resource_data, {})

        self.assertIsNone(resource.id)
        self.assertNotIn("id", resource_data)


if __name__ == "__main__":
    unittest.main()
