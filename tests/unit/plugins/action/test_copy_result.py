"""Legacy copy result compatibility for Controller templates."""

from unittest.mock import MagicMock, patch

import pytest
from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.action.inventory import ActionModule as InventoryAction
from ansible_collections.ansible.platform.plugins.action.notification_template import ActionModule as NotificationAction
from ansible_collections.ansible.platform.plugins.action.workflow_job_template import ActionModule as WorkflowAction


@pytest.mark.parametrize("action_type", [NotificationAction, WorkflowAction, InventoryAction])
@pytest.mark.parametrize("existing", [False, True])
def test_copy_result_reports_whether_a_copy_was_created(action_type, existing):
    """A new copy reports true, while an existing destination reports false."""
    action = action_type.__new__(action_type)
    action._task = MagicMock()
    action._task.args = {"name": "destination", "copy_from": "123"}
    action._task.check_mode = False
    action._display = MagicMock()
    action._validate_action_input = MagicMock()
    manager = MagicMock()
    manager.search_api.return_value = {"results": [{"id": 7, "name": "destination"}] if existing else []}
    action._get_or_spawn_manager = MagicMock(return_value=(manager, None))
    with patch.object(ActionBase, "run", return_value={}):
        with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "id": 7}):
            result = action.run(task_vars={})

    assert result["copied"] is not existing
    assert result["changed"] is not existing
    assert manager.copy_resource.call_count == (0 if existing else 1)
