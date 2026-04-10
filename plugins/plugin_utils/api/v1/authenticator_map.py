"""
API v1 Authenticator Map dataclass and transform mixin.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIAuthenticatorMap_v1(BaseTransformMixin):
    """API v1 representation of an authenticator map."""

    name: Optional[str] = None
    authenticator: Optional[int] = None
    revoke: Optional[bool] = None
    map_type: Optional[str] = None
    team: Optional[str] = None
    organization: Optional[str] = None
    role: Optional[str] = None
    triggers: Optional[Dict[str, Any]] = None
    order: Optional[int] = None

    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class AuthenticatorMapTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for Authenticator Map API v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIAuthenticatorMap_v1":
        api_data = {}
        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
        op = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")
        if op == "create":
            api_data["name"] = name or new_name
        elif op == "update":
            if new_name is not None:
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                api_data["name"] = name
        else:
            # find / other operations — include name when available
            if name is not None:
                api_data["name"] = name
        auth = getattr(ansible_instance, "authenticator", None)
        if auth is not None:
            manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
            if manager:
                try:
                    api_data["authenticator"] = manager.lookup_resource_id("authenticators", "name", str(auth))
                except Exception as e:
                    logger.debug("Lookup authenticator for authenticator_map: %s", e)
            if "authenticator" not in api_data:
                if str(auth).strip().isdigit():
                    api_data["authenticator"] = int(auth)
                else:
                    # Authenticator name given but not resolvable to an ID.
                    # Use sentinel 0 so find queries return nothing (no resource
                    # can belong to a non-existent authenticator), and create/
                    # update will fail with a clear FK validation error from the API.
                    api_data["authenticator"] = 0
        new_auth = getattr(ansible_instance, "new_authenticator", None)
        if new_auth is not None and op == "update":
            manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
            if manager:
                try:
                    api_data["authenticator"] = manager.lookup_resource_id("authenticators", "name", str(new_auth))
                except Exception as e:
                    logger.debug("Lookup new_authenticator for authenticator_map: %s", e)
            if "authenticator" not in api_data and str(new_auth).isdigit():
                api_data["authenticator"] = int(new_auth)
        for field in ("revoke", "map_type", "team", "organization", "role", "triggers", "order"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
        for field in ("id", "created", "modified", "url"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
        return APIAuthenticatorMap_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = ["name", "authenticator", "revoke", "map_type", "team", "organization", "role", "triggers", "order"]
        return {
            "create": EndpointOperation(path="/api/gateway/v1/authenticator_maps/", method="POST", fields=fields, required_for="create", order=1),
            "update": EndpointOperation(
                path="/api/gateway/v1/authenticator_maps/{id}/", method="PATCH", fields=fields, path_params=["id"], required_for="update", order=1
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/authenticator_maps/{id}/", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1
            ),
            "get": EndpointOperation(
                path="/api/gateway/v1/authenticator_maps/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1
            ),
            "list": EndpointOperation(path="/api/gateway/v1/authenticator_maps/", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    # Fields that are INCOMPATIBLE with each map_type and must be sent as null
    # when the map_type changes to a restrictive type.  Used by _update_resource
    # in platform_manager.py via the get_fields_to_null_for_update hook.
    _MAP_TYPE_EXCLUDED_FIELDS: Dict[str, tuple] = {
        "allow": ("role", "team", "organization"),
        "is_superuser": ("role", "team", "organization"),
        "organization": ("team",),
        "role": ("team", "organization"),
        # "team" supports all fields — nothing to clear
    }

    @classmethod
    def get_fields_to_null_for_update(cls, api_data) -> frozenset:
        """
        Return the set of field names that must be sent as null in the PATCH.

        Called by _update_resource after the current-data merge so it can
        send explicit null values to clear server-side fields that are
        incompatible with the new map_type.

        Example: changing map_type from 'team' (which had role='Team Admin')
        to 'is_superuser' must PATCH role=null and team=null, otherwise the
        API rejects the request with 'You cannot specify role with the
        selected map type'.
        """
        map_type = getattr(api_data, "map_type", None)
        if not map_type:
            return frozenset()
        return frozenset(cls._MAP_TYPE_EXCLUDED_FIELDS.get(map_type, ()))

    @classmethod
    def get_find_list_query_params(cls, ansible_data) -> Dict[str, Any]:
        """Include authenticator id for composite find (name + authenticator)."""
        # ansible_data here is an APIAuthenticatorMap_v1 (post-transform), which
        # stores the resolved FK integer in the 'authenticator' field — not
        # 'authenticator_id' (which lives on AnsibleAuthenticatorMap pre-transform).
        aid = getattr(ansible_data, "authenticator", None)
        if aid is not None:
            return {"authenticator": aid}
        return {}

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleAuthenticatorMap":
        from ...ansible_models.authenticator_map import AnsibleAuthenticatorMap

        auth = api_data.get("authenticator")
        return AnsibleAuthenticatorMap(
            name=api_data.get("name", ""),
            authenticator=str(auth) if auth is not None else "",
            revoke=api_data.get("revoke"),
            map_type=api_data.get("map_type"),
            team=api_data.get("team"),
            organization=api_data.get("organization"),
            role=api_data.get("role"),
            triggers=api_data.get("triggers"),
            order=api_data.get("order"),
            id=api_data.get("id"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )


# Alias for loader: module name "authenticator_map" -> title() "Authenticator_Map"
