"""Wire-level contracts for migrated Controller and EDA resources.

These tests call the public client ``execute`` API and capture the HTTP
transport. The expected path, method, and body are migration contracts; the
test does not call the client's private CRUD or request-building helpers.
"""

from __future__ import annotations

import json
import threading
import unittest
import uuid
from unittest.mock import MagicMock
from urllib.parse import urlencode

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.loader import DynamicClassLoader
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry import APIVersionRegistry

BASE_URL = "https://gateway.example"
CONTRACT_TOKEN = uuid.uuid4().hex

# Each fixture deliberately supplies only the fields needed to make one
# representative create request observable at the HTTP boundary.
CREATE_CONTRACTS = (
    (
        "ad_hoc_command",
        "/api/controller/v2/ad_hoc_commands/",
        {"module_name": "ping", "module_args": "", "inventory": "1"},
        {"inventory": 1, "module_name": "ping"},
    ),
    (
        "bulk_host_create",
        "/api/controller/v2/bulk/host_create/",
        {"inventory": "1", "hosts": [{"name": "Contract Host"}]},
        {"inventory": 1, "hosts": [{"name": "Contract Host"}]},
    ),
    ("bulk_host_delete", "/api/controller/v2/bulk/host_delete/", {"hosts": [1, 2]}, {"hosts": [1, 2]}),
    (
        "bulk_job_launch",
        "/api/controller/v2/bulk/job_launch/",
        {"jobs": [{"id": 1}], "name": "Contract Launch"},
        {"jobs": [{"id": 1}], "name": "Contract Launch"},
    ),
    (
        "controller_credential",
        "/api/controller/v2/credentials/",
        {"name": "Contract Resource", "credential_type": "1"},
        {"name": "Contract Resource", "credential_type": 1},
    ),
    ("controller_credential_type", "/api/controller/v2/credential_types/", {"name": "Contract Resource"}, {"name": "Contract Resource", "managed": False}),
    ("controller_project", "/api/controller/v2/projects/", {"name": "Contract Resource"}, {"name": "Contract Resource"}),
    (
        "credential_input_source",
        "/api/controller/v2/credential_input_sources/",
        {"input_field_name": "password", "target_credential": "1", "source_credential": "2"},
        {"input_field_name": "password", "target_credential": 1, "source_credential": 2},
    ),
    ("decision_environment", "/api/eda/v1/decision-environments/", {"name": "Contract Resource"}, {"name": "Contract Resource"}),
    (
        "eda_controller_token",
        "/api/eda/v1/users/me/awx-tokens/",
        {"name": "Contract Resource", "token": CONTRACT_TOKEN},
        {"name": "Contract Resource", "token": CONTRACT_TOKEN},
    ),
    ("eda_credential", "/api/eda/v1/eda-credentials/", {"name": "Contract Resource"}, {"name": "Contract Resource"}),
    (
        "eda_credential_input_source",
        "/api/eda/v1/credential-input-sources/",
        {"input_field_name": "password", "target_credential": "1", "source_credential": "2"},
        {"input_field_name": "password", "target_credential": 1, "source_credential": 2},
    ),
    ("eda_credential_type", "/api/eda/v1/credential-types/", {"name": "Contract Resource"}, {"name": "Contract Resource"}),
    ("eda_project", "/api/eda/v1/projects/", {"name": "Contract Resource"}, {"name": "Contract Resource"}),
    (
        "event_stream",
        "/api/eda/v1/event-streams/",
        {"name": "Contract Resource", "credential_name": "1", "organization_name": "1"},
        {"name": "Contract Resource", "eda_credential_id": 1, "organization_id": 1, "test_mode": True},
    ),
    ("execution_environment", "/api/controller/v2/execution_environments/", {"name": "Contract Resource"}, {"name": "Contract Resource"}),
    ("group", "/api/controller/v2/groups/", {"name": "Contract Resource", "inventory": "1"}, {"name": "Contract Resource", "inventory": 1}),
    ("host", "/api/controller/v2/hosts/", {"name": "Contract Resource", "inventory": "1"}, {"name": "Contract Resource", "inventory": 1}),
    ("instance", "/api/controller/v2/instances/", {"hostname": "contract-host"}, {"hostname": "contract-host"}),
    ("instance_group", "/api/controller/v2/instance_groups/", {"name": "Contract Resource"}, {"name": "Contract Resource"}),
    ("inventory", "/api/controller/v2/inventories/", {"name": "Contract Resource", "organization": "1"}, {"name": "Contract Resource", "organization": 1}),
    (
        "inventory_source",
        "/api/controller/v2/inventory_sources/",
        {"name": "Contract Resource", "inventory": "1"},
        {"name": "Contract Resource", "inventory": 1},
    ),
    ("job_template", "/api/controller/v2/job_templates/", {"name": "Contract Resource"}, {"name": "Contract Resource"}),
    ("label", "/api/controller/v2/labels/", {"name": "Contract Resource", "organization": "1"}, {"name": "Contract Resource", "organization": 1}),
    ("license", "/api/controller/v2/config/", {"manifest": "contract-manifest"}, {"manifest": "contract-manifest"}),
    ("notification_template", "/api/controller/v2/notification_templates/", {"name": "Contract Resource"}, {"name": "Contract Resource"}),
    ("rulebook_activation", "/api/eda/v1/activations/", {"name": "Contract Resource"}, {"name": "Contract Resource"}),
    ("schedule", "/api/controller/v2/schedules/", {"name": "Contract Resource"}, {"name": "Contract Resource"}),
    ("workflow_job_template", "/api/controller/v2/workflow_job_templates/", {"name": "Contract Resource"}, {"name": "Contract Resource"}),
    (
        "workflow_job_template_node",
        "/api/controller/v2/workflow_job_template_nodes/",
        {"identifier": "Contract Node", "workflow_job_template": "1", "unified_job_template": "2"},
        {"identifier": "Contract Node", "workflow_job_template": 1, "unified_job_template": 2},
    ),
)

