"""
API v1 RoleTeamAssignment dataclass and transform mixin.

Mirrors the role_user_assignment pattern exactly, substituting
team/team_ansible_id for user/user_ansible_id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext
from ...resource_type_map import (
    ASSIGNMENT_TYPE_PATH_MAP,
    CONTROLLER_NON_ORG_TYPES,
    GATEWAY_ORG_TYPES,
    ORGANIZATION_PATH_MAP,
    service_kind,
)


def _resolve_fk(manager, endpoint: str, lookup_field: str, value, display=None) -> Optional[str]:
    """Resolve a name or id string to an integer id via the manager.

    Returns the resolved numeric ID as a string on success.
    Returns the original value as a string on lookup failure and emits a
    warning (if a display object is provided) so operators can diagnose
    the issue.  The Gateway will typically reject non-integer values with
    a 400 error, but the warning makes the root cause (failed lookup)
    immediately visible in playbook output.
    """
    if value is None:
        return None
    if value == "":
        return None
    if str(value).isdigit():
        return str(value)
    try:
        return str(manager.lookup_resource_id(endpoint, lookup_field, str(value)))
    except Exception:
        # Lookup failed (team not found, API error, etc.).
        # Return the original value so the caller can still include it in the
        # payload. The Gateway will respond with a useful error if the value
        # is invalid, rather than silently missing the field.
        if display:
            display.warning(
                "Failed to resolve %s '%s' to an ID via '%s'. "
                "The name will be sent as-is. If the API rejects this, "
                "verify the %s exists and is accessible with current "
                "credentials." % (lookup_field, value, endpoint, lookup_field)
            )
        return str(value)


def _search_results(payload):
    return payload.get("results", payload.get("data", [])) or []


def _matches_org(item, org_id):
    for key in ("organization_id", "organization"):
        value = item.get(key)
        if value is None:
            continue
        if isinstance(value, dict):
            value = value.get("id")
        if str(value) == str(org_id):
            return True
    return False


def _result_id(item, name, lookup_path):
    if "id" in item:
        return item["id"]
    if "prn" in item:
        return str(item["prn"]).rsplit(":", maxsplit=1)[-1]
    raise ValueError("Resource '%s' at %s returned no 'id' field" % (name, lookup_path))


def _resolve_organization_id(manager, organization, service):
    endpoint = ORGANIZATION_PATH_MAP.get(service)
    if endpoint is None:
        return manager.lookup_resource_id("organizations", "name", organization)

    payload = manager.search_api(endpoint, query_params={"name": organization})
    results = [result for result in _search_results(payload) if result.get("name") == organization]
    if len(results) != 1:
        raise ValueError("Expected exactly one organization named '%s' on %s, got %s" % (organization, service, len(results)))
    return _result_id(results[0], organization, "organizations")


def _resolve_named_object_id(manager, obj):
    obj_type = obj["type"]
    name = obj["name"]
    organization = obj.get("organization")
    lookup_path = ASSIGNMENT_TYPE_PATH_MAP.get(obj_type, obj_type)
    service = service_kind(obj_type)

    if organization:
        if service == "hub":
            raise ValueError("organization is not supported for Hub types such as '%s'" % obj_type)
        if service == "controller" and obj_type in CONTROLLER_NON_ORG_TYPES:
            raise ValueError("organization is not supported for Controller types such as '%s'" % obj_type)
        if service == "gateway" and obj_type not in GATEWAY_ORG_TYPES:
            raise ValueError("organization is only supported for Gateway type 'teams' (got '%s')" % obj_type)

    org_id = _resolve_organization_id(manager, organization, service) if organization else None
    query = {"name": name}
    if org_id is not None and service == "controller":
        query["organization"] = org_id
    if org_id is not None and service == "gateway" and obj_type == "teams":
        query["organization"] = org_id

    if isinstance(lookup_path, str) and lookup_path.startswith("/api/") and not lookup_path.startswith("/api/gateway/"):
        payload = manager.search_api(lookup_path, query_params=query)
        results = [result for result in _search_results(payload) if result.get("name") == name]
        if org_id is not None:
            results = [result for result in results if _matches_org(result, org_id)]
        if len(results) != 1:
            scope = " in organization '%s'" % organization if organization else ""
            raise ValueError("Expected exactly one %s named '%s'%s at %s, got %s" % (obj_type, name, scope, lookup_path, len(results)))
        return str(_result_id(results[0], name, lookup_path))

    if org_id is not None and obj_type == "teams":
        payload = manager.search_api("teams", query_params=query)
        results = [result for result in _search_results(payload) if result.get("name") == name and _matches_org(result, org_id)]
        if len(results) != 1:
            raise ValueError("Expected exactly one team named '%s' in organization '%s', got %s" % (name, organization, len(results)))
        return str(_result_id(results[0], name, "teams"))

    return str(manager.lookup_resource_id(lookup_path, "name", name))


@dataclass
class APIRoleTeamAssignment_v1:
    """API v1 wire format for a role-team assignment."""

    role_definition: Optional[str] = None
    team: Optional[str] = None
    team_ansible_id: Optional[str] = None
    object_id: Optional[str] = None
    object_ansible_id: Optional[str] = None

    id: Optional[int] = None
    url: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None


class RoleTeamAssignmentTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for RoleTeamAssignment API v1."""

    @classmethod
    def resolve(cls, ansible_instance, context):
        """Resolve one named assignment object as an execute() operation."""
        manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
        if isinstance(ansible_instance, dict):
            object_lookup = ansible_instance.get("object_lookup")
        else:
            object_lookup = getattr(ansible_instance, "_object_lookup", None)
        if not manager:
            raise ValueError("object lookup requires a PlatformService manager context")
        if not isinstance(object_lookup, dict) or not object_lookup.get("name") or not object_lookup.get("type"):
            raise ValueError("object_lookup must include both 'name' and 'type'")
        return {"object_id": _resolve_named_object_id(manager, object_lookup)}

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIRoleTeamAssignment_v1:
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

        team = _get("team")
        if team is not None and manager:
            resolved = _resolve_fk(manager, "teams", "name", team)
            if resolved is not None:
                api_data["team"] = str(resolved)
        elif team is not None:
            api_data["team"] = str(team)

        team_ansible_id = _get("team_ansible_id")
        if team_ansible_id is not None and team_ansible_id != "":
            api_data["team_ansible_id"] = str(team_ansible_id)

        object_id = _get("object_id")
        if object_id is not None:
            if isinstance(object_id, int) or str(object_id).isdigit():
                api_data["object_id"] = str(object_id)
            elif manager:
                for endpoint in ("organizations", "teams"):
                    resolved = _resolve_fk(manager, endpoint, "name", object_id)
                    if resolved is not None:
                        api_data["object_id"] = str(resolved)
                        break
                else:
                    api_data["object_id"] = str(object_id)
            else:
                api_data["object_id"] = str(object_id)

        object_ansible_id = _get("object_ansible_id")
        if object_ansible_id is not None and object_ansible_id != "":
            api_data["object_ansible_id"] = str(object_ansible_id)

        for ro_field in ("id", "url", "created", "modified"):
            val = _get(ro_field)
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
        return "id"

    @classmethod
    def get_find_list_query_params(cls, ansible_data) -> Dict[str, Any]:
        """Build composite query params for finding an existing assignment."""
        params = {}

        def _get(key):
            if isinstance(ansible_data, dict):
                return ansible_data.get(key)
            return getattr(ansible_data, key, None)

        role_def = _get("role_definition")
        if role_def is not None:
            params["role_definition"] = str(role_def)
        team = _get("team")
        if team is not None:
            params["team"] = str(team)
        team_ansible_id = _get("team_ansible_id")
        if team_ansible_id is not None and team_ansible_id != "":
            params["team_ansible_id"] = str(team_ansible_id)
        object_id = _get("object_id")
        if object_id is not None:
            params["object_id"] = str(object_id)
        object_ansible_id = _get("object_ansible_id")
        if object_ansible_id is not None and object_ansible_id != "":
            params["object_ansible_id"] = str(object_ansible_id)

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
