"""Cross-batch regressions for the failure patterns exposed by Batch 3."""

import json
from dataclasses import asdict
from importlib import import_module
from unittest.mock import MagicMock, patch

import pytest
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError, WaitTimeoutError

SAMPLES = {
    "organization": {"name": "Resource"},
    "workflow_job_template": {"name": "Resource"},
    "execution_environment": {"name": "Resource"},
    "group": {"name": "Resource", "inventory": "1"},
    "token": {},
    "job_wait": {"job_id": 1},
    "settings": {"settings": {}},
    "controller_settings": {"settings": {}},
    "notification_template": {"name": "Resource"},
    "job_launch": {"name": "Resource"},
    "inventory": {"name": "Resource", "organization": "1"},
    "host": {"name": "Resource", "inventory": "1"},
    "inventory_source_update": {"name": "Resource", "inventory": "1"},
    "schedule": {"name": "Resource"},
    "inventory_source": {"name": "Resource", "inventory": "1"},
    "project_update": {"name": "Resource"},
}


def make_action(module, args=None, check_mode=False):
    """Build an action while retaining its real argument validation."""
    cls = import_module("ansible_collections.ansible.platform.plugins.action." + module).ActionModule
    action = cls.__new__(cls)
    action._task = MagicMock(args=dict(SAMPLES.get(module, {}), **(args or {})), check_mode=check_mode)
    action._display = MagicMock()
    action._display.verbosity = 0
    action._client = MagicMock()
    return action


def transform_for(module):
    """Load the concrete transform for one of the reviewed resources."""
    service, version = ("gateway", "1") if module == "organization" else ("controller", "2")
    imported = import_module(f"ansible_collections.ansible.platform.plugins.plugin_utils.api.{service}.v{version}.{module}")
    return next(value for name, value in vars(imported).items() if name.endswith("TransformMixin_v" + version))


@pytest.mark.parametrize("module", SAMPLES)
def test_real_validation_retains_canonical_inputs_and_removes_alias_keys(module):
    """Check aliases through actual Ansible validation across both earlier batches."""
    action = make_action(module)
    baseline = action._validate_action_input()
    specs = baseline.argspec["argument_spec"]
    for canonical, spec in specs.items():
        if canonical in action._AUTH_PARAMS:
            continue
        for alias in spec.get("aliases", []):
            value = {"bool": False, "dict": {}, "list": []}.get(spec.get("type"), "Resource")
            args = dict(SAMPLES[module])
            args.pop(canonical, None)
            args[alias] = value
            action._task.args = args
            validated = action._validate_action_input().validated_params
            assert alias not in validated
            assert validated[canonical] == value


@pytest.mark.parametrize(
    "module",
    ["organization", "workflow_job_template", "execution_environment", "group", "notification_template", "inventory", "host", "inventory_source", "schedule"],
)
def test_empty_description_round_trip_does_not_predict_an_update(module):
    """Preserve stored empty descriptions when comparing repeated tasks."""
    action = make_action(module)
    transform = transform_for(module)
    raw = {"id": 7, "name": "Resource", "description": "", "inventory": 1, "organization": 1}
    manager = MagicMock()
    manager.search_api.return_value = {"id": 1, "name": "Resource"}
    manager.lookup_organization_names.return_value = ["Resource"]
    current = asdict(transform.from_api(raw, {"manager": manager}))
    assert current["description"] == ""
    assert not action._should_update({"description": ""}, current)


@pytest.mark.parametrize("field", ["scm_branch", "job_tags", "skip_tags", "limit"])
def test_schedule_empty_prompt_round_trip_is_idempotent(field):
    """Do not turn stored empty prompts into null and repeatedly PATCH them."""
    transform = transform_for("schedule")
    current = asdict(transform.from_api({"name": "Resource", field: ""}, {}))
    assert current[field] == ""
    assert not make_action("schedule")._should_update({field: ""}, current)


@pytest.mark.parametrize("field", ["scm_branch", "job_tags", "skip_tags", "limit"])
def test_schedule_explicit_empty_prompt_changes_inherited_null(field):
    """Distinguish template inheritance from an explicitly cleared override."""
    current = asdict(transform_for("schedule").from_api({"name": "Resource", field: None}, {}))
    assert make_action("schedule")._should_update({field: ""}, current)


@pytest.mark.parametrize(
    "module,field",
    [
        ("execution_environment", "credential"),
        ("schedule", "inventory"),
        ("schedule", "execution_environment"),
        ("inventory_source", "source_project"),
        ("inventory_source", "credential"),
        ("inventory_source", "execution_environment"),
        ("workflow_job_template", "inventory"),
        ("workflow_job_template", "webhook_credential"),
    ],
)
@pytest.mark.parametrize("operation", ["find", "delete"])
def test_unused_write_reference_does_not_block_find_or_delete(module, field, operation):
    """Do not mistake an invalid unused reference for an absent resource."""
    action = make_action(module)
    manager = MagicMock()
    manager.lookup_resource_id.side_effect = ValueError("unused reference must not be resolved")
    model = action.MODEL_CLASS(**dict(SAMPLES[module], **{field: "Missing Reference"}))
    data = transform_for(module).from_ansible_data(model, {"manager": manager, "operation": operation})
    assert getattr(data, field) is None
    manager.lookup_resource_id.assert_not_called()


