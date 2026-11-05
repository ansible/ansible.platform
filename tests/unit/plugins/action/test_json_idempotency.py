"""Regression tests for JSON object comparison in resource action plugins."""

from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.group import ActionModule as GroupActionModule
from ansible_collections.ansible.platform.plugins.action.host import ActionModule
from ansible_collections.ansible.platform.plugins.action.inventory_source import ActionModule as InventorySourceActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.job_template import AnsibleJobTemplate
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.job_template import JobTemplateTransformMixin_v2
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext


def _make_action(variables):
    action = ActionModule.__new__(ActionModule)
    action._task = MagicMock()
    action._task.args = {
        "name": "web-1",
        "inventory": "10",
        "variables": variables,
        "state": "present",
    }
    action._task.check_mode = False
    action._task.environment = []
    action._display = MagicMock()
    action._display.verbosity = 0
    action._connection = MagicMock()
    action._templar = MagicMock()
    return action


def _run_action(action, manager):
    with patch.object(ActionBase, "run", return_value={}):
        with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
            return action.run(task_vars={})


def test_equivalent_variables_do_not_update_existing_host():
    action = _make_action({"z": 2, "a": 1})
    manager = MagicMock()
    manager.execute.return_value = {
        "id": 17,
        "name": "web-1",
        "inventory": "10",
        "variables": '{"a": 1, "z": 2}',
    }

    result = _run_action(action, manager)

    assert result["changed"] is False
    manager.execute.assert_called_once()
    assert manager.execute.call_args.kwargs["operation"] == "find"


def test_changed_variables_update_existing_host():
    action = _make_action({"z": 3, "a": 1})
    manager = MagicMock()
    manager.execute.side_effect = [
        {
            "id": 17,
            "name": "web-1",
            "inventory": "10",
            "variables": '{"a": 1, "z": 2}',
        },
        {"id": 17, "name": "web-1", "inventory": "10", "variables": '{"a": 1, "z": 3}', "changed": True},
    ]

    result = _run_action(action, manager)

    assert result["changed"] is True
    assert [call.kwargs["operation"] for call in manager.execute.call_args_list] == ["find", "update"]


def test_json_object_fields_are_declared_for_comparison():
    fields = (
        (ActionModule, "variables"),
        (GroupActionModule, "variables"),
        (InventorySourceActionModule, "source_vars"),
    )

    for action_class, field in fields:
        action = action_class.__new__(action_class)
        desired = {"z": 2, "a": 1}
        current = '{"a": 1, "z": 2}'

        assert action._should_update({field: desired}, {field: current}) is False
        assert action._should_update({field: {"z": 3, "a": 1}}, {field: current}) is True


def test_direct_client_compares_transformed_json_fields_by_content():
    client = DirectHTTPClient.__new__(DirectHTTPClient)
    client._find_resource = MagicMock(return_value={"id": 17, "name": "template", "extra_vars": {"a": 1, "z": 2}})
    client._execute_operations = MagicMock()
    context = TransformContext(manager=None, session=None, cache={}, api_version="2", service="controller", operation="update")
    desired = AnsibleJobTemplate(name="template", extra_vars={"z": 2, "a": 1}, id=17)

    result = client._update_resource(desired, JobTemplateTransformMixin_v2, context)

    assert result["changed"] is False
    client._execute_operations.assert_not_called()
