# (c) 2026 Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the job_cancel action plugin."""

from __future__ import absolute_import, division, print_function

from unittest.mock import MagicMock, patch

import pytest
from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.job_cancel import ActionModule


@pytest.fixture
def action_module():
    action = ActionModule.__new__(ActionModule)
    action._display = MagicMock()
    action._display.verbosity = 0
    action._task = MagicMock()
    action._task.args = {}
    action._task.check_mode = False
    return action


class TestJobCancelAction:
    @pytest.mark.parametrize("job_id", [0, -1])
    def test_rejects_non_positive_job_id_before_check_mode(self, action_module, job_id):
        action_module._task.check_mode = True
        manager = MagicMock()
        prepared = {"result": {}, "validated_params": {"job_id": job_id}, "manager": manager}

        with patch.object(action_module, "_prepare_action", return_value=prepared):
            result = action_module.run(task_vars={})

        assert result == {"failed": True, "msg": "job_id must be a positive integer"}
        manager.cancel_resource.assert_not_called()

    def test_missing_job_id_is_rejected_by_shared_validation(self, action_module):
        action_module._task.args = {}
        argspec = {"argument_spec": {"job_id": {"type": "int", "required": True}}}

        with patch.object(action_module, "_get_documentation", return_value="documentation"):
            with patch.object(action_module, "_build_argspec_from_docs", return_value=argspec):
                with pytest.raises(AnsibleError, match="job_id"):
                    action_module._validate_action_input()

    def test_valid_job_id_keeps_check_mode_behavior(self, action_module):
        action_module._task.check_mode = True
        manager = MagicMock()
        prepared = {"result": {}, "validated_params": {"job_id": 42}, "manager": manager}

        with patch.object(action_module, "_prepare_action", return_value=prepared):
            result = action_module.run(task_vars={})

        assert result == {
            "changed": True,
            "id": 42,
            "status": "cancel would be attempted (check mode)",
        }
        manager.cancel_resource.assert_not_called()

    def test_valid_job_id_keeps_api_behavior(self, action_module):
        manager = MagicMock()
        manager.cancel_resource.return_value = {"changed": True, "status": "canceled"}
        prepared = {"result": {}, "validated_params": {"job_id": 42}, "manager": manager}

        with patch.object(action_module, "_prepare_action", return_value=prepared):
            result = action_module.run(task_vars={})

        assert result == {"changed": True, "status": "canceled"}
        manager.cancel_resource.assert_called_once_with(
            resource_id=42,
            cancel_endpoint_path="jobs",
            fail_if_not_running=False,
            service="controller",
        )