@pytest.mark.parametrize(
    "module,field", [("schedule", "inventory"), ("schedule", "execution_environment"), ("workflow_job_template_node", "execution_environment")]
)
def test_nullable_reference_clear_is_idempotent_after_api_returns_null(module, field):
    """Treat legacy empty relationship clears as already satisfied by null."""
    action = make_action(module)
    assert not action._should_update({field: ""}, {field: None})
    assert action._should_update({field: ""}, {field: "Existing"})


@pytest.mark.parametrize("field", ["inventory", "execution_environment"])
def test_schedule_preserves_explicit_reference_clear_in_update_payload(field):
    """Send empty relationship clears without looking up an empty name."""
    action = make_action("schedule")
    manager = MagicMock()
    model = action.MODEL_CLASS(name="Resource", **{field: ""})
    data = transform_for("schedule").from_ansible_data(model, {"manager": manager, "operation": "update"})
    assert getattr(data, field) == ""
    manager.lookup_resource_id.assert_not_called()


@pytest.mark.parametrize("changed", [False, True])
@pytest.mark.parametrize("field,alias", [("labels", "labels"), ("survey_spec", "survey_spec"), ("survey_spec", "survey")])
def test_workflow_template_dry_run_compares_associations_and_survey(field, alias, changed):
    """Preserve survey aliases and compare current values instead of assuming change."""
    desired = ["Existing"] if field == "labels" else {"name": "Survey", "description": "", "spec": []}
    action = make_action("workflow_job_template", {alias: desired}, check_mode=True)
    action._client.manage_associations.return_value = changed
    action._client.manage_sub_resource.return_value = changed
    with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "id": 7}):
        result = action.run(task_vars={})
    assert result["changed"] is changed
    method = action._client.manage_associations if field == "labels" else action._client.manage_sub_resource
    assert method.call_args.kwargs["check_mode"] is True
    assert method.call_args.args[3] == desired


@pytest.mark.parametrize("missing,check_mode", [(True, True), (True, False), (False, True)])
def test_workflow_template_only_predicts_expected_missing_associations(missing, check_mode):
    """Predict a dependency created earlier in check mode while propagating real errors."""
    action = make_action("workflow_job_template", {"labels": ["New Label"]}, check_mode=check_mode)
    message = "Resource 'labels' with name=New Label not found" if missing else "Permission denied"
    action._client.manage_associations.side_effect = ValueError(message)
    with patch.object(BaseResourceActionPlugin, "run", return_value={"changed": False, "id": 7}):
        result = action.run(task_vars={})
    assert result.get("failed", False) is not (missing and check_mode)
    assert result["changed"] is (missing and check_mode)


@pytest.mark.parametrize("module", ["job_launch", "inventory_source_update", "workflow_launch"])
@pytest.mark.parametrize("timeout,expected", [(None, -1.0), (0, -1.0), (-1, 0.0), (-5, 0.0), (30, 30.0)])
def test_launch_wait_timeout_matches_legacy_rules(module, timeout, expected):
    """Preserve unlimited zero/omitted waits and immediate negative-timeout waits."""
    action = make_action(module, {"name": "Resource", "wait": True, "timeout": timeout})
    manager = action._client
    manager.lookup_resource_id.return_value = 1
    manager.search_api.return_value = {"results": [{"id": 1}]}
    manager.launch_resource.return_value = {"id": 42, "status": "pending"}
    manager.wait_for_completion.return_value = {"id": 42, "status": "successful"}
    with patch("ansible.plugins.action.ActionBase.run", return_value={}), patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
        result = action.run(task_vars={})
    assert not result.get("failed")
    assert manager.wait_for_completion.call_args.kwargs["timeout"] == expected


@pytest.mark.parametrize("module", ["job_launch", "inventory_source_update", "workflow_launch"])
@pytest.mark.parametrize("status", ["running", "successful"])
def test_negative_launch_timeout_polls_once_using_real_waiter(module, status):
    """Stop after the first unfinished response while accepting a terminal job."""
    action = make_action(module, {"name": "Resource", "wait": True, "timeout": -5})
    manager = action._client
    manager.lookup_resource_id.return_value = 1
    manager.search_api.return_value = {"results": [{"id": 1}]}
    manager.launch_resource.return_value = {"id": 42, "status": "pending"}
    client = DirectHTTPClient.__new__(DirectHTTPClient)
    client.base_url = "https://gateway.example"
    client.api_versions = {"controller": "2"}
    client._get_json = MagicMock(side_effect=[{"id": 42, "status": status}, AssertionError("Waiter polled more than once")])
    manager.wait_for_completion = client.wait_for_completion
    with (
        patch("ansible.plugins.action.ActionBase.run", return_value={}),
        patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)),
        patch("ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client.time.sleep") as sleep,
    ):
        result = action.run(task_vars={})
    assert result["changed"] is True
    assert result.get("failed", False) is (status == "running"), result.get("msg")
    assert result["id"] == 42
    assert result["status"] == status, result.get("msg")
    client._get_json.assert_called_once()
    manager.launch_resource.assert_called_once()
    sleep.assert_not_called()


