"""Unit tests for controller_project project-sync handling."""

from __future__ import annotations

from unittest.mock import MagicMock

from ansible.playbook.task import Task
from ansible_collections.ansible.platform.plugins.action.controller_project import ActionModule


def _make_module():
    task = MagicMock(spec=Task)
    task.args = {}
    task.check_mode = False
    task.async_val = 0
    task.environment = []
    return ActionModule(
        task=task,
        connection=MagicMock(),
        play_context=MagicMock(),
        loader=MagicMock(),
        templar=MagicMock(),
        shared_loader_obj=MagicMock(),
    )


def test_refresh_project_sync_data_preserves_raw_controller_metadata():
    module = _make_module()
    manager = MagicMock()
    manager.search_api.return_value = {
        "id": 42,
        "scm_revision": "after-sync",
        "summary_fields": {"current_update": {"id": 86}},
    }

    result = module._refresh_project_sync_data(
        manager, {"id": 42, "name": "project"}, 42
    )

    assert result["id"] == 42
    assert result["scm_revision"] == "after-sync"
    assert result["summary_fields"] == {"current_update": {"id": 86}}
    manager.search_api.assert_called_once_with(
        "/api/controller/v2/projects/42/", service="controller"
    )


def test_refresh_project_sync_data_does_not_drop_existing_result_fields():
    module = _make_module()
    manager = MagicMock()
    manager.search_api.return_value = {"scm_revision": "after-sync"}

    result = module._refresh_project_sync_data(
        manager, {"id": 42, "name": "project", "description": "kept"}, 42
    )

    assert result == {
        "id": 42,
        "name": "project",
        "description": "kept",
        "scm_revision": "after-sync",
    }


def test_run_refetches_sync_metadata_before_waiting():
    from unittest.mock import patch

    from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin

    action = _make_module()
    action._task.args = {"name": "project", "state": "present", "wait": True}
    manager = MagicMock()
    manager.search_api.return_value = {
        "id": 42,
        "scm_revision": "before",
        "summary_fields": {"current_update": {"id": 86}},
    }
    manager.wait_for_completion.return_value = {"id": 86, "status": "successful", "scm_revision": "after"}
    action._client = manager

    with patch.object(
        BaseResourceActionPlugin,
        "run",
        return_value={"changed": True, "failed": False, "id": 42, "controller_project": {"id": 42}},
    ):
        result = action.run(task_vars={})

    assert not result["failed"]
    manager.search_api.assert_called_once_with(
        "/api/controller/v2/projects/42/", service="controller"
    )
    manager.wait_for_completion.assert_called_once_with(
        "project_updates/86", timeout=None, interval=2.0, service="controller"
    )
