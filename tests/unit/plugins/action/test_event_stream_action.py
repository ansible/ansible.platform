# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the event_stream action plugin and transform mixin."""

import unittest
from dataclasses import asdict
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.action.event_stream import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.event_stream import AnsibleEventStream
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.event_stream import (
    EventStreamTransformMixin_v1,
)


class TestEventStreamActionPlugin(unittest.TestCase):
    """Test event_stream action plugin configuration."""

    def test_module_name(self):
        """MODULE_NAME matches the module filename."""
        self.assertEqual(ActionModule.MODULE_NAME, "event_stream")

    def test_model_class(self):
        """MODEL_CLASS points to the correct Ansible dataclass."""
        self.assertEqual(ActionModule.MODEL_CLASS, AnsibleEventStream)

    def test_deprecated_fields(self):
        """event_stream_type is registered as deprecated."""
        self.assertIn("event_stream_type", ActionModule._DEPRECATED_FIELDS)
        msg, version = ActionModule._DEPRECATED_FIELDS["event_stream_type"]
        self.assertIn("deprecated", msg.lower())
        self.assertEqual(version, "3.0.0")

    def test_mutable_fk_fields(self):
        """FK fields are registered as mutable for idempotency."""
        self.assertIn("credential_name", ActionModule._MUTABLE_FK_FIELDS)
        self.assertIn("organization_name", ActionModule._MUTABLE_FK_FIELDS)


