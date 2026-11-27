# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the job_template action plugin's Pattern C logic
(associations, copy_from, survey_spec) layered on top of the generic CRUD run()."""

from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.action.job_template import BASE_PATH, ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.job_template import JobTemplateTransformMixin_v2
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext

__metaclass__ = type


def _action(task_args, check_mode=False):
    action = ActionModule.__new__(ActionModule)
    action._task = MagicMock()
    action._task.args = dict(task_args)
    action._task.check_mode = check_mode
    action._display = MagicMock()
    return action


_LEGACY_ALIASES = (
    ("force_handlers_enabled", "force_handlers"),
    ("fact_caching_enabled", "use_fact_cache"),
    ("ask_diff_mode", "ask_diff_mode_on_launch"),
    ("ask_extra_vars", "ask_variables_on_launch"),
    ("ask_limit", "ask_limit_on_launch"),
    ("ask_tags", "ask_tags_on_launch"),
    ("ask_skip_tags", "ask_skip_tags_on_launch"),
    ("ask_job_type", "ask_job_type_on_launch"),
    ("ask_verbosity", "ask_verbosity_on_launch"),
    ("ask_inventory", "ask_inventory_on_launch"),
    ("ask_credential", "ask_credential_on_launch"),
    ("ask_execution_environment", "ask_execution_environment_on_launch"),
    ("ask_forks", "ask_forks_on_launch"),
    ("ask_instance_groups", "ask_instance_groups_on_launch"),
    ("ask_job_slice_count", "ask_job_slice_count_on_launch"),
    ("ask_timeout", "ask_timeout_on_launch"),
    ("ask_labels", "ask_labels_on_launch"),
    ("diff_mode_enabled", "diff_mode"),
    ("concurrent_jobs_enabled", "allow_simultaneous"),
)


def _prepare_job_template(resource_fields, check_mode=False):
    action = _action({"name": "Ping", **resource_fields}, check_mode=check_mode)
    manager = MagicMock()
    with patch.object(ActionBase, "run", return_value={}), patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
        prepared = action._prepare_action(None, {})
    return action, prepared, manager


def _to_api_data(action, resource_data, manager):
    resource = action.MODEL_CLASS(**resource_data)
    context = TransformContext(
        manager=manager,
        session=MagicMock(),
        cache={},
        api_version="2",
        service="controller",
        operation="create",
    )
    return JobTemplateTransformMixin_v2.from_ansible_data(resource, context)


class TestLegacyParameterAliases(unittest.TestCase):
    def test_aliases_and_canonical_options_produce_equivalent_api_data(self):
        for alias, canonical in _LEGACY_ALIASES:
            for value in (False, True):
                with self.subTest(alias=alias, value=value):
                    alias_action, alias_prepared, alias_manager = _prepare_job_template({alias: value})
                    canonical_action, canonical_prepared, canonical_manager = _prepare_job_template({canonical: value})
                    alias_resource_data = alias_prepared["resource_data"]
                    canonical_resource_data = canonical_prepared["resource_data"]

                    self.assertNotIn(alias, alias_resource_data)
                    self.assertIs(alias_resource_data[canonical], value)
                    self.assertIs(canonical_resource_data[canonical], value)
                    alias_api_data = _to_api_data(alias_action, alias_resource_data, alias_manager)
                    canonical_api_data = _to_api_data(canonical_action, canonical_resource_data, canonical_manager)
                    self.assertEqual(alias_api_data, canonical_api_data)
                    self.assertIs(getattr(alias_api_data, canonical), value)

    def test_conflicting_alias_and_canonical_values_preserve_alias_precedence(self):
        action, prepared, manager = _prepare_job_template({"ask_variables_on_launch": True, "ask_extra_vars": False})

        self.assertIs(prepared["resource_data"]["ask_variables_on_launch"], False)
        self.assertEqual(prepared["result"]["warnings"], ["Both option ask_variables_on_launch and its alias ask_extra_vars are set."])
        api_data = _to_api_data(action, prepared["resource_data"], manager)
        self.assertIs(api_data.ask_variables_on_launch, False)

    def test_alias_is_validated_in_check_mode_without_api_write(self):
        action = _action({"name": "Ping", "ask_variables_on_launch": True, "ask_extra_vars": False}, check_mode=True)
        manager = MagicMock()
        manager.execute.side_effect = ValueError("not found")
        with patch.object(ActionBase, "run", return_value={}), patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
            result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertFalse(result["failed"])
        self.assertEqual(result["warnings"], ["Both option ask_variables_on_launch and its alias ask_extra_vars are set."])
        manager.execute.assert_called_once()
        self.assertEqual(manager.execute.call_args.kwargs["operation"], "find")
        self.assertIs(manager.execute.call_args.kwargs["ansible_data"]["ask_variables_on_launch"], False)


class TestAssociationReconciliation(unittest.TestCase):
    def test_credentials_applied_after_create(self):
        action = _action({"name": "Ping", "credentials": ["Local"], "state": "present"})
        manager = MagicMock()
        manager.manage_associations.return_value = True

        with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": True, "failed": False, "id": 5, "job_template": {"id": 5}}):
            action._client = manager
            result = action.run(task_vars={})

        manager.manage_associations.assert_called_once_with(BASE_PATH, 5, "credentials", ["Local"], "credentials", "name", service="controller")
        self.assertTrue(result["changed"])

    def test_survey_spec_applied_after_create(self):
        action = _action({"name": "Ping", "survey_spec": {"name": "survey"}, "state": "present"})
        manager = MagicMock()
        manager.manage_sub_resource.return_value = True

        with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "failed": False, "id": 5}):
            action._client = manager
            result = action.run(task_vars={})

        manager.manage_sub_resource.assert_called_once_with(BASE_PATH, 5, "survey_spec", {"name": "survey"})
        self.assertTrue(result["changed"])

    def test_no_reconciliation_fields_means_no_manager_calls(self):
        action = _action({"name": "Ping", "state": "present"})
        manager = MagicMock()

        with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": True, "failed": False, "id": 5}):
            action._client = manager
            result = action.run(task_vars={})

        manager.manage_associations.assert_not_called()
        manager.manage_sub_resource.assert_not_called()
        self.assertTrue(result["changed"])

    def test_no_reconciliation_when_state_absent(self):
        action = _action({"name": "Ping", "credentials": ["Local"], "state": "absent"})
        manager = MagicMock()

        with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": True, "failed": False}):
            action._client = manager
            action.run(task_vars={})

        manager.manage_associations.assert_not_called()

    def test_no_reconciliation_when_state_exists(self):
        action = _action({"name": "Ping", "credentials": ["Local"], "state": "exists"})
        manager = MagicMock()

        with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "failed": False, "exists": True}):
            action._client = manager
            action.run(task_vars={})

        manager.manage_associations.assert_not_called()

    def test_no_reconciliation_when_crud_failed(self):
        action = _action({"name": "Ping", "credentials": ["Local"], "state": "present"})
        manager = MagicMock()

        with patch.object(BaseResourceActionPlugin, "run", return_value={"failed": True, "msg": "boom"}):
            action._client = manager
            result = action.run(task_vars={})

        manager.manage_associations.assert_not_called()
        self.assertTrue(result["failed"])

    def test_association_failure_sets_failed_result(self):
        action = _action({"name": "Ping", "credentials": ["Local"], "state": "present"})
        manager = MagicMock()
        manager.manage_associations.side_effect = ValueError("not found")

        with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": True, "failed": False, "id": 5}):
            action._client = manager
            result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("not found", result["msg"])

    def test_credential_and_vault_credential_aliases_merge_into_credentials(self):
        credentials = ["Existing"]
        action = _action({"name": "Ping", "credentials": credentials, "credential": "Local", "vault_credential": "Vault", "state": "present"})
        manager = MagicMock()
        manager.manage_associations.return_value = True

        with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "failed": False, "id": 5}):
            action._client = manager
            action.run(task_vars={})

        call_args = manager.manage_associations.call_args
        self.assertEqual(call_args.args[0], BASE_PATH)
        self.assertEqual(sorted(call_args.args[3]), ["Existing", "Local", "Vault"])
        self.assertEqual(credentials, ["Existing"])

    def test_credential_and_vault_credential_surface_deprecation_warnings(self):
        action = _action({"name": "Ping", "credential": "Local", "vault_credential": "Vault", "state": "present"})
        manager = MagicMock()

        with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "failed": False, "id": 5}):
            action._client = manager
            result = action.run(task_vars={})

        deprecated_params = {d["msg"] for d in result["deprecations"]}
        self.assertEqual(len(result["deprecations"]), 2)
        self.assertTrue(any("'credential'" in msg for msg in deprecated_params))
        self.assertTrue(any("'vault_credential'" in msg for msg in deprecated_params))

    def test_no_deprecation_warnings_when_only_credentials_used(self):
        action = _action({"name": "Ping", "credentials": ["Local"], "state": "present"})
        manager = MagicMock()

        with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "failed": False, "id": 5}):
            action._client = manager
            result = action.run(task_vars={})

        self.assertNotIn("deprecations", result)


class TestCheckMode(unittest.TestCase):
    def test_check_mode_never_calls_manage_associations(self):
        action = _action({"name": "Ping", "credentials": ["Local"], "state": "present"}, check_mode=True)
        manager = MagicMock()

        with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": True, "failed": False, "id": 5}):
            action._client = manager
            result = action.run(task_vars={})

        manager.manage_associations.assert_not_called()
        manager.manage_sub_resource.assert_not_called()
        self.assertTrue(result["changed"])

    def test_check_mode_reports_no_change_when_no_reconcile_fields_set(self):
        action = _action({"name": "Ping", "state": "present"}, check_mode=True)
        manager = MagicMock()

        with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "failed": False, "id": 5}):
            action._client = manager
            result = action.run(task_vars={})

        self.assertFalse(result["changed"])

    def test_check_mode_never_calls_copy_resource(self):
        action = _action({"name": "Ping copy", "copy_from": "Ping", "state": "present"}, check_mode=True)
        manager = MagicMock()

        with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
            with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": True, "failed": False, "id": None}):
                result = action.run(task_vars={})

        manager.copy_resource.assert_not_called()
        self.assertTrue(result["changed"])


class TestForeignKeyComparison(unittest.TestCase):
    def test_unchanged_unscoped_inventory_name_does_not_trigger_lookup(self):
        desired = {"name": "Ping", "inventory": "Hosts"}
        action = _action(desired)
        action._client = MagicMock()
        action._client.lookup_resource_id.side_effect = ValueError("Multiple inventories named Hosts")

        self.assertFalse(action._should_update(desired, {**desired, "inventory_id": 70}))
        action._client.lookup_resource_id.assert_not_called()

    def test_numeric_fk_and_organization_do_not_trigger_update_when_unchanged(self):
        action = _action({"name": "Ping"})
        action._client = MagicMock()
        action._client.search_api.return_value = {"name": "Mock Inventory"}

        changed = action._should_update(
            {"name": "Ping", "inventory": "5101", "organization": "Default"},
            {"name": "Ping", "inventory": "Mock Inventory", "inventory_id": 5101, "organization": None},
        )

        self.assertFalse(changed)
        action._client.search_api.assert_not_called()

    def test_scoped_inventory_comparison_uses_current_id(self):
        desired = {"name": "Ping", "inventory": "Hosts", "organization": "1", "inventory_organization": "9"}
        for current_id, expected_change in ((70, True), (90, False)):
            with self.subTest(current_id=current_id):
                action = _action(desired)
                action._client = MagicMock()
                action._client.lookup_resource_id.return_value = 90

                changed = action._should_update(desired, {"name": "Ping", "inventory": "Hosts", "inventory_id": current_id})

                self.assertIs(changed, expected_change)
                action._client.lookup_resource_id.assert_called_once_with(
                    "inventories", "name", "Hosts", service="controller", extra_query_params={"organization": 9}
                )


class TestCopyFrom(unittest.TestCase):
    def test_copy_from_calls_copy_resource_before_crud(self):
        action = _action({"name": "Ping copy", "copy_from": "Ping", "state": "present"})
        manager = MagicMock()
        manager.search_api.return_value = {"results": []}

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": True, "failed": False, "id": 9}):
                    result = action.run(task_vars={})

        manager.copy_resource.assert_called_once_with("job_template", "Ping", "Ping copy", BASE_PATH, service="controller")
        self.assertTrue(result["changed"])

    def test_copy_from_does_not_copy_existing_destination(self):
        action = _action({"name": "Ping copy", "copy_from": "Ping", "state": "present"})
        manager = MagicMock()
        manager.search_api.return_value = {"results": [{"id": 9, "name": "Ping copy"}]}

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "failed": False, "id": 9}):
                    result = action.run(task_vars={})

        manager.copy_resource.assert_not_called()
        self.assertFalse(result["changed"])

    def test_copy_from_skipped_when_state_absent(self):
        action = _action({"name": "Ping copy", "copy_from": "Ping", "state": "absent"})
        manager = MagicMock()

        with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
            with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": True, "failed": False}):
                action.run(task_vars={})

        manager.copy_resource.assert_not_called()

    def test_copy_from_failure_returns_failed_result_without_crud(self):
        action = _action({"name": "Ping copy", "copy_from": "Missing", "state": "present"})
        manager = MagicMock()
        manager.copy_resource.side_effect = ValueError("Could not find job_template 'Missing' to copy from")

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                with patch.object(BaseResourceActionPlugin, "run") as mock_super_run:
                    result = action.run(task_vars={})

        mock_super_run.assert_not_called()
        self.assertTrue(result["failed"])
        self.assertIn("Missing", result["msg"])


if __name__ == "__main__":
    unittest.main()
