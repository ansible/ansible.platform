"""
API v1 RoleTeamAssignment dataclass and transform mixin.

Mirrors the role_user_assignment pattern exactly, substituting
team/team_ansible_id for user/user_ansible_id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext


def _resolve_fk(manager, endpoint: str, lookup_field: str, value) -> Optional[int]:
    """Resolve a name or id string to an integer id via the manager."""
    if value is None:
        return None
    if str(value).isdigit():
        return int(value)
    try:
        return manager.lookup_resource_id(endpoint, lookup_field, str(value))
    except Exception:
        return None


@dataclass
class APIRoleTeamAssignment_v1:
    """API v1 wire format for a role-team assignment."""

    role_definition: Optional[int] = None
    team: Optional[int] = None
    team_ansible_id: Optional[str] = None
    object_id: Optional[int] = None
    object_ansible_id: Optional[str] = None

    # Read-only
    id: Optional[int] = None
    url: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None


class RoleTeamAssignmentTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for RoleTeamAssignment API v1."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIRoleTeamAssignment_v1:
        api_data: Dict[str, Any] = {}
        manager = context.manager if isinstance(context, TransformContext) else context.get("manager")

        # Resolve role_definition name → id
        role_definition = getattr(ansible_instance, "role_definition", None)
        if role_definition is not None and manager:
            resolved = _resolve_fk(manager, "role_definitions", "name", role_definition)
            if resolved is not None:
                api_data["role_definition"] = resolved
        elif role_definition is not None and str(role_definition).isdigit():
            api_data["role_definition"] = int(role_definition)

        # Resolve team name → id
        team = getattr(ansible_instance, "team", None)
        if team is not None and manager:
            resolved = _resolve_fk(manager, "teams", "name", team)
            if resolved is not None:
                api_data["team"] = resolved
        elif team is not None and str(team).isdigit():
            api_data["team"] = int(team)

        team_ansible_id = getattr(ansible_instance, "team_ansible_id", None)
        if team_ansible_id is not None:
            api_data["team_ansible_id"] = team_ansible_id

        object_id = getattr(ansible_instance, "object_id", None)
        if object_id is not None:
            if isinstance(object_id, int):
                api_data["object_id"] = object_id
            elif str(object_id).isdigit():
                api_data["object_id"] = int(object_id)
            elif manager:
                for endpoint in ("organizations", "teams"):
                    resolved = _resolve_fk(manager, endpoint, "name", object_id)
                    if resolved is not None:
                        api_data["object_id"] = resolved
                        break
                else:
                    api_data["object_id"] = object_id
            else:
                api_data["object_id"] = object_id

        object_ansible_id = getattr(ansible_instance, "object_ansible_id", None)
        if object_ansible_id is not None:
            api_data["object_ansible_id"] = object_ansible_id

        for ro_field in ("id", "url", "created", "modified"):
            val = getattr(ansible_instance, ro_field, None)
            if val is not None:
                api_data[ro_field] = val

        return APIRoleTeamAssignment_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/gateway/v1/role_team_assignments/",
                method="POST",
                fields=["role_definition", "team", "team_ansible_id", "object_id", "object_ansible_id"],
                required_for="create",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/role_team_assignments/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/gateway/v1/role_team_assignments/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/gateway/v1/role_team_assignments/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        # Assignments have no single unique name; lookup uses composite query params.
        return "role_definition"

    @classmethod
    def get_find_list_query_params(cls, ansible_data) -> Dict[str, Any]:
        """Build composite query params for finding an existing assignment."""
        params = {}
        role_def = getattr(ansible_data, "role_definition", None)
        if role_def is not None:
            params["role_definition"] = role_def
        team = getattr(ansible_data, "team", None)
        if team is not None:
            params["team"] = team
        team_ansible_id = getattr(ansible_data, "team_ansible_id", None)
        if team_ansible_id is not None:
            params["team_ansible_id"] = team_ansible_id
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
        from ...ansible_models.role_team_assignment import AnsibleRoleTeamAssignment

        return AnsibleRoleTeamAssignment(
            role_definition=str(api_data.get("role_definition", "")),
            team=str(api_data.get("team")) if api_data.get("team") is not None else None,
            team_ansible_id=api_data.get("team_ansible_id"),
            object_id=api_data.get("object_id"),
            object_ansible_id=api_data.get("object_ansible_id"),
            id=api_data.get("id"),
            url=api_data.get("url"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
        )