class TestAnsibleEventStreamModel(unittest.TestCase):
    """Test AnsibleEventStream dataclass."""

    def test_basic_creation(self):
        """Minimal creation with only required field."""
        es = AnsibleEventStream(name="test-stream")
        self.assertEqual(es.name, "test-stream")
        self.assertIsNone(es.credential_name)
        self.assertIsNone(es.organization_name)
        self.assertIsNone(es.forward_events)
        self.assertIsNone(es.headers)
        self.assertIsNone(es.uuid)
        self.assertIsNone(es.event_stream_type)
        self.assertIsNone(es.id)

    def test_full_creation(self):
        """All fields populated correctly."""
        es = AnsibleEventStream(
            name="test-stream",
            new_name="renamed-stream",
            credential_name="my-cred",
            organization_name="Default",
            event_stream_type="hmac",
            forward_events=True,
            headers="Content-Type,X-Custom",
            uuid="550e8400-e29b-41d4-a716-446655440000",
            id=42,
        )
        self.assertEqual(es.name, "test-stream")
        self.assertEqual(es.new_name, "renamed-stream")
        self.assertEqual(es.credential_name, "my-cred")
        self.assertEqual(es.organization_name, "Default")
        self.assertEqual(es.event_stream_type, "hmac")
        self.assertTrue(es.forward_events)
        self.assertEqual(es.headers, "Content-Type,X-Custom")
        self.assertEqual(es.uuid, "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(es.id, 42)


class TestEventStreamTransformMixin(unittest.TestCase):
    """Test EventStreamTransformMixin_v1 forward and reverse transforms."""

    def _make_context(self, operation="create", manager=None):
        """Create a mock TransformContext as a dict (accepted by the transform mixin)."""
        return {"operation": operation, "manager": manager}

    def _make_manager(self, credential_id=10, org_id=1):
        """Create a mock manager with lookup_resource_id support."""
        manager = MagicMock()

        def lookup_side_effect(endpoint, field, value, **kwargs):
            if endpoint == "eda-credentials":
                return credential_id
            if endpoint == "organizations":
                return org_id
            raise ValueError("Unknown endpoint: %s" % endpoint)

        manager.lookup_resource_id.side_effect = lookup_side_effect
        return manager

    # ------------------------------------------------------------------ #
    # from_ansible_data tests
    # ------------------------------------------------------------------ #

    def test_basic_create(self):
        """Basic create produces correct API fields."""
        manager = self._make_manager(credential_id=10, org_id=1)
        ctx = self._make_context("create", manager)
        ansible_obj = AnsibleEventStream(
            name="my-stream",
            credential_name="My Credential",
            organization_name="Default",
        )
        api_obj = EventStreamTransformMixin_v1.from_ansible_data(ansible_obj, ctx)

        self.assertEqual(api_obj.name, "my-stream")
        self.assertEqual(api_obj.eda_credential_id, 10)
        self.assertEqual(api_obj.organization_id, 1)

    def test_forward_events_true_to_test_mode_false(self):
        """forward_events=True becomes test_mode=False."""
        manager = self._make_manager()
        ctx = self._make_context("create", manager)
        ansible_obj = AnsibleEventStream(
            name="stream-1",
            credential_name="cred",
            organization_name="Default",
            forward_events=True,
        )
        api_obj = EventStreamTransformMixin_v1.from_ansible_data(ansible_obj, ctx)
        self.assertFalse(api_obj.test_mode)

    def test_forward_events_false_to_test_mode_true(self):
        """forward_events=False becomes test_mode=True."""
        manager = self._make_manager()
        ctx = self._make_context("create", manager)
        ansible_obj = AnsibleEventStream(
            name="stream-2",
            credential_name="cred",
            organization_name="Default",
            forward_events=False,
        )
        api_obj = EventStreamTransformMixin_v1.from_ansible_data(ansible_obj, ctx)
        self.assertTrue(api_obj.test_mode)

    def test_forward_events_none_skips_test_mode(self):
        """forward_events=None does not set test_mode."""
        ctx = self._make_context("create")
        ansible_obj = AnsibleEventStream(name="stream")
        api_obj = EventStreamTransformMixin_v1.from_ansible_data(ansible_obj, ctx)
        self.assertIsNone(api_obj.test_mode)

    def test_headers_rename(self):
        """headers maps to additional_data_headers."""
        manager = self._make_manager()
        ctx = self._make_context("create", manager)
        ansible_obj = AnsibleEventStream(
            name="stream",
            credential_name="cred",
            organization_name="Default",
            headers="Content-Type,X-Custom",
        )
        api_obj = EventStreamTransformMixin_v1.from_ansible_data(ansible_obj, ctx)
        self.assertEqual(api_obj.additional_data_headers, "Content-Type,X-Custom")

    def test_uuid_passthrough(self):
        """Valid UUID is passed through to API."""
        manager = self._make_manager()
        ctx = self._make_context("create", manager)
        ansible_obj = AnsibleEventStream(
            name="stream",
            credential_name="cred",
            organization_name="Default",
            uuid="550e8400-e29b-41d4-a716-446655440000",
        )
        api_obj = EventStreamTransformMixin_v1.from_ansible_data(ansible_obj, ctx)
        self.assertEqual(api_obj.uuid, "550e8400-e29b-41d4-a716-446655440000")

    def test_uuid_invalid_raises(self):
        """Invalid UUID raises ValueError from model validation."""
        with self.assertRaises(ValueError) as cm:
            AnsibleEventStream(name="stream", uuid="not-a-uuid")
        self.assertIn("UUID", str(cm.exception))

    def test_new_name_on_update(self):
        """new_name is used as name on update operations."""
        ctx = self._make_context("update")
        ansible_obj = AnsibleEventStream(
            name="old-name",
            new_name="new-name",
        )
        api_obj = EventStreamTransformMixin_v1.from_ansible_data(ansible_obj, ctx)
        self.assertEqual(api_obj.name, "new-name")

    def test_new_name_ignored_on_create(self):
        """On create, name takes precedence over new_name."""
        ctx = self._make_context("create")
        ansible_obj = AnsibleEventStream(
            name="original",
            new_name="should-not-be-used",
        )
        api_obj = EventStreamTransformMixin_v1.from_ansible_data(ansible_obj, ctx)
        self.assertEqual(api_obj.name, "original")

    def test_optional_fields_omitted_when_none(self):
        """Optional fields are not set on API object when not provided."""
        ctx = self._make_context("create")
        ansible_obj = AnsibleEventStream(name="minimal-stream")
        api_obj = EventStreamTransformMixin_v1.from_ansible_data(ansible_obj, ctx)
        self.assertIsNone(api_obj.test_mode)
        self.assertIsNone(api_obj.additional_data_headers)
        self.assertIsNone(api_obj.uuid)

    def test_credential_as_numeric_id(self):
        """Numeric credential_name is treated as an ID directly."""
        ctx = self._make_context("create", manager=None)
        ansible_obj = AnsibleEventStream(
            name="stream",
            credential_name="42",
            organization_name="7",
        )
        api_obj = EventStreamTransformMixin_v1.from_ansible_data(ansible_obj, ctx)
        self.assertEqual(api_obj.eda_credential_id, 42)
        self.assertEqual(api_obj.organization_id, 7)

    def test_credential_lookup_uses_eda_service(self):
        """credential_name lookup passes service='eda' to lookup_resource_id."""
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 42
        ctx = self._make_context("create", manager)
        ansible_obj = AnsibleEventStream(
            name="stream",
            credential_name="My Credential",
            organization_name="1",
        )
        EventStreamTransformMixin_v1.from_ansible_data(ansible_obj, ctx)
        manager.lookup_resource_id.assert_called_once_with("eda-credentials", "name", "My Credential", service="eda")

    def test_organization_lookup_uses_default_service(self):
        """organization_name lookup does NOT pass service='eda' (gateway-managed)."""
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 1
        ctx = self._make_context("create", manager)
        ansible_obj = AnsibleEventStream(
            name="stream",
            credential_name="42",
            organization_name="Default",
        )
        EventStreamTransformMixin_v1.from_ansible_data(ansible_obj, ctx)
        manager.lookup_resource_id.assert_called_once_with("organizations", "name", "Default")

    def test_event_stream_type_ignored(self):
        """Deprecated event_stream_type field is not sent to API."""
        ctx = self._make_context("create")
        ansible_obj = AnsibleEventStream(
            name="stream",
            event_stream_type="hmac",
        )
        api_obj = EventStreamTransformMixin_v1.from_ansible_data(ansible_obj, ctx)
        api_dict = asdict(api_obj)
        self.assertNotIn("event_stream_type", api_dict)

    # ------------------------------------------------------------------ #
    # from_api tests
    # ------------------------------------------------------------------ #

    def test_from_api_basic(self):
        """from_api creates AnsibleEventStream with correct field mapping."""
        ctx = self._make_context()
        api_data = {
            "id": 42,
            "name": "my-stream",
            "eda_credential_id": 10,
            "organization_id": 1,
            "test_mode": False,
            "additional_data_headers": "Content-Type",
            "uuid": "550e8400-e29b-41d4-a716-446655440000",
        }
        ansible_obj = EventStreamTransformMixin_v1.from_api(api_data, ctx)

        self.assertIsInstance(ansible_obj, AnsibleEventStream)
        self.assertEqual(ansible_obj.name, "my-stream")
        self.assertEqual(ansible_obj.id, 42)
        # Without a manager, FK IDs are returned as string fallback
        self.assertEqual(ansible_obj.credential_name, "10")
        self.assertEqual(ansible_obj.organization_name, "1")
        self.assertTrue(ansible_obj.forward_events)  # test_mode=False -> forward_events=True
        self.assertEqual(ansible_obj.headers, "Content-Type")
        self.assertEqual(ansible_obj.uuid, "550e8400-e29b-41d4-a716-446655440000")

    def test_from_api_null_fk_ids(self):
        """Null FK IDs result in None credential_name / organization_name."""
        ctx = self._make_context()
        api_data = {"name": "stream"}
        ansible_obj = EventStreamTransformMixin_v1.from_api(api_data, ctx)
        self.assertIsNone(ansible_obj.credential_name)
        self.assertIsNone(ansible_obj.organization_name)

    def test_from_api_test_mode_true(self):
        """test_mode=True becomes forward_events=False."""
        ctx = self._make_context()
        api_data = {"name": "stream", "test_mode": True}
        ansible_obj = EventStreamTransformMixin_v1.from_api(api_data, ctx)
        self.assertFalse(ansible_obj.forward_events)

    def test_from_api_test_mode_none(self):
        """Absent test_mode results in forward_events=None."""
        ctx = self._make_context()
        api_data = {"name": "stream"}
        ansible_obj = EventStreamTransformMixin_v1.from_api(api_data, ctx)
        self.assertIsNone(ansible_obj.forward_events)

    # ------------------------------------------------------------------ #
    # Endpoint and lookup tests
    # ------------------------------------------------------------------ #

    def test_endpoint_operations(self):
        """All CRUD operations are defined with correct paths."""
        ops = EventStreamTransformMixin_v1.get_endpoint_operations()
        self.assertIn("create", ops)
        self.assertIn("update", ops)
        self.assertIn("delete", ops)
        self.assertIn("get", ops)
        self.assertIn("list", ops)
        self.assertEqual(ops["create"].path, "/api/eda/v1/event-streams/")
        self.assertEqual(ops["create"].method, "POST")
        self.assertEqual(ops["update"].path, "/api/eda/v1/event-streams/{id}/")
        self.assertEqual(ops["update"].method, "PATCH")
        self.assertEqual(ops["delete"].method, "DELETE")

    def test_lookup_field(self):
        """Lookup field is name."""
        self.assertEqual(EventStreamTransformMixin_v1.get_lookup_field(), "name")

    def test_find_list_query_params(self):
        """Query params include name for lookup."""
        ansible_obj = AnsibleEventStream(name="my-stream")
        params = EventStreamTransformMixin_v1.get_find_list_query_params(ansible_obj)
        self.assertEqual(params, {"name": "my-stream"})


if __name__ == "__main__":
    unittest.main()