DELETE_PATHS = {
    "controller_credential": "/api/controller/v2/credentials/42/",
    "controller_credential_type": "/api/controller/v2/credential_types/42/",
    "controller_project": "/api/controller/v2/projects/42/",
    "credential_input_source": "/api/controller/v2/credential_input_sources/42/",
    "decision_environment": "/api/eda/v1/decision-environments/42/",
    "eda_controller_token": "/api/eda/v1/users/me/awx-tokens/42/",
    "eda_credential": "/api/eda/v1/eda-credentials/42/",
    "eda_credential_input_source": "/api/eda/v1/credential-input-sources/42/",
    "eda_credential_type": "/api/eda/v1/credential-types/42/",
    "eda_project": "/api/eda/v1/projects/42/",
    "event_stream": "/api/eda/v1/event-streams/42/",
    "execution_environment": "/api/controller/v2/execution_environments/42/",
    "group": "/api/controller/v2/groups/42/",
    "host": "/api/controller/v2/hosts/42/",
    "instance_group": "/api/controller/v2/instance_groups/42/",
    "inventory": "/api/controller/v2/inventories/42/",
    "inventory_source": "/api/controller/v2/inventory_sources/42/",
    "job_template": "/api/controller/v2/job_templates/42/",
    "notification_template": "/api/controller/v2/notification_templates/42/",
    "rulebook_activation": "/api/eda/v1/activations/42/",
    "schedule": "/api/controller/v2/schedules/42/",
    "workflow_job_template": "/api/controller/v2/workflow_job_templates/42/",
    "workflow_job_template_node": "/api/controller/v2/workflow_job_template_nodes/42/",
}

FIND_QUERY_PARAMETERS = {
    "controller_credential": {"name": "Contract Resource"},
    "controller_credential_type": {"name": "Contract Resource"},
    "controller_project": {"name": "Contract Resource"},
    "credential_input_source": {"input_field_name": "password", "target_credential": 1},
    "decision_environment": {"name": "Contract Resource"},
    "eda_controller_token": {"name": "Contract Resource"},
    "eda_credential": {"name": "Contract Resource"},
    "eda_credential_input_source": {"input_field_name": "password", "target_credential": 1, "source_credential": 2},
    "eda_credential_type": {"name": "Contract Resource"},
    "eda_project": {"name": "Contract Resource"},
    "event_stream": {"name": "Contract Resource", "organization_id": 1},
    "execution_environment": {"name": "Contract Resource"},
    "group": {"name": "Contract Resource", "inventory": 1},
    "host": {"name": "Contract Resource", "inventory": 1},
    "instance_group": {"name": "Contract Resource"},
    "inventory": {"name": "Contract Resource", "organization": 1},
    "inventory_source": {"name": "Contract Resource", "inventory": 1},
    "job_template": {"name": "Contract Resource"},
    "notification_template": {"name": "Contract Resource"},
    "rulebook_activation": {"name": "Contract Resource"},
    "schedule": {"name": "Contract Resource"},
    "workflow_job_template": {"name": "Contract Resource"},
    "workflow_job_template_node": {"identifier": "Contract Node", "workflow_job_template": 1},
}

UPDATE_CHANGE_CONTRACTS = {
    "controller_credential": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource", "credential_type": 1}),
    "controller_credential_type": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource"}),
    "controller_project": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource"}),
    "credential_input_source": (
        {"input_field_name": "updated_password"},
        {"input_field_name": "updated_password", "target_credential": 1, "source_credential": 2},
    ),
    "decision_environment": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource"}),
    "eda_credential": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource"}),
    "eda_credential_input_source": ({"description": "Updated description"}, {"description": "Updated description"}),
    "eda_credential_type": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource"}),
    "eda_project": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource"}),
    "event_stream": (
        {"new_name": "Updated Contract Resource"},
        {"name": "Updated Contract Resource", "eda_credential_id": 1, "organization_id": 1},
    ),
    "execution_environment": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource"}),
    "group": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource", "inventory": 1}),
    "host": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource", "inventory": 1}),
    "instance_group": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource"}),
    "inventory": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource", "organization": 1}),
    "inventory_source": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource", "inventory": 1}),
    "job_template": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource"}),
    "notification_template": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource"}),
    "rulebook_activation": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource"}),
    "schedule": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource"}),
    "workflow_job_template": ({"new_name": "Updated Contract Resource"}, {"name": "Updated Contract Resource"}),
    "workflow_job_template_node": (
        {"identifier": "Updated Node"},
        {
            "identifier": "Updated Node",
            "workflow_job_template": 1,
            "unified_job_template": 2,
        },
    ),
}


