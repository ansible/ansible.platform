"""Tests for clearing omitted associations during enforced updates."""

from dataclasses import dataclass
from typing import Optional
from unittest import TestCase
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import EndpointOperation, TransformContext


@dataclass
class _AnsibleResource:
    id: int
    name: str
    organization: Optional[int] = None
    credential: Optional[int] = None


@dataclass
class _APIResource:
    id: Optional[int] = None
    name: Optional[str] = None
    organization: Optional[int] = None
    credential: Optional[int] = None


class _ResourceMixin:
    @classmethod
    def from_ansible_data(cls, ansible_data, context):
        return _APIResource(
            id=ansible_data.id,
            name=ansible_data.name,
            organization=ansible_data.organization,
            credential=ansible_data.credential,
        )

    @classmethod
    def get_endpoint_operations(cls):
        return {
            "update": EndpointOperation(
                path="/resources/{id}/",
                method="PATCH",
                fields=["id", "name", "organization", "credential"],
                path_params=["id"],
                required_for="update",
            )
        }

    @classmethod
    def from_api(cls, api_data, context):
        return _APIResource(**api_data)

    @classmethod
    def get_lookup_field(cls):
        return "name"


class TestUpdateResourceEnforcedNulls(TestCase):
    def setUp(self):
        self.service = PlatformService.__new__(PlatformService)
        self.service._find_resource = MagicMock(return_value={"id": 42, "name": "resource", "organization": 10, "credential": 20})
        self.service._execute_operations = MagicMock(return_value={"id": 42, "name": "resource"})
        self.ansible_data = _AnsibleResource(id=42, name="resource")

    def _update(self, enforced):
        context = TransformContext(
            manager=self.service,
            session=MagicMock(),
            cache={},
            api_version="1",
            operation="update",
            include_nulls_for_update=enforced,
        )
        return self.service._update_resource(self.ansible_data, _ResourceMixin, context)

    def test_enforced_update_clears_omitted_organization_and_credential(self):
        self._update(enforced=True)

        api_data = self.service._execute_operations.call_args.args[1]
        kwargs = self.service._execute_operations.call_args.kwargs
        self.assertIsNone(api_data.organization)
        self.assertIsNone(api_data.credential)
        self.assertEqual(kwargs["fields_to_null"], {"organization", "credential"})

    def test_non_enforced_update_preserves_omitted_organization_and_credential(self):
        self._update(enforced=False)

        api_data = self.service._execute_operations.call_args.args[1]
        kwargs = self.service._execute_operations.call_args.kwargs
        self.assertEqual(api_data.organization, 10)
        self.assertEqual(api_data.credential, 20)
        self.assertEqual(kwargs["fields_to_null"], set())
