"""Unit tests for workflow_node_wait action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def action_module():
    """Create a minimally-initialized ActionModule for testing."""
    from ansible_collections.ansible.platform.plugins.action.workflow_node_wait import ActionModule

    module = ActionModule.__new__(ActionModule)
    module.MODULE_NAME = "workflow_node_wait"
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


class TestWorkflowNodeWaitActionModule:
    """Tests for workflow_node_wait action plugin."""

    def test_module_name(self, action_module):
        assert action_module.MODULE_NAME == "workflow_node_wait"

    def test_model_class(self):
        from ansible_collections.ansible.platform.plugins.action.workflow_node_wait import ActionModule
        from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.workflow_node_wait import AnsibleWorkflowNodeWait

        assert ActionModule.MODEL_CLASS is AnsibleWorkflowNodeWait

    @patch("ansible_collections.ansible.platform.plugins.action.workflow_node_wait.time")
    def test_check_mode_waits_for_node_completion(self, mock_time, action_module):
        action_module._task.check_mode = True
        mock_time.time.side_effect = [0.0, 0.5, 1.0]

        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "count": 1,
            "results": [{"id": 100, "related": {"job": "/api/controller/v2/jobs/55/"}}],
        }
        mock_manager.wait_for_completion.return_value = {"id": 55, "status": "successful", "elapsed": 1.0}
        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "workflow_job_id": 42,
                    "name": "Approval Step",
                    "interval": 1.0,
                    "timeout": 10,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["changed"] is False
        assert result["status"] == "successful"
        mock_manager.search_api.assert_called_once_with(
            "workflow_jobs/42/workflow_nodes/",
            query_params={"job__name": "Approval Step"},
            service="controller",
        )
        mock_manager.wait_for_completion.assert_called_once()

    def test_missing_workflow_job_id(self, action_module):
        mock_manager = MagicMock()
        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "workflow_job_id": None,
                    "name": "Step",
                    "interval": 1.0,
                    "timeout": 10,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert "workflow_job_id" in result["msg"]

    def test_missing_name(self, action_module):
        mock_manager = MagicMock()
        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "workflow_job_id": 42,
                    "name": "",
                    "interval": 1.0,
                    "timeout": 10,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert "name" in result["msg"]

    @pytest.mark.parametrize("interval", [0, -1])
    def test_invalid_interval_fails_before_search(self, action_module, interval):
        mock_manager = MagicMock()
        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {"workflow_job_id": 42, "name": "Deploy Step", "interval": interval, "timeout": 10},
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert result["msg"] == "interval must be greater than 0"
        mock_manager.search_api.assert_not_called()
        mock_manager.wait_for_completion.assert_not_called()

    @patch("ansible_collections.ansible.platform.plugins.action.workflow_node_wait.time")
    def test_node_found_immediately_job_succeeds(self, mock_time, action_module):
        mock_time.time.side_effect = [0.0, 0.5, 1.0]

        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "count": 1,
            "results": [
                {
                    "id": 100,
                    "related": {"job": "/api/controller/v2/jobs/55/"},
                    "summary_fields": {"job": {"id": 55, "status": "pending"}},
                }
            ],
        }
        mock_manager.wait_for_completion.return_value = {
            "id": 55,
            "status": "successful",
            "elapsed": 5.0,
        }

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "workflow_job_id": 42,
                    "name": "Deploy Step",
                    "interval": 1.0,
                    "timeout": 120,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["changed"] is False
        assert result["id"] == 55
        assert result["status"] == "successful"
        assert result["elapsed"] == 5.0
        assert result.get("failed") is not True
        mock_manager.search_api.assert_called_once()
        mock_manager.wait_for_completion.assert_called_once()
        call_kwargs = mock_manager.wait_for_completion.call_args[1]
        assert call_kwargs["resource_url"] == "jobs/55/"
        assert call_kwargs["interval"] == 1.0
        assert call_kwargs["service"] == "controller"
        assert call_kwargs["timeout"] <= 120.0

    @patch("ansible_collections.ansible.platform.plugins.action.workflow_node_wait.time")
    def test_node_found_after_polling(self, mock_time, action_module):
        mock_time.time.side_effect = [0.0, 1.0, 2.0, 3.0, 4.0]

        mock_manager = MagicMock()
        mock_manager.search_api.side_effect = [
            {"count": 0, "results": []},
            {"count": 0, "results": []},
            {
                "count": 1,
                "results": [
                    {
                        "id": 100,
                        "related": {"job": "/api/controller/v2/jobs/55/"},
                    }
                ],
            },
        ]
        mock_manager.wait_for_completion.return_value = {
            "id": 55,
            "status": "successful",
            "elapsed": 3.0,
        }

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "workflow_job_id": 42,
                    "name": "Build Step",
                    "interval": 1.0,
                    "timeout": 120,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["changed"] is False
        assert result["id"] == 55
        assert result["status"] == "successful"
        assert mock_manager.search_api.call_count == 3
        assert mock_time.sleep.call_count == 2

    @patch("ansible_collections.ansible.platform.plugins.action.workflow_node_wait.time")
    def test_phase1_timeout(self, mock_time, action_module):
        mock_time.time.side_effect = [0.0, 5.0, 11.0]

        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {"count": 0, "results": []}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "workflow_job_id": 42,
                    "name": "Missing Step",
                    "interval": 1.0,
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
        assert "Missing Step" in result["msg"]

    @patch("ansible_collections.ansible.platform.plugins.action.workflow_node_wait.time")
    def test_expired_phase1_timeout_is_clamped_before_phase2(self, mock_time, action_module):
        mock_time.time.side_effect = [0.0, 9.5, 10.5]

        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "count": 1,
            "results": [{"id": 100, "related": {"job": "/api/controller/v2/jobs/55/"}}],
        }
        mock_manager.wait_for_completion.return_value = {"id": 55, "status": "successful", "elapsed": 0.0}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {"workflow_job_id": 42, "name": "Deploy Step", "interval": 1.0, "timeout": 10},
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["status"] == "successful"
        assert mock_manager.wait_for_completion.call_args.kwargs["timeout"] == 0.0

    @patch("ansible_collections.ansible.platform.plugins.action.workflow_node_wait.time")
    def test_zero_timeout_is_bounded(self, mock_time, action_module):
        mock_time.time.side_effect = [0.0, 0.0]

        mock_manager = MagicMock()
        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {"workflow_job_id": 42, "name": "Deploy Step", "interval": 1.0, "timeout": 0},
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert "Timed out" in result["msg"]
        mock_manager.search_api.assert_not_called()
        mock_manager.wait_for_completion.assert_not_called()

    @pytest.mark.parametrize("timeout", [None, -1])
    @patch("ansible_collections.ansible.platform.plugins.action.workflow_node_wait.time")
    def test_none_and_negative_timeouts_are_preserved(self, mock_time, timeout, action_module):
        mock_time.time.side_effect = [0.0, 0.5]

        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "count": 1,
            "results": [{"id": 100, "related": {"job": "/api/controller/v2/jobs/55/"}}],
        }
        mock_manager.wait_for_completion.return_value = {"id": 55, "status": "successful", "elapsed": 0.5}

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {"workflow_job_id": 42, "name": "Deploy Step", "interval": 1.0, "timeout": timeout},
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["status"] == "successful"
        assert mock_manager.wait_for_completion.call_args.kwargs["timeout"] == timeout

    @patch("ansible_collections.ansible.platform.plugins.action.workflow_node_wait.time")
    def test_job_fails(self, mock_time, action_module):
        mock_time.time.side_effect = [0.0, 0.5, 1.0]

        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "count": 1,
            "results": [
                {
                    "id": 100,
                    "related": {"job": "/api/controller/v2/jobs/55/"},
                }
            ],
        }
        mock_manager.wait_for_completion.return_value = {
            "id": 55,
            "status": "failed",
            "elapsed": 2.0,
        }

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "workflow_job_id": 42,
                    "name": "Failing Step",
                    "interval": 1.0,
                    "timeout": 120,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert result["status"] == "failed"
        assert "Failing Step" in result["msg"]

    @patch("ansible_collections.ansible.platform.plugins.action.workflow_node_wait.time")
    def test_phase2_timeout(self, mock_time, action_module):
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError

        mock_time.time.side_effect = [0.0, 0.5, 1.0]

        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "count": 1,
            "results": [
                {
                    "id": 100,
                    "related": {"job": "/api/controller/v2/jobs/55/"},
                }
            ],
        }
        mock_manager.wait_for_completion.side_effect = WaitTimeoutError(
            "Timed out waiting after 10s",
            last_result={"id": 55, "status": "running", "elapsed": 10.0},
        )

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "workflow_job_id": 42,
                    "name": "Slow Step",
                    "interval": 1.0,
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
        assert result["id"] == 55
        assert result["status"] == "running"

    @patch("ansible_collections.ansible.platform.plugins.action.workflow_node_wait.time")
    def test_node_no_related_job(self, mock_time, action_module):
        """Node without a related job URL (e.g. approval node) returns node data directly."""
        mock_time.time.side_effect = [0.0, 0.5]

        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "count": 1,
            "results": [
                {
                    "id": 100,
                    "related": {},
                    "summary_fields": {"job": {"id": 100, "status": "pending"}},
                }
            ],
        }

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "workflow_job_id": 42,
                    "name": "Approval Node",
                    "interval": 1.0,
                    "timeout": 120,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["changed"] is False
        assert result["id"] == 100
        mock_manager.wait_for_completion.assert_not_called()

    @patch("ansible_collections.ansible.platform.plugins.action.workflow_node_wait.time")
    def test_query_params_pass_job_name(self, mock_time, action_module):
        mock_time.time.side_effect = [0.0, 0.5, 1.0]

        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "count": 1,
            "results": [
                {
                    "id": 100,
                    "related": {"job": "/api/controller/v2/jobs/55/"},
                }
            ],
        }
        mock_manager.wait_for_completion.return_value = {
            "id": 55,
            "status": "successful",
            "elapsed": 1.0,
        }

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "workflow_job_id": 99,
                    "name": "My Node",
                    "interval": 1.0,
                    "timeout": 120,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            action_module.run(task_vars={})

        mock_manager.search_api.assert_called_with(
            "workflow_jobs/99/workflow_nodes/",
            query_params={"job__name": "My Node"},
            service="controller",
        )

    @patch("ansible_collections.ansible.platform.plugins.action.workflow_node_wait.time")
    def test_url_prefix_stripping(self, mock_time, action_module):
        """Job URL prefix /api/controller/v2/ should be stripped for wait_for_completion."""
        mock_time.time.side_effect = [0.0, 0.5, 1.0]

        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "count": 1,
            "results": [
                {
                    "id": 100,
                    "related": {"job": "/api/controller/v2/workflow_jobs/77/"},
                }
            ],
        }
        mock_manager.wait_for_completion.return_value = {
            "id": 77,
            "status": "successful",
            "elapsed": 1.0,
        }

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "workflow_job_id": 42,
                    "name": "WF Node",
                    "interval": 1.0,
                    "timeout": 120,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            action_module.run(task_vars={})

        call_kwargs = mock_manager.wait_for_completion.call_args
        assert call_kwargs[1]["resource_url"] == "workflow_jobs/77/"

    @patch("ansible_collections.ansible.platform.plugins.action.workflow_node_wait.time")
    def test_canceled_status_is_failure(self, mock_time, action_module):
        mock_time.time.side_effect = [0.0, 0.5, 1.0]

        mock_manager = MagicMock()
        mock_manager.search_api.return_value = {
            "count": 1,
            "results": [
                {
                    "id": 100,
                    "related": {"job": "/api/controller/v2/jobs/55/"},
                }
            ],
        }
        mock_manager.wait_for_completion.return_value = {
            "id": 55,
            "status": "canceled",
            "elapsed": 1.0,
        }

        with patch.object(action_module, "_prepare_action") as mock_prepare:
            mock_prepare.return_value = {
                "result": {},
                "validated_params": {
                    "workflow_job_id": 42,
                    "name": "Canceled Step",
                    "interval": 1.0,
                    "timeout": 120,
                },
                "resource_data": {},
                "write_only_data": {},
                "manager": mock_manager,
                "argspec": {},
            }
            result = action_module.run(task_vars={})

        assert result["failed"] is True
        assert result["status"] == "canceled"
