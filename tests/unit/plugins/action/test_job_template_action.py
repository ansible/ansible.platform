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

__metaclass__ = type


def _action(task_args, check_mode=False):
    action = ActionModule.__new__(ActionModule)
    action._task = MagicMock()
    action._task.args = dict(task_args)
    action._task.check_mode = check_mode
    action._display = MagicMock()
    return action


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
        action = _action({"name": "Ping", "credential": "Local", "vault_credential": "Vault", "state": "present"})
        manager = MagicMock()
        manager.manage_associations.return_value = True

        with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "failed": False, "id": 5}):
            action._client = manager
            action.run(task_vars={})

        call_args = manager.manage_associations.call_args
        self.assertEqual(call_args.args[0], BASE_PATH)
        self.assertEqual(sorted(call_args.args[3]), ["Local", "Vault"])

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


class TestCopyFrom(unittest.TestCase):
    def test_copy_from_calls_copy_resource_before_crud(self):
        action = _action({"name": "Ping copy", "copy_from": "Ping", "state": "present"})
        manager = MagicMock()

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": True, "failed": False, "id": 9}):
                    result = action.run(task_vars={})

        manager.copy_resource.assert_called_once_with("job_template", "Ping", "Ping copy", BASE_PATH, service="controller")
        self.assertTrue(result["changed"])

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