def _response(body: dict, direct: bool):
    encoded = json.dumps(body).encode("utf-8")
    if direct:
        response = MagicMock(spec=["read", "status", "code"])
        response.read.return_value = encoded
        response.status = 200
        response.code = 200
    else:
        response = MagicMock(spec=["json", "content", "status_code", "ok", "headers", "text", "raise_for_status"])
        response.content = encoded
        response.status_code = 200
        response.ok = True
        response.headers = {"Content-Type": "application/json"}
        response.text = encoded.decode("utf-8")
        response.json.return_value = body
    return response


def _client(client_mode: str):
    registry = APIVersionRegistry()
    loader = DynamicClassLoader(registry)
    api_versions = {"controller": "2", "eda": "1", "gateway": "1"}
    response_data = {"id": 42, "name": "Contract Resource"}
    response = _response(response_data, direct=client_mode == "direct")

    if client_mode == "direct":
        client = DirectHTTPClient.__new__(DirectHTTPClient)
        client._authenticated = True
        client._lock = threading.Lock()
        client._http_request_count = 0
        client.session = MagicMock()
        client.session.headers = {}
    else:
        client = PlatformService.__new__(PlatformService)
        client.record_activity = MagicMock()
        client.session = MagicMock()

    client.base_url = BASE_URL
    client.api_versions = api_versions
    client.registry = registry
    client.loader = loader
    client.cache = {}
    client._make_request = MagicMock(return_value=response)
    return client


def _update_responder(client_mode: str, current: dict, patch_response: dict | None = None, patch_error: APIError | None = None):
    """Return an API stub for update lookups, relationship lookups, and PATCH."""

    def respond(method, url, **kwargs):
        path = url.removeprefix(BASE_URL)
        params = kwargs.get("params") or {}
        if method.upper() == "PATCH":
            if patch_error is not None:
                raise patch_error
            return _response(patch_response or current, direct=client_mode == "direct")
        if "/organizations/1/" in path or "/workflow_job_templates/1/" in path:
            return _response({"id": 1, "name": "1"}, direct=client_mode == "direct")
        if ("/organizations/" in path or "/eda-credentials/" in path) and ("id=1" in path or params.get("id") == 1):
            return _response({"count": 1, "results": [{"id": 1, "name": "1"}]}, direct=client_mode == "direct")
        if client_mode == "direct":
            return _response({"count": 1, "results": [current]}, direct=True)
        return _response(current, direct=False)

    return respond


class TestMigratedCreateRequestContracts(unittest.TestCase):
    """Both public clients send the migrated resource create contract."""

    def test_create_sends_expected_method_path_and_body(self):
        for module_name, expected_path, ansible_data, expected_body in CREATE_CONTRACTS:
            for client_mode in ("direct", "persistent"):
                with self.subTest(module=module_name, client=client_mode):
                    client = _client(client_mode)

                    result = client.execute("create", module_name, dict(ansible_data))

                    client._make_request.assert_called_once()
                    request = client._make_request.call_args
                    self.assertEqual(request.args[0], "POST")
                    self.assertEqual(request.args[1], BASE_URL + expected_path)
                    self.assertEqual(request.kwargs["json"], expected_body)
                    self.assertIs(result["changed"], True)
                    if "id" in result:
                        self.assertEqual(result["id"], 42)


class TestMigratedDeleteRequestContracts(unittest.TestCase):
    """Delete operations use each migrated resource's public API endpoint."""

    def test_delete_sends_expected_method_and_path(self):
        for contract in CREATE_CONTRACTS:
            module_name = contract[0]
            ansible_data = contract[2]
            if module_name not in DELETE_PATHS:
                continue
            for client_mode in ("direct", "persistent"):
                with self.subTest(module=module_name, client=client_mode):
                    client = _client(client_mode)
                    client._make_request.return_value = _response({}, direct=client_mode == "direct")

                    result = client.execute("delete", module_name, dict(ansible_data, id=42))

                    client._make_request.assert_called_once()
                    request = client._make_request.call_args
                    self.assertEqual(request.args[0].upper(), "DELETE")
                    self.assertEqual(request.args[1], BASE_URL + DELETE_PATHS[module_name])
                    self.assertNotIn("json", request.kwargs)
                    self.assertEqual(result, {"changed": True, "id": 42})


