"""Unit tests for controller_job_wait action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock, patch

import pytest
from ansible_collections.ansible.platform.plugins.action.controller_job_wait import (
    JOB_TYPE_ENDPOINTS,
    ActionModule,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError

MOCK_DOCUMENTATION = """
---
module: controller_job_wait
options:
  job_id:
    type: int
    required: true
  job_type:
    type: str
    default: jobs
    choices: ['project_updates', 'jobs', 'inventory_updates', 'workflow_jobs']
  timeout:
    type: int
  interval:
    type: float
    default: 2
extends_documentation_fragment: ansible.platform.auth
"""


@pytest.fixture
def action_module():
    """Create a minimal ActionModule for testing."""
    task = MagicMock()
    task.args = {}
    task.check_mode = False
    task.async_val = 0
    connection = MagicMock()
    play_context = MagicMock()
    loader = MagicMock()
    templar = MagicMock()
    shared_loader_obj = MagicMock()
    module = ActionModule(
        task=task,
        connection=connection,
        play_context=play_context,
        loader=loader,
        templar=templar,
        shared_loader_obj=shared_loader_obj,
    )
    return module


class TestJobTypeEndpoints:
    """Verify endpoint mapping covers all legacy job_type choices."""

    def test_all_job_types_mapped(self):
        expected = {"jobs", "project_updates", "inventory_updates", "workflow_jobs"}
        assert set(JOB_TYPE_ENDPOINTS.keys()) == expected

    def test_jobs_endpoint(self):
        assert JOB_TYPE_ENDPOINTS["jobs"] == "/api/controller/v2/jobs"

    def test_project_updates_endpoint(self):
        assert JOB_TYPE_ENDPOINTS["project_updates"] == "/api/controller/v2/project_updates"

    def test_inventory_updates_endpoint(self):
        assert JOB_TYPE_ENDPOINTS["inventory_updates"] == "/api/controller/v2/inventory_updates"

    def test_workflow_jobs_endpoint(self):
        assert JOB_TYPE_ENDPOINTS["workflow_jobs"] == "/api/controller/v2/workflow_jobs"


class TestActionModuleAttributes:
    """Verify class-level attributes."""

    def test_module_name(self):
        assert ActionModule.MODULE_NAME == "controller_job_wait"

    def test_model_class_is_none(self):
        assert ActionModule.MODEL_CLASS is None


class TestCheckMode:
    """Verify check mode short-circuits without API calls."""

    @patch.object(ActionModule, "_get_or_spawn_manager")
    @patch.object(ActionModule, "_get_documentation")
    def test_check_mode_returns_unchanged(self, mock_doc, mock_manager, action_module):
        action_module._task.check_mode = True
        action_module._task.args = {"job_id": 42, "job_type": "jobs"}

        mock_doc.return_value = MOCK_DOCUMENTATION
        mock_manager.return_value = (MagicMock(), None)

        result = action_module.run(task_vars={})

        assert result["changed"] is False
        assert result["id"] == 42
        assert result["status"] == "unknown"
        mock_manager.return_value[0].wait_for_resource.assert_not_called()


class TestWaitSuccess:
    """Verify successful wait scenarios."""

    @patch.object(ActionModule, "_get_or_spawn_manager")
    @patch.object(ActionModule, "_get_documentation")
    def test_successful_job(self, mock_doc, mock_manager, action_module):
        action_module._task.args = {"job_id": 99}

        mock_doc.return_value = MOCK_DOCUMENTATION

        manager = MagicMock()
        manager.wait_for_resource.return_value = {
            "id": 99,
            "status": "successful",
            "elapsed": 10.5,
            "started": "2025-01-01T00:00:00Z",
            "finished": "2025-01-01T00:00:10Z",
        }
        mock_manager.return_value = (manager, None)

        result = action_module.run(task_vars={})

        assert result["changed"] is False
        assert result.get("failed") is not True
        assert result["id"] == 99
        assert result["status"] == "successful"
        assert result["elapsed"] == 10.5
        manager.wait_for_resource.assert_called_once_with(
            base_path="/api/controller/v2/jobs",
            resource_id=99,
            timeout=None,
            interval=2,
        )


class TestWaitFailure:
    """Verify failure handling."""

    @patch.object(ActionModule, "_get_or_spawn_manager")
    @patch.object(ActionModule, "_get_documentation")
    def test_failed_job(self, mock_doc, mock_manager, action_module):
        action_module._task.args = {"job_id": 100}

        mock_doc.return_value = MOCK_DOCUMENTATION

        manager = MagicMock()
        manager.wait_for_resource.return_value = {
            "id": 100,
            "status": "failed",
            "elapsed": 5.0,
            "started": "2025-01-01T00:00:00Z",
            "finished": "2025-01-01T00:00:05Z",
            "failed": True,
        }
        mock_manager.return_value = (manager, None)

        result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert result["status"] == "failed"
        assert "finished with status: failed" in result["msg"]

    @patch.object(ActionModule, "_get_or_spawn_manager")
    @patch.object(ActionModule, "_get_documentation")
    def test_timeout(self, mock_doc, mock_manager, action_module):
        action_module._task.args = {"job_id": 101, "timeout": 30}

        mock_doc.return_value = MOCK_DOCUMENTATION

        manager = MagicMock()
        manager.wait_for_resource.side_effect = WaitTimeoutError(
            message="Timed out waiting for job 101 (last status: running)",
            last_result={"id": 101, "status": "running", "elapsed": 30.0, "started": "2025-01-01T00:00:00Z", "finished": None},
            timeout_seconds=30,
        )
        mock_manager.return_value = (manager, None)

        result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert result["id"] == 101
        assert result["status"] == "running"
        assert "Timed out" in result["msg"]

    @patch.object(ActionModule, "_get_or_spawn_manager")
    @patch.object(ActionModule, "_get_documentation")
    def test_not_found(self, mock_doc, mock_manager, action_module):
        action_module._task.args = {"job_id": 999}

        mock_doc.return_value = MOCK_DOCUMENTATION

        manager = MagicMock()
        manager.wait_for_resource.side_effect = ValueError("Resource not found")
        mock_manager.return_value = (manager, None)

        result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert "does not exist" in result["msg"]
