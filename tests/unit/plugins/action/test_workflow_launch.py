"""Unit tests for workflow_launch action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def action_module():
    """Create a minimally-initialized ActionModule for testing."""
    from ansible_collections.ansible.platform.plugins.action.workflow_launch import ActionModule

    module = ActionModule.__new__(ActionModule)
    module.MODULE_NAME = "workflow_launch"
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


class TestWorkflowLaunchActionModule:
    """Tests for workflow_launch action plugin."""

    def test_module_name(self, action_module):
        assert action_module.MODULE_NAME == "workflow_launch"

    def test_model_class(self):
        from ansible_collections.ansible.platform.plugins.action.workflow_launch import ActionModule
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.workflow_launch import AnsibleWorkflowLaunch

        assert ActionModule.MODEL_CLASS is AnsibleWorkflowLaunch

    def test_check_mode_returns_changed(self, action_module):
        """Check mode should short-circuit with changed=True."""
        action_module._task.check_mode = True
        action_module._task.args = {"name": "Test Workflow"}

        mock_manager = MagicMock()
        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {"name": "Test Workflow", "wait": True, "interval": 2.0},
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["changed"] is True
        assert "check mode" in result["msg"]
        mock_manager.launch_resource.assert_not_called()

    def test_launch_without_wait(self, action_module):
        """Launch with wait=False should return immediately after launch."""
        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {"results": [{"id": 10, "name": "Test WJT", "ask_inventory_on_launch": False}]}
        mock_manager.launch_resource.return_value = {
            "id": 42,
            "status": "pending",
            "type": "workflow_job",
        }

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "name": "Test WJT",
                    "organization": None,
                    "inventory": None,
                    "wait": False,
                    "interval": 2.0,
                    "timeout": None,
                    "limit": None,
                    "tags": None,
                    "skip_tags": None,
                    "scm_branch": None,
                    "extra_vars": None,
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
        assert result["workflow_launch"]["id"] == 42
        mock_manager.launch_resource.assert_called_once_with(
            "workflow_job_templates/10/launch",
            {},
            service="controller",
        )
        mock_manager.wait_for_completion.assert_not_called()

    def test_launch_with_wait_success(self, action_module):
        """Launch with wait=True should poll until completion."""
        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {"results": [{"id": 10, "name": "Test WJT", "ask_inventory_on_launch": False}]}
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
                    "name": "Test WJT",
                    "organization": None,
                    "inventory": None,
                    "wait": True,
                    "interval": 2.0,
                    "timeout": 600,
                    "limit": None,
                    "tags": None,
                    "skip_tags": None,
                    "scm_branch": None,
                    "extra_vars": None,
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
        """A workflow that finishes with 'failed' status should fail the task."""
        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {"results": [{"id": 10, "name": "Test WJT"}]}
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}
        mock_manager.wait_for_completion.return_value = {"id": 42, "status": "failed"}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "name": "Test WJT",
                    "organization": None,
                    "inventory": None,
                    "wait": True,
                    "interval": 2.0,
                    "timeout": None,
                    "limit": None,
                    "tags": None,
                    "skip_tags": None,
                    "scm_branch": None,
                    "extra_vars": None,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert result["status"] == "failed"
        assert result["id"] == 42

    def test_launch_with_wait_timeout(self, action_module):
        """A timed-out wait should fail but still report id/status."""
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import WaitTimeoutError

        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {"results": [{"id": 10, "name": "Test WJT"}]}
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}
        mock_manager.wait_for_completion.side_effect = WaitTimeoutError(
            "Timed out waiting after 10s",
            last_result={"id": 42, "status": "running"},
        )

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "name": "Test WJT",
                    "organization": None,
                    "inventory": None,
                    "wait": True,
                    "interval": 2.0,
                    "timeout": 10,
                    "limit": None,
                    "tags": None,
                    "skip_tags": None,
                    "scm_branch": None,
                    "extra_vars": None,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert "Timed out" in result["msg"]
        assert result["id"] == 42
        assert result["status"] == "running"

    def test_wjt_not_found(self, action_module):
        """Should fail if workflow job template not found."""
        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {"results": []}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "name": "Nonexistent",
                    "organization": None,
                    "inventory": None,
                    "wait": True,
                    "interval": 2.0,
                    "timeout": None,
                    "limit": None,
                    "tags": None,
                    "skip_tags": None,
                    "scm_branch": None,
                    "extra_vars": None,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert "Unable to find" in result["msg"]

    def test_prompt_on_launch_validation(self, action_module):
        """Should fail if fields are passed that aren't prompt-on-launch."""
        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "results": [
                {
                    "id": 10,
                    "name": "Test WJT",
                    "ask_inventory_on_launch": False,
                    "ask_limit_on_launch": False,
                    "ask_tags_on_launch": False,
                    "ask_skip_tags_on_launch": False,
                    "ask_scm_branch_on_launch": False,
                    "ask_variables_on_launch": False,
                    "survey_enabled": False,
                }
            ]
        }
        mock_manager.lookup_resource_id.return_value = 5

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "name": "Test WJT",
                    "organization": None,
                    "inventory": "My Inventory",
                    "wait": False,
                    "interval": 2.0,
                    "timeout": None,
                    "limit": "webservers",
                    "tags": None,
                    "skip_tags": None,
                    "scm_branch": None,
                    "extra_vars": {"key": "value"},
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert "inventory" in result["msg"]
        assert "limit" in result["msg"]
        assert "extra_vars" in result["msg"]

    def test_tags_comma_joined(self, action_module):
        """Tags should be comma-joined as job_tags in the launch payload."""
        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "results": [
                {
                    "id": 10,
                    "name": "Test WJT",
                    "ask_tags_on_launch": True,
                    "ask_skip_tags_on_launch": True,
                }
            ]
        }
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "name": "Test WJT",
                    "organization": None,
                    "inventory": None,
                    "wait": False,
                    "interval": 2.0,
                    "timeout": None,
                    "limit": None,
                    "tags": ["web", "deploy"],
                    "skip_tags": ["debug"],
                    "scm_branch": None,
                    "extra_vars": None,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["changed"] is True
        call_args = mock_manager.launch_resource.call_args
        payload = call_args[0][1]
        assert payload["job_tags"] == "web,deploy"
        assert payload["skip_tags"] == "debug"

    def test_inventory_fk_resolution(self, action_module):
        """Inventory name should be resolved to ID via lookup_resource_id with service=controller."""
        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "results": [
                {
                    "id": 10,
                    "name": "Test WJT",
                    "ask_inventory_on_launch": True,
                }
            ]
        }
        mock_manager.lookup_resource_id.return_value = 7
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "name": "Test WJT",
                    "organization": None,
                    "inventory": "Production",
                    "wait": False,
                    "interval": 2.0,
                    "timeout": None,
                    "limit": None,
                    "tags": None,
                    "skip_tags": None,
                    "scm_branch": None,
                    "extra_vars": None,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["changed"] is True
        mock_manager.lookup_resource_id.assert_called_once_with("inventories", "name", "Production", service="controller")
        call_args = mock_manager.launch_resource.call_args
        payload = call_args[0][1]
        assert payload["inventory"] == 7

    def test_organization_lookup_for_wjt(self, action_module):
        """Organization name should be resolved and used in WJT query."""
        mock_manager = MagicMock()
        mock_manager.lookup_resource_id.return_value = 3
        mock_manager.search_api.return_value = {"results": [{"id": 10, "name": "Test WJT"}]}
        mock_manager.launch_resource.return_value = {"id": 42, "status": "pending"}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "name": "Test WJT",
                    "organization": "Default",
                    "inventory": None,
                    "wait": False,
                    "interval": 2.0,
                    "timeout": None,
                    "limit": None,
                    "tags": None,
                    "skip_tags": None,
                    "scm_branch": None,
                    "extra_vars": None,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["changed"] is True
        mock_manager.lookup_resource_id.assert_called_once_with("organizations", "name", "Default")
        mock_manager.search_api.assert_called_once_with(
            "/api/controller/v2/workflow_job_templates/",
            query_params={"name": "Test WJT", "organization": 3},
        )