class TestMigratedFindRequestContracts(unittest.TestCase):
    """Find operations query each endpoint and transform API results."""

    def test_find_uses_expected_query_and_returns_resource_id(self):
        for module_name, endpoint, ansible_data, response_body in CREATE_CONTRACTS:
            if module_name not in DELETE_PATHS:
                continue
            api_resource = {"id": 42, **response_body}
            api_resource.setdefault("name", ansible_data.get("name"))
            response_data = {"count": 1, "results": [api_resource]}
            for client_mode in ("direct", "persistent"):
                with self.subTest(module=module_name, client=client_mode):
                    client = _client(client_mode)
                    client._make_request.return_value = _response(response_data, direct=client_mode == "direct")

                    result = client.execute("find", module_name, dict(ansible_data))

                    self.assertGreaterEqual(client._make_request.call_count, 1)
                    request = client._make_request.call_args_list[0]
                    self.assertEqual(request.args[0].upper(), "GET")
                    query = FIND_QUERY_PARAMETERS[module_name]
                    expected_url = BASE_URL + endpoint
                    if not (module_name == "eda_credential_input_source" and client_mode == "persistent"):
                        expected_url += "?" + urlencode(query)
                    self.assertEqual(request.args[1], expected_url)
                    if module_name == "eda_credential_input_source" and client_mode == "persistent":
                        self.assertEqual(request.kwargs["params"], query)
                    self.assertEqual(result["id"], 42)

    def test_event_stream_response_is_transformed_into_module_fields(self):
        api_resource = {
            "id": 42,
            "name": "Contract Resource",
            "eda_credential": {"id": 7, "name": "Event Credential"},
            "organization": {"id": 9, "name": "Events"},
            "test_mode": False,
            "additional_data_headers": '{"X-Contract": "present"}',
            "uuid": "4cf8d9dd-2137-4890-b21c-60084d9e5ed5",
        }
        response_data = {"count": 1, "results": [api_resource]}

        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode)
                client._make_request.return_value = _response(response_data, direct=client_mode == "direct")

                result = client.execute("find", "event_stream", {"name": "Contract Resource"})

                request = client._make_request.call_args
                self.assertEqual(request.args[0].upper(), "GET")
                self.assertEqual(request.args[1], BASE_URL + "/api/eda/v1/event-streams/?name=Contract+Resource")
                result_fields = ("id", "name", "credential_name", "organization_name", "forward_events", "headers", "uuid")
                self.assertEqual(
                    {key: result[key] for key in result_fields},
                    {
                        "id": 42,
                        "name": "Contract Resource",
                        "credential_name": "Event Credential",
                        "organization_name": "Events",
                        "forward_events": True,
                        "headers": '{"X-Contract": "present"}',
                        "uuid": "4cf8d9dd-2137-4890-b21c-60084d9e5ed5",
                    },
                )


