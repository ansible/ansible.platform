"""
API v1 RoleUserAssignment dataclass and transform mixin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext


def _resolve_fk(manager, endpoint: str, lookup_field: str, value) -> Optional[str]:
    if value is None:
        return None
    if str(value).isdigit():
        return str(value)
    try:
        return str(manager.lookup_resource_id(endpoint, lookup_field, str(value)))
    except Exception:
        return None


@dataclass
class APIRoleUserAssignment_v1:
    """API v1 representation of a role-user assignment."""

    role_definition: Optional[str] = None
    user: Optional[str] = None
    user_ansible_id: Optional[str] = None
    object_id: Optional[str] = None
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

        def _get(key):
            if isinstance(ansible_instance, dict):
                return ansible_instance.get(key)
            return getattr(ansible_instance, key, None)

        role_definition = _get("role_definition")
        if role_definition is not None and manager:
            resolved = _resolve_fk(manager, "role_definitions", "name", role_definition)
            if resolved is not None:
                api_data["role_definition"] = str(resolved)
        elif role_definition is not None:
            api_data["role_definition"] = str(role_definition)

        user = _get("user")
        if user is not None and manager:
            resolved = _resolve_fk(manager, "users", "username", user)
            if resolved is not None:
                api_data["user"] = str(resolved)
        elif user is not None:
            api_data["user"] = str(user)

        user_ansible_id = _get("user_ansible_id")
        if user_ansible_id is not None:
            api_data["user_ansible_id"] = str(user_ansible_id)

        object_id = _get("object_id")
        if object_id is not None:
            if isinstance(object_id, int) or str(object_id).isdigit():
                api_data["object_id"] = str(object_id)
            elif manager:
                for endpoint in ("organizations", "teams", "projects", "inventories", "credentials"):
                    resolved = _resolve_fk(manager, endpoint, "name", object_id)
                    if resolved is not None:
                        api_data["object_id"] = str(resolved)
                        break
                else:
                    api_data["object_id"] = str(object_id)
            else:
                api_data["object_id"] = str(object_id)

        object_ansible_id = _get("object_ansible_id")
        if object_ansible_id is not None:
            api_data["object_ansible_id"] = str(object_ansible_id)

        for ro_field in ("id", "url", "created", "modified"):
            val = _get(ro_field)
            if val is not None:
                api_data[ro_field] = val

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

        def _get(key):
            if isinstance(ansible_data, dict):
                return ansible_data.get(key)
            return getattr(ansible_data, key, None)

        role_definition = _get("role_definition")
        if role_definition is not None:
            params["role_definition"] = str(role_definition)

        user = _get("user")
        if user is not None:
            params["user"] = str(user)

        user_ansible_id = _get("user_ansible_id")
        if user_ansible_id is not None:
            params["user_ansible_id"] = str(user_ansible_id)

        object_id = _get("object_id")
        if object_id is not None:
            params["object_id"] = str(object_id)

        object_ansible_id = _get("object_ansible_id")
        if object_ansible_id is not None:
            params["object_ansible_id"] = str(object_ansible_id)

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
