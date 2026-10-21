"""Unit tests for bulk_job_launch action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock, patch

import pytest


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
        mock_manager.launch_resource.assert_not_called()

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
        mock_manager.launch_resource.return_value = {
            "id": 42,
            "status": "pending",
            "type": "workflow_job",
        }

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
        mock_manager.launch_resource.assert_called_once()
        mock_manager.wait_for_completion.assert_not_called()

    def test_launch_with_wait_success(self, action_module):
        mock_manager = MagicMock()
        mock_manager.launch_resource.return_value = {
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
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}
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

    def test_launch_with_wait_error_status(self, action_module):
        mock_manager = MagicMock()
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}
        mock_manager.wait_for_completion.return_value = {"id": 42, "status": "error"}

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
        assert result["status"] == "error"

    def test_launch_with_wait_timeout(self, action_module):
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import WaitTimeoutError

        mock_manager = MagicMock()
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}
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

    def test_organization_fk_resolution_by_name(self, action_module):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 3
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [{"unified_job_template": 7}],
                    "name": None,
                    "description": None,
                    "organization": "Default",
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
        mock_manager.lookup_resource_id.assert_called_once_with("organizations", "name", "Default")
        payload = mock_manager.launch_resource.call_args[0][1]
        assert payload["organization"] == 3

    def test_organization_fk_resolution_by_id(self, action_module):
        mock_manager = MagicMock()
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [{"unified_job_template": 7}],
                    "name": None,
                    "description": None,
                    "organization": "5",
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
        mock_manager.lookup_resource_id.assert_not_called()
        payload = mock_manager.launch_resource.call_args[0][1]
        assert payload["organization"] == 5

    def test_inventory_fk_resolution_by_name(self, action_module):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 7
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [{"unified_job_template": 7}],
                    "name": None,
                    "description": None,
                    "organization": None,
                    "inventory": "Production",
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
        mock_manager.lookup_resource_id.assert_called_once_with("inventories", "name", "Production", service="controller")
        payload = mock_manager.launch_resource.call_args[0][1]
        assert payload["inventory"] == 7

    def test_full_payload_construction(self, action_module):
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.side_effect = [3, 7]
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "jobs": [
                        {"unified_job_template": 7, "limit": "webservers"},
                        {"unified_job_template": 10, "extra_data": {"key": "val"}},
                    ],
                    "name": "My Bulk Launch",
                    "description": "Test bulk launch",
                    "organization": "Default",
                    "inventory": "Production",
                    "limit": "all",
                    "scm_branch": "main",
                    "extra_vars": {"food": "grape"},
                    "job_tags": "deploy",
                    "skip_tags": "debug",
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
        payload = mock_manager.launch_resource.call_args[0][1]
        assert len(payload["jobs"]) == 2
        assert payload["name"] == "My Bulk Launch"
        assert payload["description"] == "Test bulk launch"
        assert payload["organization"] == 3
        assert payload["inventory"] == 7
        assert payload["limit"] == "all"
        assert payload["scm_branch"] == "main"
        assert payload["extra_vars"] == {"food": "grape"}
        assert payload["job_tags"] == "deploy"
        assert payload["skip_tags"] == "debug"

    def test_launch_endpoint_used(self, action_module):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.bulk_job_launch import BULK_JOB_LAUNCH_ENDPOINT

        mock_manager = MagicMock()
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}

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
            action_module.run(task_vars={})

        mock_manager.launch_resource.assert_called_once_with(
            BULK_JOB_LAUNCH_ENDPOINT,
            {"jobs": [{"unified_job_template": 7}]},
            service="controller",
        )

    def test_none_optional_fields_omitted_from_payload(self, action_module):
        mock_manager = MagicMock()
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}

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
            action_module.run(task_vars={})

        payload = mock_manager.launch_resource.call_args[0][1]
        assert list(payload.keys()) == ["jobs"]

    def test_wait_timeout_none_passes_none(self, action_module):
        mock_manager = MagicMock()
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}
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
            timeout=None,
            interval=5.0,
            service="controller",
        )

    def test_job_info_updated_after_wait(self, action_module):
        mock_manager = MagicMock()
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}
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
