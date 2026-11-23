"""Unit tests for controller_project project-sync handling."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
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

    result = module._refresh_project_sync_data(manager, {"id": 42, "name": "project"}, 42)

    assert result["id"] == 42
    assert result["scm_revision"] == "after-sync"
    assert result["summary_fields"] == {"current_update": {"id": 86}}
    manager.search_api.assert_called_once_with("/api/controller/v2/projects/42/", service="controller")


def test_refresh_project_sync_data_does_not_drop_existing_result_fields():
    module = _make_module()
    manager = MagicMock()
    manager.search_api.return_value = {"scm_revision": "after-sync"}

    result = module._refresh_project_sync_data(manager, {"id": 42, "name": "project", "description": "kept"}, 42)

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
    manager.search_api.side_effect = [
        {
            "id": 42,
            "scm_revision": "before",
            "summary_fields": {"current_update": {"id": 86}},
        },
        {
            "id": 42,
            "scm_revision": "after",
            "summary_fields": {"last_update": {"id": 86}},
        },
    ]
    manager.wait_for_completion.return_value = {"id": 86, "status": "successful", "scm_revision": "after"}
    action._client = manager

    with patch.object(
        BaseResourceActionPlugin,
        "run",
        return_value={"changed": True, "failed": False, "id": 42, "controller_project": {"id": 42}},
    ):
        result = action.run(task_vars={})

    assert not result["failed"]
    assert result["controller_project"]["scm_revision"] == "after"
    assert result["controller_project"]["summary_fields"] == {"last_update": {"id": 86}}
    assert manager.search_api.call_count == 2
    manager.wait_for_completion.assert_called_once_with("project_updates/86", timeout=None, interval=2.0, service="controller")


def test_handle_project_sync_rejects_failed_automatic_sync_after_refresh():
    module = _make_module()
    manager = MagicMock()
    result = {
        "changed": True,
        "controller_project": {
            "id": 42,
            "scm_type": "git",
            "summary_fields": {"last_update": {"id": 86, "status": "failed"}},
        },
    }

    with pytest.raises(ValueError, match="Automatic project sync finished with status 'failed'"):
        module._handle_project_sync(result, manager, 42, wait=True, update_project=False, interval=2.0, timeout=None, project_changed=True)

    manager.wait_for_completion.assert_not_called()


def test_handle_project_sync_ignores_prior_failed_sync():
    module = _make_module()
    manager = MagicMock()
    result = {
        "changed": True,
        "controller_project": {
            "id": 42,
            "scm_type": "git",
            "summary_fields": {"last_update": {"id": 86, "status": "failed"}},
        },
    }

    module._handle_project_sync(
        result,
        manager,
        42,
        wait=True,
        update_project=False,
        interval=2.0,
        timeout=None,
        project_changed=True,
        project_sync_before_update_id=86,
    )

    manager.wait_for_completion.assert_not_called()


def test_handle_project_sync_tolerates_null_summary_fields():
    module = _make_module()
    manager = MagicMock()
    result = {
        "controller_project": {
            "id": 42,
            "scm_revision": None,
            "summary_fields": None,
        }
    }

    module._handle_project_sync(result, manager, 42, wait=True, update_project=False, interval=2.0, timeout=None)

    manager.wait_for_completion.assert_not_called()


def test_handle_project_sync_reports_running_update_for_nowait_request():
    module = _make_module()
    manager = MagicMock()
    result = {
        "controller_project": {
            "id": 42,
            "summary_fields": {"current_update": {"id": 86}},
        }
    }

    with pytest.raises(ValueError, match="cannot schedule update_project with wait=false"):
        module._handle_project_sync(result, manager, 42, wait=False, update_project=True, interval=2.0, timeout=None)

    manager.launch_resource.assert_not_called()
    manager.wait_for_completion.assert_not_called()


def test_handle_project_sync_updates_requested_sync_after_existing_sync():
    module = _make_module()
    manager = MagicMock()
    manager.wait_for_completion.side_effect = [
        {"id": 86, "status": "successful"},
        {"id": 87, "status": "successful"},
    ]
    manager.launch_resource.return_value = {"id": 87}
    manager.search_api.side_effect = [
        {"scm_revision": "after-first", "summary_fields": {"last_update": {"id": 86}}},
        {"scm_revision": "after-second", "summary_fields": {"last_update": {"id": 87}}},
    ]
    result = {
        "controller_project": {
            "id": 42,
            "scm_revision": "before",
            "summary_fields": {"current_update": {"id": 86}},
        }
    }

    module._handle_project_sync(result, manager, 42, wait=True, update_project=True, interval=2.0, timeout=None)

    manager.launch_resource.assert_called_once_with("/api/controller/v2/projects/42/update/", {}, service="controller")
    assert manager.wait_for_completion.call_args_list[0].args[0] == "project_updates/86"
    assert manager.wait_for_completion.call_args_list[1].args[0] == "project_updates/87"
    assert result["controller_project"]["scm_revision"] == "after-second"
    assert result["controller_project"]["summary_fields"] == {"last_update": {"id": 87}}


@pytest.mark.parametrize(
    ("launch_result", "expected_update_url"),
    [
        ({"url": "project_updates/87/"}, "project_updates/87/"),
        ({"project_update": 87}, "project_updates/87"),
    ],
)
def test_handle_project_sync_uses_launched_update_reference(launch_result, expected_update_url):
    module = _make_module()
    manager = MagicMock()
    manager.launch_resource.return_value = launch_result
    manager.wait_for_completion.return_value = {"id": 87, "status": "successful"}
    manager.search_api.return_value = {"scm_revision": "after", "summary_fields": {}}
    result = {"controller_project": {"id": 42, "summary_fields": {}}}

    module._handle_project_sync(result, manager, 42, wait=True, update_project=True, interval=2.0, timeout=None)

    manager.wait_for_completion.assert_called_once_with(expected_update_url, timeout=None, interval=2.0, service="controller")


def test_handle_project_sync_rejects_launch_without_update_reference():
    module = _make_module()
    manager = MagicMock()
    manager.launch_resource.return_value = {}
    result = {"controller_project": {"id": 42, "summary_fields": {}}}

    with pytest.raises(ValueError, match="did not include a URL or project update identifier"):
        module._handle_project_sync(result, manager, 42, wait=True, update_project=True, interval=2.0, timeout=None)

    manager.wait_for_completion.assert_not_called()