class TestMigratedRequestErrors(unittest.TestCase):
    """API failures remain visible through both public client execute APIs."""

    def test_create_propagates_api_error(self):
        for contract in CREATE_CONTRACTS:
            module_name = contract[0]
            ansible_data = contract[2]
            for client_mode in ("direct", "persistent"):
                with self.subTest(module=module_name, client=client_mode):
                    client = _client(client_mode)
                    error = APIError("Contract API failure", operation="create", resource=module_name)
                    client._make_request.side_effect = error

                    with self.assertRaises(APIError) as raised:
                        client.execute("create", module_name, dict(ansible_data))

                    self.assertIs(raised.exception, error)

    def test_delete_treats_missing_resource_as_noop_and_propagates_other_errors(self):
        create_fixtures = {contract[0]: contract[2] for contract in CREATE_CONTRACTS}
        for module_name in DELETE_PATHS:
            for client_mode in ("direct", "persistent"):
                with self.subTest(module=module_name, client=client_mode, status=404):
                    client = _client(client_mode)
                    client._make_request.side_effect = APIError("Not found", status_code=404)

                    result = client.execute("delete", module_name, {**create_fixtures[module_name], "id": 42})

                    self.assertEqual(result, {"changed": False, "id": 42})

                with self.subTest(module=module_name, client=client_mode, status=500):
                    client = _client(client_mode)
                    error = APIError("Server error", status_code=500)
                    client._make_request.side_effect = error

                    with self.assertRaises(APIError) as raised:
                        client.execute("delete", module_name, {**create_fixtures[module_name], "id": 42})

                    self.assertIs(raised.exception, error)

    def test_update_errors_propagate_for_all_updateable_resources(self):
        for client_mode in ("direct", "persistent"):
            fixtures = {contract[0]: (contract[2], contract[3]) for contract in CREATE_CONTRACTS}
            for module_name, update_contract in UPDATE_CHANGE_CONTRACTS.items():
                changes = update_contract[0]
                ansible_data, response_body = fixtures[module_name]
                current = {"id": 42, **response_body}
                for field in ("name", "input_field_name", "hostname", "identifier"):
                    if field in ansible_data:
                        current.setdefault(field, ansible_data[field])
                if module_name == "workflow_job_template_node":
                    current["summary_fields"] = {
                        "workflow_job_template": {"name": "1"},
                        "unified_job_template": {"name": "2"},
                    }

                with self.subTest(module=module_name, client=client_mode, operation="update"):
                    client = _client(client_mode)
                    error = APIError("Update failed", status_code=500)
                    client._make_request.side_effect = _update_responder(client_mode, current, patch_error=error)

                    with self.assertRaises(APIError) as raised:
                        client.execute("update", module_name, {**ansible_data, **changes, "id": 42})

                    self.assertIs(raised.exception, error)

    def test_custom_endpoint_errors_propagate(self):
        error_cases = (
            ("launch", lambda client: client.launch_resource("/api/controller/v2/job_templates/42/launch/", {}, service="controller")),
            ("wait", lambda client: client.wait_for_completion("/jobs/42/", timeout=1, interval=0.01, service="controller")),
            ("search", lambda client: client.search_api("jobs", service="controller")),
            ("direct_request", lambda client: client.direct_request("POST", "/api/controller/v2/workflow_approvals/77/approve/")),
            ("cancel", lambda client: client.cancel_resource(42, "jobs", service="controller")),
            ("post_resource", lambda client: client.post_resource("/api/controller/v2/config/attach/", {}, service="controller")),
        )
        for client_mode in ("direct", "persistent"):
            for operation, call in error_cases:
                with self.subTest(client=client_mode, operation=operation):
                    client = _client(client_mode)
                    error = APIError(f"{operation} failed", status_code=500)
                    client._make_request.side_effect = error

                    with self.assertRaises(APIError) as raised:
                        call(client)

                    self.assertIs(raised.exception, error)

    def test_cancel_treats_not_running_as_unchanged(self):
        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode, operation="cancel_not_running"):
                client = _client(client_mode)
                client._make_request.side_effect = APIError("Not running", status_code=405)

                result = client.cancel_resource(42, "jobs", service="controller")

                self.assertEqual(result, {"changed": False, "id": 42, "status": "already finished"})

    def test_settings_update_propagates_api_error(self):
        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode, operation="settings_update"):
                client = _client(client_mode)
                error = APIError("Settings update failed", status_code=500)
                client._make_request.side_effect = [_response({"SETTING_A": "old"}, direct=client_mode == "direct"), error]

                with self.assertRaises(APIError) as raised:
                    client.execute("update", "controller_settings", {"settings": {"SETTING_A": "new"}})

                self.assertIs(raised.exception, error)


