# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the event_stream action plugin and transform mixin."""

import unittest
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.event_stream import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.event_stream import AnsibleEventStream
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.event_stream import (
    EventStreamTransformMixin_v1,
)


class TestEventStreamActionPlugin(unittest.TestCase):
    """Test event_stream action plugin configuration."""

    def test_module_name(self):
        self.assertEqual(ActionModule.MODULE_NAME, "event_stream")

    def test_model_class(self):
        self.assertEqual(ActionModule.MODEL_CLASS, AnsibleEventStream)

    def test_deprecated_fields(self):
        self.assertIn("event_stream_type", ActionModule._DEPRECATED_FIELDS)
        msg, version = ActionModule._DEPRECATED_FIELDS["event_stream_type"]
        self.assertIn("deprecated", msg.lower())
        self.assertEqual(version, "3.0.0")


class TestEventStreamActionCRUD(unittest.TestCase):
    """Test event_stream action plugin CRUD behavior."""

    def _make_action(self, check_mode=False):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.check_mode = check_mode
        action._task.args = {}
        action._task.environment = []
        action._display = MagicMock()
        action._display.verbosity = 0
        return action

    def _make_manager(self, find_result=None, create_result=None):
        manager = MagicMock()

        def lookup_resource_id(endpoint, field, value, **kwargs):
            if endpoint == "organizations":
                return 1 if value in ("D", "Default", "1") else None
            if endpoint == "eda-credentials":
                return 10 if value in ("c", "Token", "10") else None
            return None

        manager.lookup_resource_id.side_effect = lookup_resource_id

        def side_effect(operation, module_name, ansible_data):
            if operation == "find":
                if find_result:
                    return find_result
                raise ValueError("Resource with name=%s not found" % ansible_data.get("name"))
            if operation == "delete":
                return {"changed": True}
            if operation == "create":
                return create_result or {"id": 100, "name": ansible_data.get("name", ""), "changed": True}
            if operation == "update":
                merged = dict(find_result or {})
                merged.update(ansible_data)
                merged["changed"] = True
                return merged
            return {}

        manager.execute.side_effect = side_effect
        return manager

    def _run(self, action, manager, params):
        argspec = {
            "argument_spec": {
                "name": {"required": True, "type": "str"},
                "new_name": {"type": "str"},
                "credential_name": {"type": "str", "aliases": ["credential"]},
                "organization_name": {"type": "str", "aliases": ["organization"]},
                "event_stream_type": {"type": "str", "aliases": ["type"]},
                "headers": {"type": "str"},
                "forward_events": {"type": "bool"},
                "uuid": {"type": "str"},
                "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            }
        }

        def validate_side_effect(data, spec, direction):
            if direction == "input":
                return SimpleNamespace(validated_parameters=params)
            return data

        with (
            patch.object(ActionBase, "run", return_value={}),
            patch.object(action, "_get_documentation", return_value="module: event_stream"),
            patch.object(action, "_build_argspec_from_docs", return_value=argspec),
            patch.object(action, "_validate_data", side_effect=validate_side_effect),
            patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)),
        ):
            return action.run(task_vars={})

    def test_create_new(self):
        action = self._make_action()
        mgr = self._make_manager(create_result={"id": 100, "name": "s", "changed": True})
        r = self._run(action, mgr, {"name": "s", "credential_name": "c", "organization_name": "D", "state": "present"})
        self.assertFalse(r.get("failed", False))
        self.assertTrue(r["changed"])

    def test_delete_existing(self):
        action = self._make_action()
        mgr = self._make_manager(find_result={"id": 100, "name": "s"})
        r = self._run(action, mgr, {"name": "s", "state": "absent"})
        self.assertFalse(r.get("failed", False))

    def test_delete_nonexistent(self):
        action = self._make_action()
        mgr = self._make_manager()
        r = self._run(action, mgr, {"name": "ghost", "state": "absent"})
        self.assertFalse(r.get("failed", False))
        self.assertFalse(r["changed"])
        self.assertIn("already absent", r["msg"])

    def test_absent_does_not_fall_back_to_new_name(self):
        """state=absent must not delete the rename target when the original
        name is already gone -- new_name here is leftover task data, not a
        request to rename-then-delete."""
        action = self._make_action()
        manager = self._make_manager()

        def find_only(operation, module_name, ansible_data):
            if operation == "find":
                if ansible_data.get("name") == "old":
                    raise ValueError("Resource with name=old not found")
                if ansible_data.get("name") == "new":
                    return {"id": 100, "name": "new"}
                raise ValueError("Unexpected lookup")
            raise AssertionError("delete should not be called when the original name is already absent")

        manager.execute.side_effect = find_only
        result = self._run(action, manager, {"name": "old", "new_name": "new", "state": "absent"})

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])
        self.assertIn("already absent", result["msg"])
        self.assertEqual([call.kwargs["ansible_data"]["name"] for call in manager.execute.call_args_list], ["old"])

    def test_check_mode_present(self):
        action = self._make_action(check_mode=True)
        mgr = self._make_manager()
        r = self._run(action, mgr, {"name": "s", "credential_name": "c", "organization_name": "D", "state": "present"})
        self.assertTrue(r["changed"])
        ops = [c.kwargs.get("operation") for c in mgr.execute.call_args_list]
        self.assertNotIn("create", ops)

    def test_deprecated_emits_warning(self):
        action = self._make_action()
        mgr = self._make_manager(create_result={"id": 1, "name": "s", "changed": True})
        r = self._run(action, mgr, {"name": "s", "credential_name": "c", "organization_name": "D", "event_stream_type": "t", "state": "present"})
        self.assertFalse(r.get("failed", False))
        self.assertTrue(len(r.get("deprecations", [])) > 0)

    def test_completed_rename_is_idempotent(self):
        action = self._make_action()
        manager = self._make_manager()

        def find_or_create(operation, module_name, ansible_data):
            if operation == "find":
                if ansible_data.get("name") == "old":
                    raise ValueError("Resource with name=old not found")
                if ansible_data.get("name") == "new":
                    return {
                        "id": 100,
                        "name": "new",
                        "credential_name": "c",
                        "organization_name": "D",
                        "forward_events": False,
                    }
                raise ValueError("Unexpected lookup")
            return {"changed": True, "id": 100}

        manager.execute.side_effect = find_or_create
        result = self._run(
            action,
            manager,
            {"name": "old", "new_name": "new", "credential_name": "c", "organization_name": "D", "state": "present"},
        )

        self.assertFalse(result["changed"])
        self.assertEqual([call.kwargs["ansible_data"]["name"] for call in manager.execute.call_args_list], ["old", "new"])

    def test_rename_rejects_a_target_name_owned_by_another_event_stream(self):
        action = self._make_action()
        manager = self._make_manager()

        def find_resources(operation, module_name, ansible_data):
            if operation == "find":
                if ansible_data.get("name") == "old":
                    return {"id": 100, "name": "old"}
                if ansible_data.get("name") == "new":
                    return {"id": 101, "name": "new"}
            return {"changed": True}

        manager.execute.side_effect = find_resources
        result = self._run(action, manager, {"name": "old", "new_name": "new", "state": "present"})

        self.assertTrue(result["failed"])
        self.assertIn("event stream 'new' already exists", result["msg"])
        self.assertEqual([call.kwargs["ansible_data"]["name"] for call in manager.execute.call_args_list], ["old", "new"])

    def test_rename_updates_when_target_name_is_available(self):
        action = self._make_action()
        manager = self._make_manager()

        def find_and_update(operation, module_name, ansible_data):
            if operation == "find":
                if ansible_data.get("name") == "old":
                    return {"id": 100, "name": "old"}
                raise ValueError("Resource with name=new not found")
            if operation == "update":
                return {"id": 100, "name": "new", "changed": True}
            return {}

        manager.execute.side_effect = find_and_update
        result = self._run(action, manager, {"name": "old", "new_name": "new", "state": "present"})

        self.assertTrue(result["changed"])
        update_call = next(call for call in manager.execute.call_args_list if call.kwargs["operation"] == "update")
        self.assertEqual(update_call.kwargs["ansible_data"]["new_name"], "new")

    def test_ambiguous_find_error_is_not_treated_as_missing(self):
        action = self._make_action()
        manager = self._make_manager()
        manager.execute.side_effect = ValueError("Resource with name=s matched multiple resources")

        result = self._run(action, manager, {"name": "s", "credential_name": "c", "organization_name": "D", "state": "present"})

        self.assertTrue(result["failed"])
        manager.execute.assert_called_once()

    def test_documentation_validation_preserves_legacy_forward_events_default(self):
        action = self._make_action()
        action._task.args = {"name": "s", "credential_name": "c", "organization_name": "D", "state": "present"}
        manager = self._make_manager(create_result={"id": 100, "name": "s", "changed": True})

        with patch.object(ActionBase, "run", return_value={}), patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
            result = action.run(task_vars={})

        self.assertFalse(result.get("failed", False))
        create_call = next(call for call in manager.execute.call_args_list if call.kwargs.get("operation") == "create")
        self.assertFalse(create_call.kwargs["ansible_data"]["forward_events"])

    def test_create_fails_when_required_references_missing(self):
        """credential_name/organization_name are enforced by the transform's
        from_ansible_data() (see TestEventStreamTransform), not by DOCUMENTATION's
        required_if -- that construct breaks ansible-doc rendering and isn't used
        anywhere else in this collection. This only verifies the action plugin
        surfaces that failure instead of swallowing it.
        """
        action = self._make_action()
        action._task.args = {"name": "s", "state": "present"}
        manager = MagicMock()

        def side_effect(operation, module_name, ansible_data):
            if operation == "find":
                raise ValueError("Resource with name=s not found")
            raise ValueError("credential_name is required to create an event stream")

        manager.execute.side_effect = side_effect

        with patch.object(ActionBase, "run", return_value={}), patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
            result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("credential_name is required", result["msg"])


