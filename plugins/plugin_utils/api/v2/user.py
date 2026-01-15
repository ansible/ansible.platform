"""
API v2 User dataclass and transform mixin (mocked for POC testing).

Why this exists
---------------
AAP Gateway only exposes v1 today, but for ANSTRAT-1640 we want to validate that
our architecture can:
  - Discover multiple API versions from the filesystem (api/v1, api/v2, ...)
  - Select a version based on detected API version (from /ping)
  - Load version-specific classes without conflicts

This v2 implementation intentionally mirrors v1, but uses v2 endpoint paths so
we can exercise it against the local mock server.
"""

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, ClassVar, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

@dataclass
class APIUser_v2(BaseTransformMixin):
    """API v2 representation of a user (mock)."""

    username: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    is_superuser: Optional[bool] = None
    is_platform_auditor: Optional[bool] = None

    # Read-only fields from API
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None

    # For organizations - handled separately via associations
    organization_ids: Optional[List[int]] = None

class UserTransformMixin_v2(BaseTransformMixin):
    """
    Transform mixin for User API v2 (mock).

    Mirrors v1 behavior but uses v2 endpoint paths.
    """

    # Field mapping: ansible_field -> api_field or complex mapping
    _field_mapping: ClassVar[Dict[str, Any]] = {
        "username": "username",
        "email": "email",
        "first_name": "first_name",
        "last_name": "last_name",
        "password": "password",
        "is_superuser": "is_superuser",
        "is_platform_auditor": "is_platform_auditor",
        "id": "id",
        "created": "created",
        "modified": "modified",
        "url": "url",
        # Complex mapping for organizations (names <-> IDs)
        "organizations": {
            "api_field": "organization_ids",
            "forward_transform": "names_to_ids",
            "reverse_transform": "ids_to_names",
        },
    }

    _transform_registry: ClassVar[Dict[str, Any]] = {
        "names_to_ids": lambda names, ctx: ctx.manager.lookup_organization_ids(names) if names else [],
        "ids_to_names": lambda ids, ctx: ctx.manager.lookup_organization_names(ids) if ids else [],
    }

    @classmethod
    def from_ansible_data(
        cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]
    ) -> "APIUser_v2":
        logger.info(
            f"[v2] Transforming AnsibleUser -> APIUser_v2: username={getattr(ansible_instance, 'username', None)}"
        )
        api_data: Dict[str, Any] = {}

        simple_fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "is_superuser",
            "is_platform_auditor",
            "id",
            "created",
            "modified",
            "url",
        ]
        for field in simple_fields:
            value = getattr(ansible_instance, field, None)
            if value is not None:
                api_data[field] = value

        # organizations (names -> IDs)
        if getattr(ansible_instance, "organizations", None):
            org_names = ansible_instance.organizations
            if isinstance(context, TransformContext):
                api_data["organization_ids"] = context.manager.lookup_organization_ids(org_names)
            else:
                mgr = context.get("manager")
                api_data["organization_ids"] = mgr.lookup_organization_ids(org_names) if mgr else []

        return APIUser_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        # NOTE: v2 endpoints only exist on the local mock server today.
        return {
            "create": EndpointOperation(
                path="/api/gateway/v2/users/",
                method="POST",
                fields=[
                    "username",
                    "email",
                    "first_name",
                    "last_name",
                    "password",
                    "is_superuser",
                    "is_platform_auditor",
                ],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/gateway/v2/users/{id}/",
                method="PATCH",
                fields=[
                    "username",
                    "email",
                    "first_name",
                    "last_name",
                    "password",
                    "is_superuser",
                    "is_platform_auditor",
                ],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v2/users/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/gateway/v2/users/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/gateway/v2/users/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "username"

    def to_api(self, context: Union[TransformContext, Dict[str, Any]]) -> "APIUser_v2":
        # Reuse BaseTransformMixin behavior via the v1-style mapping pattern.
        api_data: Dict[str, Any] = {}
        for ansible_field, mapping in self._field_mapping.items():
            if not hasattr(self, ansible_field):
                continue
            value = getattr(self, ansible_field)
            if value is None:
                continue
            if isinstance(mapping, str):
                api_data[mapping] = value
            elif isinstance(mapping, dict):
                api_field = mapping["api_field"]
                transform_name = mapping.get("forward_transform")
                if transform_name and transform_name in self._transform_registry:
                    api_data[api_field] = self._transform_registry[transform_name](value, context)
                else:
                    api_data[api_field] = value
        return APIUser_v2(**api_data)

    @classmethod
    def from_api(
        cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]
    ) -> Dict[str, Any]:
        # Keep identical to v1 behavior: return dict so manager can add 'changed'
        ansible_data: Dict[str, Any] = {}
        for ansible_field, mapping in cls._field_mapping.items():
            if isinstance(mapping, str):
                if mapping in api_data:
                    ansible_data[ansible_field] = api_data[mapping]
            elif isinstance(mapping, dict):
                api_field = mapping["api_field"]
                transform_name = mapping.get("reverse_transform")
                if api_field in api_data:
                    value = api_data[api_field]
                    if transform_name and transform_name in cls._transform_registry:
                        # Normalize context
                        if isinstance(context, dict):
                            ctx = TransformContext(
                                manager=context["manager"],
                                session=context["session"],
                                cache=context.get("cache", {}),
                                api_version=context.get("api_version", "2"),
                            )
                        else:
                            ctx = context
                        ansible_data[ansible_field] = cls._transform_registry[transform_name](value, ctx)
                    else:
                        ansible_data[ansible_field] = value
        return ansible_data

