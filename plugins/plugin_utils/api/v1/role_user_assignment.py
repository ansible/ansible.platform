"""
API v1 RoleUserAssignment dataclass and transform mixin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, Union, List

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext


def _resolve_fk(manager, endpoint: str, lookup_field: str, value) -> Optional[int]:
    """Resolve a name or id to an integer id."""
    if value is None:
        return None
    if str(value).isdigit():
        return int(value)
    try:
        return manager.lookup_resource_id(endpoint, lookup_field, str(value))
    except Exception:
        return None


@dataclass
class APIRoleUserAssignment_v1(BaseTransformMixin):
    """API v1 representation of a role-user assignment."""

    role_definition: Optional[int] = None
    user: Optional[int] = None
    user_ansible_id: Optional[str] = None
    object_id: Optional[int] = None
    object_ansible_id: Optional[str] = None

    # Read-only
    id: Optional[int] = None
    url: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None


class RoleUserAssignmentTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for RoleUserAssignment API v1."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIRoleUserAssignment_v1:
        api_data: Dict[str, Any] = {}
        manager = context.manager if isinstance(context, TransformContext) else context.get("manager")

        # Resolve role_definition name -> id
        role_definition = getattr(ansible_instance, "role_definition", None)
        if role_definition is not None and manager:
            resolved = _resolve_fk(manager, "role_definitions", "name", role_definition)
            if resolved is not None:
                api_data["role_definition"] = resolved
        elif role_definition is not None and str(role_definition).isdigit():
            api_data["role_definition"] = int(role_definition)

        # Resolve user name -> id
        user = getattr(ansible_instance, "user", None)
        if user is not None and manager:
            resolved = _resolve_fk(manager, "users", "username", user)
            if resolved is not None:
                api_data["user"] = resolved
        elif user is not None and str(user).isdigit():
            api_data["user"] = int(user)

        user_ansible_id = getattr(ansible_instance, "user_ansible_id", None)
        if user_ansible_id is not None:
            api_data["user_ansible_id"] = user_ansible_id

        object_id = getattr(ansible_instance, "object_id", None)
        if object_id is not None:
            api_data["object_id"] = int(object_id) if str(object_id).isdigit() else object_id

        object_ansible_id = getattr(ansible_instance, "object_ansible_id", None)
        if object_ansible_id is not None:
            api_data["object_ansible_id"] = object_ansible_id

        for ro in ("id", "url", "created", "modified"):
            val = getattr(ansible_instance, ro, None)
            if val is not None:
                api_data[ro] = val

        return APIRoleUserAssignment_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/gateway/v1/role_user_assignments/",
                method="POST",
                fields=["role_definition", "user", "user_ansible_id", "object_id", "object_ansible_id"],
                required_for="create",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/role_user_assignments/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/gateway/v1/role_user_assignments/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/gateway/v1/role_user_assignments/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "id"

    @classmethod
    def get_find_list_query_params(cls, ansible_data) -> Dict[str, Any]:
        """Build query params for finding an existing assignment."""
        params = {}
        role_def = getattr(ansible_data, "role_definition", None)
        if role_def is not None:
            params["role_definition"] = role_def
        user = getattr(ansible_data, "user", None)
        if user is not None:
            params["user"] = user
        user_ansible_id = getattr(ansible_data, "user_ansible_id", None)
        if user_ansible_id is not None:
            params["user_ansible_id"] = user_ansible_id
        object_id = getattr(ansible_data, "object_id", None)
        if object_id is not None:
            params["object_id"] = object_id
        object_ansible_id = getattr(ansible_data, "object_ansible_id", None)
        if object_ansible_id is not None:
            params["object_ansible_id"] = object_ansible_id
        return params

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ...ansible_models.role_user_assignment import AnsibleRoleUserAssignment

        return AnsibleRoleUserAssignment(
            role_definition=str(api_data.get("role_definition", "")),
            user=str(api_data.get("user")) if api_data.get("user") is not None else None,
            user_ansible_id=api_data.get("user_ansible_id"),
            object_id=api_data.get("object_id"),
            object_ansible_id=api_data.get("object_ansible_id"),
            id=api_data.get("id"),
            url=api_data.get("url"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
        )