class TestAnsibleEventStreamModel(unittest.TestCase):
    """Test AnsibleEventStream dataclass."""

    def test_basic(self):
        es = AnsibleEventStream(name="test")
        self.assertEqual(es.state, "present")
        self.assertIsNone(es.id)

    def test_uuid_validation(self):
        with self.assertRaises(ValueError):
            AnsibleEventStream(name="s", uuid="bad")


class TestEventStreamTransform(unittest.TestCase):
    """Test EventStreamTransformMixin_v1."""

    def _ctx(self, op="create", mgr=None):
        return {"operation": op, "manager": mgr}

    def _mgr(self, cred_id=10, org_id=1):
        m = MagicMock()

        def lookup(endpoint, field, value, service="gateway", extra_query_params=None, require_unique=False):
            if endpoint == "eda-credentials":
                return cred_id
            if endpoint == "organizations":
                return org_id
            raise ValueError(endpoint)

        m.lookup_resource_id.side_effect = lookup
        return m

    def test_create_resolves_fks(self):
        mgr = self._mgr()
        obj = AnsibleEventStream(name="s", credential_name="C", organization_name="D")
        api = EventStreamTransformMixin_v1.from_ansible_data(obj, self._ctx("create", mgr))
        self.assertEqual(api.eda_credential_id, 10)
        self.assertEqual(api.organization_id, 1)
        self.assertEqual(
            mgr.lookup_resource_id.call_args_list[1].kwargs,
            {"service": "eda", "extra_query_params": {"organization": 1}, "require_unique": True},
        )
        self.assertEqual(mgr.lookup_resource_id.call_args_list[0].kwargs, {"service": "eda", "extra_query_params": None, "require_unique": True})

    def test_unresolved_credential_is_rejected(self):
        mgr = self._mgr(cred_id=None)
        obj = AnsibleEventStream(name="s", credential_name="missing", organization_name="D")
        with self.assertRaisesRegex(ValueError, "Could not resolve eda-credentials reference 'missing'"):
            EventStreamTransformMixin_v1.from_ansible_data(obj, self._ctx("create", mgr))

    def test_create_requires_organization_and_credential(self):
        with self.assertRaisesRegex(ValueError, "credential_name is required"):
            EventStreamTransformMixin_v1.from_ansible_data(AnsibleEventStream(name="s"), self._ctx("create"))
        with self.assertRaisesRegex(ValueError, "organization_name is required"):
            EventStreamTransformMixin_v1.from_ansible_data(AnsibleEventStream(name="s", credential_name="10"), self._ctx("create"))

    def test_forward_events_defaults_to_legacy_false(self):
        api = EventStreamTransformMixin_v1.from_ansible_data(AnsibleEventStream(name="s", credential_name="10", organization_name="1"), self._ctx("create"))
        self.assertTrue(api.test_mode)

    def test_forward_events_true(self):
        mgr = self._mgr()
        obj = AnsibleEventStream(name="s", credential_name="c", organization_name="D", forward_events=True)
        api = EventStreamTransformMixin_v1.from_ansible_data(obj, self._ctx("create", mgr))
        self.assertFalse(api.test_mode)

    def test_forward_events_false(self):
        mgr = self._mgr()
        obj = AnsibleEventStream(name="s", credential_name="c", organization_name="D", forward_events=False)
        api = EventStreamTransformMixin_v1.from_ansible_data(obj, self._ctx("create", mgr))
        self.assertTrue(api.test_mode)

    def test_headers_rename(self):
        mgr = self._mgr()
        obj = AnsibleEventStream(name="s", credential_name="c", organization_name="D", headers="X-H")
        api = EventStreamTransformMixin_v1.from_ansible_data(obj, self._ctx("create", mgr))
        self.assertEqual(api.additional_data_headers, "X-H")

    def test_numeric_credential(self):
        obj = AnsibleEventStream(name="s", credential_name="42", organization_name="7")
        api = EventStreamTransformMixin_v1.from_ansible_data(obj, self._ctx("create"))
        self.assertEqual(api.eda_credential_id, 42)
        self.assertEqual(api.organization_id, 7)

    def test_new_name_update(self):
        obj = AnsibleEventStream(name="old", new_name="new")
        api = EventStreamTransformMixin_v1.from_ansible_data(obj, self._ctx("update"))
        self.assertEqual(api.name, "new")

    def test_uuid_invalid(self):
        obj = AnsibleEventStream.__new__(AnsibleEventStream)
        for attr in ("name", "new_name", "credential_name", "organization_name", "event_stream_type", "headers", "forward_events", "state", "id"):
            setattr(obj, attr, None)
        obj.name = "s"
        obj.state = "present"
        obj.uuid = "bad"
        with self.assertRaises(ValueError):
            EventStreamTransformMixin_v1.from_ansible_data(obj, self._ctx("create"))

    def test_type_not_in_api(self):
        obj = AnsibleEventStream(name="s", credential_name="10", organization_name="1", event_stream_type="hmac")
        api = EventStreamTransformMixin_v1.from_ansible_data(obj, self._ctx("create"))
        self.assertNotIn("event_stream_type", asdict(api))

    def test_from_api_basic(self):
        data = {
            "id": 42,
            "name": "s",
            "eda_credential_id": 10,
            "organization_id": 1,
            "test_mode": False,
            "additional_data_headers": "H",
            "uuid": "550e8400-e29b-41d4-a716-446655440000",
        }
        obj = EventStreamTransformMixin_v1.from_api(data, {})
        self.assertEqual(obj.credential_name, "10")
        self.assertEqual(obj.organization_name, "1")
        self.assertTrue(obj.forward_events)
        self.assertEqual(obj.headers, "H")

    def test_from_api_test_mode_true(self):
        obj = EventStreamTransformMixin_v1.from_api({"name": "s", "test_mode": True}, {})
        self.assertFalse(obj.forward_events)

    def test_from_api_null_fks(self):
        obj = EventStreamTransformMixin_v1.from_api({"name": "s", "eda_credential_id": None, "organization_id": None}, {})
        self.assertIsNone(obj.credential_name)
        self.assertIsNone(obj.organization_name)

    def test_endpoints(self):
        ops = EventStreamTransformMixin_v1.get_endpoint_operations()
        self.assertEqual(ops["create"].path, "/api/eda/v1/event-streams/")
        self.assertEqual(ops["update"].method, "PATCH")

    def test_lookup_field(self):
        self.assertEqual(EventStreamTransformMixin_v1.get_lookup_field(), "name")

    def test_find_query_scopes_to_organization(self):
        api_data = EventStreamTransformMixin_v1.from_ansible_data(AnsibleEventStream(name="s", organization_name="12"), self._ctx("find"))
        self.assertEqual(EventStreamTransformMixin_v1.get_find_list_query_params(api_data), {"organization_id": 12})


class TestEventStreamComparison(unittest.TestCase):
    """Verify FK names and numeric IDs converge in action comparisons."""

    def test_numeric_ids_match_current_named_references(self):
        action = ActionModule.__new__(ActionModule)
        manager = MagicMock()

        def lookup(endpoint, field, value, **kwargs):
            ids = {"organizations": {"Default": 7}, "eda-credentials": {"Event Credential": 42}}
            return ids[endpoint].get(value)

        manager.lookup_resource_id.side_effect = lookup
        action._client = manager
        desired = {"name": "stream", "organization_name": "7", "credential_name": "42", "forward_events": False}
        current = {"name": "stream", "organization_name": "Default", "credential_name": "Event Credential", "forward_events": False}

        self.assertFalse(action._should_update(desired, current))


if __name__ == "__main__":
    unittest.main()
