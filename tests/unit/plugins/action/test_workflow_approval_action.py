"""Tests for workflow approval request construction and orchestration."""

from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.action.workflow_approval import ActionModule


def _make_action():
    action = ActionModule.__new__(ActionModule)
    action._task = MagicMock()
    action._task.check_mode = False
    action._display = MagicMock()
    action._display.verbosity = 0
    return action


def _assert_action_request(action_name, related_job):
    action = _make_action()
    manager = MagicMock()
    node = {"summary_fields": {"job": {"type": "workflow_approval", "status": "pending", "id": 71}}}
    if related_job is not None:
        node["related"] = {"job": related_job}
    manager.search_api.return_value = {"results": [node]}
    prepared = {
        "result": {},
        "validated_params": {
            "workflow_job_id": 42,
            "name": "Deploy Approval",
            "action": action_name,
            "timeout": 10,
            "interval": 1.0,
        },
        "manager": manager,
    }

    with patch.object(action, "_prepare_action", return_value=prepared):
        result = action.run(task_vars={})

    assert not result.get("failed", False)
    manager.search_api.assert_called_once_with(
        "/api/controller/v2/workflow_jobs/42/workflow_nodes/",
        query_params={"job__name": "Deploy Approval"},
    )
    manager.direct_request.assert_called_once_with(
        "POST",
        f"/api/controller/v2/workflow_approvals/71/{action_name}/",
    )


def test_approval_action_uses_declared_poll_and_action_operations():
    for action_name in ("approve", "deny"):
        for related_job in ("/api/controller/v2/workflow_approvals/71/", None):
            _assert_action_request(action_name, related_job)