class TestMigratedUpdateIdempotency(unittest.TestCase):
    """Unchanged resources skip PATCH; actual changes send it in both modes."""

    def test_unchanged_crud_resources_skip_patch_in_both_clients(self):
        for module_name, _endpoint, ansible_data, response_body in CREATE_CONTRACTS:
            if module_name not in DELETE_PATHS or module_name == "eda_controller_token":
                continue
            api_resource = {"id": 42, **response_body}
            for field in ("name", "input_field_name", "hostname", "identifier"):
                if field in ansible_data:
                    api_resource.setdefault(field, ansible_data[field])
            if module_name == "workflow_job_template_node":
                api_resource["summary_fields"] = {
                    "workflow_job_template": {"id": 1, "name": "Contract Workflow"},
                    "unified_job_template": {"id": 2, "name": "Contract Job Template"},
                }
            if module_name == "event_stream":
                api_resource["eda_credential"] = {"id": 1, "name": "Contract Credential"}
                api_resource["organization"] = {"id": 1, "name": "Contract Organization"}

            for client_mode in ("direct", "persistent"):
                with self.subTest(module=module_name, client=client_mode):
                    client = _client(client_mode)
                    if module_name == "workflow_job_template_node":
                        client.lookup_resource_id = MagicMock()
                    elif module_name == "event_stream":
                        client.lookup_resource_id = MagicMock(return_value=1)

                    client._make_request.side_effect = _update_responder(client_mode, api_resource)
                    result = client.execute("update", module_name, dict(ansible_data, id=42))

                    self.assertFalse(any(call.args[0].upper() == "PATCH" for call in client._make_request.call_args_list))
                    if module_name == "workflow_job_template_node":
                        client.lookup_resource_id.assert_not_called()
                    elif module_name == "event_stream":
                        self.assertNotIn("eda-credentials", [call.args[0] for call in client.lookup_resource_id.call_args_list])
                    self.assertIs(result["changed"], False)

    def test_real_changes_send_expected_patch_body_in_both_clients(self):
        fixtures = {module_name: (endpoint, ansible_data, response_body) for module_name, endpoint, ansible_data, response_body in CREATE_CONTRACTS}
        for module_name, (changes, expected_body) in UPDATE_CHANGE_CONTRACTS.items():
            endpoint, ansible_data, response_body = fixtures[module_name]
            api_resource = {"id": 42, **response_body}
            for field in ("name", "input_field_name", "hostname", "identifier"):
                if field in ansible_data:
                    api_resource.setdefault(field, ansible_data[field])
            if module_name == "workflow_job_template_node":
                api_resource["inventory"] = 3
                api_resource["execution_environment"] = 4
                api_resource["summary_fields"] = {
                    "workflow_job_template": {"id": 1, "name": "Contract Workflow"},
                    "unified_job_template": {"id": 2, "name": "Contract Job Template"},
                    "inventory": {"id": 3, "name": "Contract Inventory"},
                    "execution_environment": {"id": 4, "name": "Contract Execution Environment"},
                }

            for client_mode in ("direct", "persistent"):
                with self.subTest(module=module_name, client=client_mode):
                    client = _client(client_mode)

                    client._make_request.side_effect = _update_responder(
                        client_mode,
                        api_resource,
                        patch_response={**api_resource, **expected_body},
                    )
                    update_data = {**ansible_data, **changes, "id": 42}
                    result = client.execute("update", module_name, update_data)

                    patch_calls = [call for call in client._make_request.call_args_list if call.args[0].upper() == "PATCH"]
                    self.assertEqual(len(patch_calls), 1)
                    self.assertEqual(patch_calls[0].args[1], BASE_URL + endpoint.rstrip("/") + "/42/")
                    self.assertEqual(patch_calls[0].kwargs["json"], expected_body)
                    self.assertIs(result["changed"], True)

    def test_project_description_update_uses_expected_lookup_and_patch_contract(self):
        current = {"id": 42, "name": "Contract Resource", "description": "Current description"}
        changed = {**current, "description": "Updated description"}
        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode)
                client._make_request.side_effect = _update_responder(client_mode, current, patch_response=changed)

                result = client.execute("update", "controller_project", {"id": 42, "name": "Contract Resource", "description": "Updated description"})

                self.assertEqual(client._make_request.call_count, 2)
                find_request, patch_request = client._make_request.call_args_list
                self.assertEqual(find_request.args[0].upper(), "GET")
                expected_find_url = (
                    BASE_URL + "/api/controller/v2/projects/?name=Contract+Resource"
                    if client_mode == "direct"
                    else BASE_URL + "/api/controller/v2/projects/42/"
                )
                self.assertEqual(find_request.args[1], expected_find_url)
                self.assertEqual(patch_request.args[0].upper(), "PATCH")
                self.assertEqual(patch_request.args[1], BASE_URL + "/api/controller/v2/projects/42/")
                self.assertEqual(patch_request.kwargs["json"], {"name": "Contract Resource", "description": "Updated description"})
                self.assertIs(result["changed"], True)

    def test_literal_none_updates_field_missing_from_current_resource(self):
        current = {"id": 42, "name": "Contract Resource", "description": None}
        updated = {"id": 42, "name": "Contract Resource", "description": "None"}

        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode)
                client._make_request.side_effect = _update_responder(client_mode, current, patch_response=updated)

                result = client.execute(
                    "update",
                    "controller_project",
                    {"id": 42, "name": "Contract Resource", "description": "None"},
                )

                patch_calls = [call for call in client._make_request.call_args_list if call.args[0].upper() == "PATCH"]
                self.assertEqual(len(patch_calls), 1)
                self.assertEqual(patch_calls[0].kwargs["json"], {"name": "Contract Resource", "description": "None"})
                self.assertIs(result["changed"], True)
                self.assertEqual(result["description"], "None")

    def test_explicit_empty_scm_branch_is_sent_to_clear_stored_value(self):
        current = {"id": 42, "name": "Contract Workflow", "scm_branch": "main"}
        updated = {"id": 42, "name": "Contract Workflow", "scm_branch": ""}

        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode)
                client._make_request.side_effect = _update_responder(client_mode, current, patch_response=updated)

                result = client.execute(
                    "update",
                    "workflow_job_template",
                    {"id": 42, "name": "Contract Workflow", "scm_branch": ""},
                )

                patch_calls = [call for call in client._make_request.call_args_list if call.args[0].upper() == "PATCH"]
                self.assertEqual(len(patch_calls), 1)
                self.assertEqual(patch_calls[0].kwargs["json"], {"name": "Contract Workflow", "scm_branch": ""})
                self.assertIs(result["changed"], True)

    def test_explicit_force_update_patches_write_only_password_in_both_clients(self):
        api_resource = {"id": 42, "username": "contract-user", "password": "$encrypted$"}
        test_password = uuid.uuid4().hex
        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode)

                def respond(method, url, **kwargs):
                    if method.upper() == "PATCH":
                        return _response(api_resource, direct=client_mode == "direct")
                    if client_mode == "direct":
                        return _response({"count": 1, "results": [api_resource]}, direct=True)
                    return _response(api_resource, direct=False)

                client._make_request.side_effect = respond
                client.execute(
                    "update",
                    "user",
                    {
                        "id": 42,
                        "username": "contract-user",
                        "password": test_password,
                        "_platform_force_update": True,
                    },
                )

                patch_calls = [call for call in client._make_request.call_args_list if call.args[0].upper() == "PATCH"]
                self.assertEqual(len(patch_calls), 1)
                self.assertEqual(patch_calls[0].args[1], BASE_URL + "/api/gateway/v1/users/42/")
                self.assertEqual(patch_calls[0].kwargs["json"], {"password": test_password})


