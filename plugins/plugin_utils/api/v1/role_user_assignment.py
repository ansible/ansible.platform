"""
API v1 RoleUserAssignment dataclass and transform mixin.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


def _resolve_fk(manager, endpoint: str, lookup_field: str, value) -> Optional[int]:
    """Resolve a name or id to an integer id.

    Returns the integer ID, or None if resolution fails.
    Exceptions are logged but not re-raised so callers can decide how to handle.
    """
    if value is None:
        return None
    if str(value).isdigit():
        return int(value)
    try:
        result = manager.lookup_resource_id(endpoint, lookup_field, str(value))
        if result is None:
            logger.debug("_resolve_fk: lookup_resource_id returned None for %s=%s in endpoint '%s'", lookup_field, value, endpoint)
        return result
    except Exception as exc:
        logger.debug("_resolve_fk: Failed to resolve %s=%s in endpoint '%s': %s: %s", lookup_field, value, endpoint, type(exc).__name__, exc)
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
            # Ensure object_id is always an integer for the API.
            if isinstance(object_id, int):
                api_data["object_id"] = object_id
            elif str(object_id).isdigit():
                api_data["object_id"] = int(object_id)
            elif manager:
                # object_id is a name string — derive entity type from role_definition to
                # make a targeted lookup rather than trying all common types blindly.
                role_def_name = getattr(ansible_instance, "role_definition", "") or ""
                _entity_candidates = []
                if role_def_name.lower().startswith("organization"):
                    _entity_candidates = ["organizations", "teams"]
                elif role_def_name.lower().startswith("team"):
                    _entity_candidates = ["teams", "organizations"]
                else:
                    _entity_candidates = ["organizations", "teams"]

                resolved = None
                for endpoint in _entity_candidates:
                    resolved = _resolve_fk(manager, endpoint, "name", object_id)
                    if resolved is not None:
                        api_data["object_id"] = resolved
                        break

                if resolved is None:
                    # All lookups failed — cannot send a name string as object_id to the API.
                    raise ValueError(
                        "Cannot resolve object name '%s' to an integer ID. "
                        "Checked endpoints: %s. "
                        "Ensure the resource exists or pass an integer object_id directly." % (object_id, ", ".join(_entity_candidates))
                    )
            else:
                # No manager available — we have no way to resolve the name.
                raise ValueError("object_id '%s' is not an integer and no manager is available to resolve it. Please provide an integer object_id." % object_id)

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