@pytest.mark.parametrize("timed_out", [False, True])
def test_inventory_update_retains_timestamp_using_documented_platform_key(timed_out):
    """Preserve timing for both completed and timed-out inventory updates."""
    action = make_action("inventory_source_update", {"wait": True})
    manager = action._client
    manager.lookup_resource_id.return_value = 1
    manager.search_api.return_value = {"results": [{"id": 1}]}
    manager.launch_resource.return_value = {"id": 42, "status": "pending"}
    data = {"id": 42, "status": "successful", "elapsed": 2.0, "started": "2026-01-01T00:00:00Z", "finished": "2026-01-01T00:00:02Z"}
    manager.wait_for_completion.return_value = data
    if timed_out:
        data.update(status="running", finished=None)
        manager.wait_for_completion.side_effect = WaitTimeoutError("Timed out", last_result=data)
    with patch("ansible.plugins.action.ActionBase.run", return_value={}), patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
        result = action.run(task_vars={})
    assert result["finished"] is (not timed_out)
    assert result["finished_at"] == data["finished"]
    assert result["elapsed"] == 2.0


@pytest.mark.parametrize("persistent", [False, True])
@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    "current,desired,changed",
    [({}, {}, False), ({"name": "Old"}, {}, True), ({"name": "Same"}, {"name": "Same"}, False), ({"name": "Old"}, {"name": "New"}, True)],
)
def test_subresource_comparison_and_clear_idempotency(persistent, check_mode, current, desired, changed):
    """Compare both transports, preserving live writes and preventing dry-run writes."""
    from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService

    client = (PlatformService if persistent else DirectHTTPClient).__new__(PlatformService if persistent else DirectHTTPClient)
    client.base_url = "https://gateway.example"
    client.request_timeout = 10.0
    client.verify_ssl = False
    client._ensure_authenticated = MagicMock()
    client.record_activity = MagicMock()
    client.session = MagicMock()
    client.session.get.return_value.status_code = 200
    client.session.get.return_value.json.return_value = current
    client._make_request = MagicMock()
    client._make_request.return_value.read.return_value = json.dumps(current).encode()
    assert client.manage_sub_resource("/api/controller/v2/workflow_job_templates", 7, "survey_spec", desired, check_mode=check_mode) is changed
    if check_mode or not changed:
        client.session.post.assert_not_called()
        client.session.delete.assert_not_called()
    elif persistent:
        method = client.session.delete if desired == {} else client.session.post
        method.assert_called_once()
    if not persistent:
        expected_methods = ["GET"]
        if changed and not check_mode:
            expected_methods.append("DELETE" if desired == {} else "POST")
        assert [call.args[0] for call in client._make_request.call_args_list] == expected_methods


def test_subresource_dry_run_flag_is_forwarded_through_rpc():
    """Keep the persistent action on the same comparison path as direct mode."""
    from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient

    client = ManagerRPCClient.__new__(ManagerRPCClient)
    client.service_proxy = MagicMock()
    client.service_proxy.manage_sub_resource.return_value = True
    assert client.manage_sub_resource("/api/controller/v2/workflow_job_templates", 7, "survey_spec", {}, check_mode=True)
    client.service_proxy.manage_sub_resource.assert_called_once_with("/api/controller/v2/workflow_job_templates", 7, "survey_spec", {}, True)


@pytest.mark.parametrize("persistent", [False, True])
def test_subresource_clear_dry_run_handles_absent_survey(persistent):
    """Treat a missing survey as an unchanged dry-run clear."""
    from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService

    client_type = PlatformService if persistent else DirectHTTPClient
    client = client_type.__new__(client_type)
    client.base_url = "https://gateway.example"
    client.request_timeout = 10.0
    client.verify_ssl = False
    client._ensure_authenticated = MagicMock()
    client.record_activity = MagicMock()
    client.session = MagicMock()
    client.session.get.return_value.status_code = 404
    client._make_request = MagicMock(side_effect=APIError("Not found", status_code=404))
    assert client.manage_sub_resource("/api/controller/v2/workflow_job_templates", 7, "survey_spec", {}, check_mode=True) is False
    client.session.delete.assert_not_called()