class TestMigratedActionRequestContracts(unittest.TestCase):
    """Custom launch and cancellation endpoints match migrated module contracts."""

    def test_launch_operations_post_expected_paths_and_payloads(self):
        launch_contracts = (
            ("job_launch", "/api/controller/v2/job_templates/42/launch/", {"extra_vars": {"contract": True}}, False),
            ("inventory_source_update", "/api/controller/v2/inventory_sources/42/update/", {}, False),
            ("project_update", "/api/controller/v2/projects/42/update/", {}, True),
            ("workflow_launch", "/api/controller/v2/workflow_job_templates/42/launch/", {"extra_vars": {"contract": True}}, False),
        )
        for module_name, endpoint, payload, retry in launch_contracts:
            for client_mode in ("direct", "persistent"):
                with self.subTest(module=module_name, client=client_mode):
                    client = _client(client_mode)
                    expected_response = {"id": 42, "status": "pending"}
                    client._make_request.return_value = _response(expected_response, direct=client_mode == "direct")

                    result = client.launch_resource(endpoint, payload, service="controller", retry=retry)

                    request = client._make_request.call_args
                    self.assertEqual(request.args[0].upper(), "POST")
                    self.assertEqual(request.args[1], BASE_URL + endpoint)
                    self.assertEqual(request.kwargs["json"], payload)
                    if not retry and client_mode == "persistent":
                        self.assertEqual(request.kwargs["retry_config"].max_attempts, 1)
                    self.assertEqual(result, expected_response)

    def test_cancel_operations_post_expected_paths_and_return_module_result(self):
        for module_name, endpoint in (
            ("job_cancel", "jobs"),
            ("ad_hoc_command_cancel", "ad_hoc_commands"),
        ):
            for client_mode in ("direct", "persistent"):
                with self.subTest(module=module_name, client=client_mode):
                    client = _client(client_mode)
                    client._make_request.return_value = _response({}, direct=client_mode == "direct")

                    result = client.cancel_resource(42, endpoint, service="controller")

                    request = client._make_request.call_args
                    self.assertEqual(request.args[0].upper(), "POST")
                    self.assertEqual(request.args[1], f"{BASE_URL}/api/controller/v2/{endpoint}/42/cancel/")
                    self.assertEqual(request.kwargs["json"], {})
                    self.assertEqual(result, {"changed": True, "id": 42, "status": "canceled"})


