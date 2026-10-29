"""Unit tests for bulk_job_launch action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock, patch

import pytest


def _launch_result():
    """Return the action result shape produced by the create transform."""
    return {
        "changed": True,
        "id": 42,
        "status": "pending",
        "job_info": {"id": 42, "status": "pending", "type": "workflow_job"},
    }


@pytest.fixture
def action_module():
    """Create a minimally-initialized ActionModule for testing."""
    from ansible_collections.ansible.platform.plugins.action.bulk_job_launch import ActionModule

    module = ActionModule.__new__(ActionModule)
    module.MODULE_NAME = "bulk_job_launch"
    module._display = MagicMock()
    module._display.verbosity = 0
    module._task = MagicMock()
    module._task.check_mode = False
    module._task.args = {}
    module._task.environment = []
    module._connection = MagicMock()
    module._loader = MagicMock()
    module._templar = MagicMock()
    module._shared_loader_obj = MagicMock()
    return module


class TestBulkJobLaunchActionModule:
    """Tests for bulk_job_launch action plugin."""

    def test_module_name(self, action_module):
        assert action_module.MODULE_NAME == "bulk_job_launch"

    def test_model_class(self):
        from ansible_collections.ansible.platform.plugins.action.bulk_job_launch import ActionModule
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.bulk_job_launch import AnsibleBulkJobLaunch

        assert ActionModule.MODEL_CLASS is AnsibleBulkJobLaunch

    def test_check_mode_returns_changed(self, action_module):
        action_module._task.check_mode = True

        mock_manager = MagicMock()
        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [{"unified_job_template": 7}],
                    "wait": True,
                    "interval": 2.0,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["changed"] is True
        assert "check mode" in result["msg"]
        mock_manager.execute.assert_not_called()

    def test_check_mode_fails_on_invalid_reference(self, action_module):
        action_module._task.check_mode = True

        mock_manager = MagicMock()
        mock_manager.execute.side_effect = ValueError("Inventory 'Missing' was not found")
        validated_params = {
            "jobs": [{"unified_job_template": 7}],
            "organization": "Default",
            "inventory": "Missing",
            "wait": True,
            "interval": 2.0,
        }
        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": validated_params,
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert result["msg"] == "Inventory 'Missing' was not found"
        mock_manager.execute.assert_called_once_with("resolve", "bulk_job_launch", {"organization": "Default", "inventory": "Missing"})

    def test_empty_jobs_fails(self, action_module):
        mock_manager = MagicMock()
        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [],
                    "wait": True,
                    "interval": 2.0,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert "jobs" in result["msg"]

    def test_launch_without_wait(self, action_module):
        mock_manager = MagicMock()
        mock_manager.execute.return_value = _launch_result()

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [{"unified_job_template": 7}],
                    "name": None,
                    "description": None,
                    "organization": None,
                    "inventory": None,
                    "limit": None,
                    "scm_branch": None,
                    "extra_vars": None,
                    "job_tags": None,
                    "skip_tags": None,
                    "wait": False,
                    "interval": 2.0,
                    "timeout": None,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["changed"] is True
        assert result["id"] == 42
        assert result["status"] == "pending"
        assert result["job_info"]["type"] == "workflow_job"
        mock_manager.execute.assert_called_once()
        mock_manager.wait_for_completion.assert_not_called()

    def test_launch_with_wait_success(self, action_module):
        mock_manager = MagicMock()
        mock_manager.execute.return_value = {
            "id": 42,
            "status": "pending",
        }
        mock_manager.wait_for_completion.return_value = {
            "id": 42,
            "status": "successful",
        }

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [{"unified_job_template": 7}, {"unified_job_template": 10}],
                    "name": "My Bulk Launch",
                    "description": None,
                    "organization": None,
                    "inventory": None,
                    "limit": None,
                    "scm_branch": None,
                    "extra_vars": None,
                    "job_tags": None,
                    "skip_tags": None,
                    "wait": True,
                    "interval": 2.0,
                    "timeout": 600,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["changed"] is True
        assert result["id"] == 42
        assert result["status"] == "successful"
        assert result.get("failed") is not True
        mock_manager.wait_for_completion.assert_called_once_with(
            "workflow_jobs/42",
            timeout=600.0,
            interval=2.0,
            service="controller",
        )

    def test_launch_with_wait_failure_status(self, action_module):
        mock_manager = MagicMock()
        mock_manager.execute.return_value = _launch_result()
        mock_manager.wait_for_completion.return_value = {"id": 42, "status": "failed"}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [{"unified_job_template": 7}],
                    "name": None,
                    "description": None,
                    "organization": None,
                    "inventory": None,
                    "limit": None,
                    "scm_branch": None,
                    "extra_vars": None,
                    "job_tags": None,
                    "skip_tags": None,
                    "wait": True,
                    "interval": 2.0,
                    "timeout": None,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert result["status"] == "failed"
        assert "Bulk job 42" in result["msg"]

    @pytest.mark.parametrize("status", ["error", "canceled"])
    def test_launch_with_wait_error_status(self, action_module, status):
        mock_manager = MagicMock()
        mock_manager.execute.return_value = _launch_result()
        mock_manager.wait_for_completion.return_value = {"id": 42, "status": status}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [{"unified_job_template": 7}],
                    "name": None,
                    "description": None,
                    "organization": None,
                    "inventory": None,
                    "limit": None,
                    "scm_branch": None,
                    "extra_vars": None,
                    "job_tags": None,
                    "skip_tags": None,
                    "wait": True,
                    "interval": 2.0,
                    "timeout": None,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert result["status"] == status

    def test_launch_with_wait_failed_flag(self, action_module):
        mock_manager = MagicMock()
        mock_manager.execute.return_value = _launch_result()
        mock_manager.wait_for_completion.return_value = {"id": 42, "failed": True}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [{"unified_job_template": 7}],
                    "wait": True,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert result["msg"] == "Bulk job 42 finished with status ''"

    def test_launch_with_wait_timeout(self, action_module):
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError

        mock_manager = MagicMock()
        mock_manager.execute.return_value = _launch_result()
        mock_manager.wait_for_completion.side_effect = WaitTimeoutError(
            "Timed out waiting after 10s",
            last_result={"id": 42, "status": "running"},
        )

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [{"unified_job_template": 7}],
                    "name": None,
                    "description": None,
                    "organization": None,
                    "inventory": None,
                    "limit": None,
                    "scm_branch": None,
                    "extra_vars": None,
                    "job_tags": None,
                    "skip_tags": None,
                    "wait": True,
                    "interval": 2.0,
                    "timeout": 10,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert "Timed out" in result["msg"]
        assert result["status"] == "running"
        assert result["job_info"] == {"id": 42, "status": "running"}

    def test_launch_uses_create_execution_path(self, action_module):
        mock_manager = MagicMock()
        mock_manager.execute.return_value = _launch_result()
        params = {
            "jobs": [{"unified_job_template": 7}],
            "name": "Bulk launch",
            "wait": False,
        }

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": params,
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        mock_manager.execute.assert_called_once_with("create", "bulk_job_launch", params)
        mock_manager.launch_resource.assert_not_called()
        assert result["id"] == 42
        assert result["status"] == "pending"
        assert result["job_info"]["type"] == "workflow_job"

    def test_docs_based_validation_accepts_organization_and_inventory(self, action_module):
        mock_manager = MagicMock()
        mock_manager.execute.return_value = _launch_result()
        action_module._task.args = {
            "jobs": [{"unified_job_template": 7}],
            "organization": "Default",
            "inventory": "Demo Inventory",
            "wait": False,
            "aap_hostname": "https://gateway.example.com",
            "persistent_manager_idle_timeout": 60,
        }

        with patch.object(action_module, "_get_or_spawn_manager", return_value=(mock_manager, None)):
            result = action_module.run(task_vars={})

        assert result.get("failed") is not True
        mock_manager.execute.assert_called_once()
        validated_params = mock_manager.execute.call_args.args[2]
        assert validated_params["organization"] == "Default"
        assert validated_params["inventory"] == "Demo Inventory"
        assert "aap_hostname" not in validated_params
        assert "persistent_manager_idle_timeout" not in validated_params

    @pytest.mark.parametrize("interval", [None, 0, -1])
    @pytest.mark.parametrize("check_mode", [False, True])
    def test_invalid_interval_fails_before_launch(self, action_module, interval, check_mode):
        action_module._task.check_mode = check_mode
        mock_manager = MagicMock()
        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [{"unified_job_template": 7}],
                    "wait": True,
                    "interval": interval,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert result["msg"] == "interval must be greater than 0"
        mock_manager.execute.assert_not_called()
        mock_manager.wait_for_completion.assert_not_called()

    def test_omitted_wait_timeout_preserves_indefinite_wait(self, action_module):
        mock_manager = MagicMock()
        mock_manager.execute.return_value = _launch_result()
        mock_manager.wait_for_completion.return_value = {"id": 42, "status": "successful"}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [{"unified_job_template": 7}],
                    "name": None,
                    "description": None,
                    "organization": None,
                    "inventory": None,
                    "limit": None,
                    "scm_branch": None,
                    "extra_vars": None,
                    "job_tags": None,
                    "skip_tags": None,
                    "wait": True,
                    "interval": 5.0,
                    "timeout": None,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            action_module.run(task_vars={})

        mock_manager.wait_for_completion.assert_called_once_with(
            "workflow_jobs/42",
            timeout=-1.0,
            interval=5.0,
            service="controller",
        )

    def test_negative_wait_timeout_fails_before_launch(self, action_module):
        mock_manager = MagicMock()

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [{"unified_job_template": 7}],
                    "wait": True,
                    "interval": 5.0,
                    "timeout": -1,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert result["msg"] == "timeout must be 0 or greater"
        mock_manager.execute.assert_not_called()
        mock_manager.wait_for_completion.assert_not_called()

    def test_job_info_updated_after_wait(self, action_module):
        mock_manager = MagicMock()
        mock_manager.execute.return_value = _launch_result()
        final_response = {"id": 42, "status": "successful", "elapsed": 15.3}
        mock_manager.wait_for_completion.return_value = final_response

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [{"unified_job_template": 7}],
                    "name": None,
                    "description": None,
                    "organization": None,
                    "inventory": None,
                    "limit": None,
                    "scm_branch": None,
                    "extra_vars": None,
                    "job_tags": None,
                    "skip_tags": None,
                    "wait": True,
                    "interval": 2.0,
                    "timeout": None,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["job_info"] == final_response
        assert result["job_info"]["elapsed"] == 15.3