class TestCustomMigrationAPIContracts(unittest.TestCase):
    """Public query, singleton, and direct-action APIs keep migrated contracts."""

    def test_custom_list_modules_query_their_public_endpoints(self):
        cases = (
            ("job_list", "/api/controller/v2/jobs/", {"status": "successful", "page": 2}),
            ("workflow_approval", "/api/controller/v2/workflow_jobs/42/workflow_nodes/", {"job__name": "Contract Approval"}),
            ("workflow_node_wait", "workflow_jobs/42/workflow_nodes/", {"job__name": "Contract Node"}),
        )
        response_data = {"count": 1, "next": None, "previous": None, "results": [{"id": 99, "status": "successful"}]}
        for module_name, endpoint, query in cases:
            for client_mode in ("direct", "persistent"):
                with self.subTest(module=module_name, client=client_mode):
                    client = _client(client_mode)
                    client._make_request.return_value = _response(response_data, direct=client_mode == "direct")

                    result = client.search_api(endpoint, query_params=query, service="controller")

                    request = client._make_request.call_args
                    self.assertEqual(request.args[0].upper(), "GET")
                    expected_path = endpoint if endpoint.startswith("/api/") else f"/api/controller/v2/{endpoint}"
                    expected_url = BASE_URL + expected_path
                    if client_mode == "direct":
                        expected_url += "?" + urlencode(query)
                        self.assertEqual(request.args[1], expected_url)
                    else:
                        self.assertEqual(request.args[1], expected_url)
                        self.assertEqual(request.kwargs["params"], query)
                    self.assertEqual(result, response_data)

    def test_job_wait_finds_the_selected_job_type_endpoint(self):
        response_data = {"id": 42, "status": "successful", "finished": "2026-01-01T00:00:00Z"}
        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode):
                client = _client(client_mode)
                client._make_request.return_value = _response(response_data, direct=client_mode == "direct")

                result = client.execute("find", "job_wait", {"job_id": 42, "job_type": "jobs"})

                request = client._make_request.call_args
                self.assertEqual(request.args[0].upper(), "GET")
                self.assertEqual(request.args[1], BASE_URL + "/api/controller/v2/jobs/42/")
                self.assertEqual(result["id"], 42)
                self.assertEqual(result["status"], "successful")

    def test_wait_modules_poll_their_resource_endpoints(self):
        cases = (
            ("job_wait", "/jobs/42/"),
            ("ad_hoc_command_wait", "/ad_hoc_commands/42/"),
            ("workflow_node_wait", "jobs/99/"),
        )
        for module_name, resource_path in cases:
            for client_mode in ("direct", "persistent"):
                with self.subTest(module=module_name, client=client_mode):
                    client = _client(client_mode)
                    client._make_request.return_value = _response({"id": 42, "status": "successful"}, direct=client_mode == "direct")

                    result = client.wait_for_completion(resource_path, timeout=1, interval=0.01, service="controller")

                    request = client._make_request.call_args
                    self.assertEqual(request.args[0].upper(), "GET")
                    self.assertEqual(request.args[1], BASE_URL + "/api/controller/v2/" + resource_path.lstrip("/"))
                    self.assertEqual(result["status"], "successful")

    def test_direct_actions_post_declared_custom_endpoints(self):
        cases = (
            ("workflow_approval", "POST", "/api/controller/v2/workflow_approvals/77/approve/", None),
            ("workflow_approval", "POST", "/api/controller/v2/workflow_approvals/77/deny/", None),
            ("rulebook_activation", "POST", "/api/eda/v1/activations/42/enable/", None),
            ("rulebook_activation", "POST", "/api/eda/v1/activations/42/disable/", None),
            ("rulebook_activation", "POST", "/api/eda/v1/activations/42/restart/", None),
            ("rulebook_activation_copy", "POST", "/api/eda/v1/activations/42/copy/", {"name": "Contract Copy"}),
        )
        for module_name, method, path, payload in cases:
            for client_mode in ("direct", "persistent"):
                with self.subTest(module=module_name, path=path, client=client_mode):
                    client = _client(client_mode)
                    response_body = {"id": 43, "name": "Contract Copy"}
                    client._make_request.return_value = _response(response_body, direct=client_mode == "direct")

                    result = client.direct_request(method, path, data=payload)

                    request = client._make_request.call_args
                    self.assertEqual(request.args[0].upper(), method)
                    self.assertEqual(request.args[1], BASE_URL + path)
                    if payload is not None:
                        body_arg = "data" if client_mode == "direct" else "json"
                        body = request.kwargs[body_arg]
                        if client_mode == "direct":
                            body = json.loads(body)
                        self.assertEqual(body, payload)
                    self.assertEqual(result, response_body)

    def test_controller_settings_singleton_uses_get_and_patch_contracts(self):
        current = {"SETTING_A": "old"}
        updated = {"SETTING_A": "new"}
        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode, operation="find"):
                client = _client(client_mode)
                client._make_request.return_value = _response(current, direct=client_mode == "direct")

                result = client.execute("find", "controller_settings", {"settings": {}})

                request = client._make_request.call_args
                self.assertEqual(request.args[0].upper(), "GET")
                self.assertEqual(request.args[1], BASE_URL + "/api/controller/v2/settings/all/")
                self.assertEqual(result["settings"], current)

            with self.subTest(client=client_mode, operation="update"):
                client = _client(client_mode)
                client._make_request.side_effect = [
                    _response(current, direct=client_mode == "direct"),
                    _response(updated, direct=client_mode == "direct"),
                ]

                result = client.execute("update", "controller_settings", {"settings": updated})

                request = client._make_request.call_args_list[-1]
                self.assertEqual(request.args[0].upper(), "PATCH")
                self.assertEqual(request.args[1], BASE_URL + "/api/controller/v2/settings/all/")
                self.assertEqual(request.kwargs["json"], updated)
                self.assertIs(result["changed"], True)

    def test_license_config_helpers_use_expected_http_contracts(self):
        for client_mode in ("direct", "persistent"):
            with self.subTest(client=client_mode, operation="attach"):
                client = _client(client_mode)
                response_body = {"license_info": {"license_type": "enterprise"}}
                client._make_request.return_value = _response(response_body, direct=client_mode == "direct")

                result = client.post_resource("/api/controller/v2/config/attach/", {"subscription_id": "SUB-42"}, service="controller", retry=False)

                request = client._make_request.call_args
                self.assertEqual(request.args[0].upper(), "POST")
                self.assertEqual(request.args[1], BASE_URL + "/api/controller/v2/config/attach/")
                self.assertEqual(request.kwargs["json"], {"subscription_id": "SUB-42"})
                self.assertEqual(result, response_body)

            with self.subTest(client=client_mode, operation="delete"):
                client = _client(client_mode)
                client._make_request.return_value = _response({}, direct=client_mode == "direct")

                result = client.delete_resource("/api/controller/v2/config/", service="controller")

                request = client._make_request.call_args
                self.assertEqual(request.args[0].upper(), "DELETE")
                self.assertEqual(request.args[1], BASE_URL + "/api/controller/v2/config/")
                self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
