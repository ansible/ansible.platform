"""
API v1 Team dataclass and transform mixin.

Handles transformations between Ansible format and Gateway API v1 format.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APITeam_v1(BaseTransformMixin):
    """
    API v1 representation of a team.
    """

    name: Optional[str] = None
    organization: Optional[int] = None  # organization id for API
    description: Optional[str] = None

    # Read-only fields from API
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class TeamTransformMixin_v1(BaseTransformMixin):
    """
    Transform mixin for Team API v1.
    """

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APITeam_v1":
        """Create API instance from Ansible dataclass."""
        api_data = {}
        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
        description = getattr(ansible_instance, "description", None)
        organization = getattr(ansible_instance, "organization", None)
        organization_id = getattr(ansible_instance, "organization_id", None)
        new_organization = getattr(ansible_instance, "new_organization", None)
        op = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")
        include_nulls = (
            getattr(context, "include_nulls_for_update", False) if isinstance(context, TransformContext) else context.get("include_nulls_for_update", False)
        )

        # Resolve organization to id if not already set
        if organization_id is not None:
            api_data["organization"] = organization_id
        elif organization is not None:
            manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
            if manager:
                try:
                    ids = manager.lookup_organization_ids([organization])
                    if ids:
                        api_data["organization"] = ids[0]
                except Exception as e:
                    logger.debug("Lookup organization for team: %s", e)
                    # Re-raise for non-digit names: the caller specified an org that
                    # doesn't exist.  Propagate the "not found" message so that action
                    # plugins (and tests) can surface a clear failure instead of
                    # silently sending a wrong/missing organization in the API request.
                    if not str(organization).strip().isdigit():
                        raise
            if "organization" not in api_data and str(organization).isdigit():
                api_data["organization"] = int(organization)

        if op == "create":
            api_data["name"] = name or new_name
        elif op == "update":
            if new_name is not None:
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                # Regular update by name: echo the name back (idempotent).
                # If name is a digit string the caller used the integer PK for
                # lookup only — omit name from the PATCH body so we don't
                # accidentally rename the team to its own ID string.
                api_data["name"] = name
        else:
            # find / other operations — include name when available
            if name is not None:
                api_data["name"] = name

        if description is not None:
            api_data["description"] = description
        elif op == "update" and include_nulls:
            api_data["description"] = ""

        if new_organization is not None and op == "update":
            manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
            if manager:
                try:
                    ids = manager.lookup_organization_ids([new_organization])
                    if ids:
                        api_data["organization"] = ids[0]
                except Exception as e:
                    logger.debug("Lookup new_organization for team: %s", e)

        for field in ("id", "created", "modified", "url"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APITeam_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for team operations."""
        return {
            "create": EndpointOperation(
                path="/api/gateway/v1/teams/", method="POST", fields=["name", "description", "organization"], required_for="create", order=1
            ),
            "update": EndpointOperation(
                path="/api/gateway/v1/teams/{id}/",
                method="PATCH",
                fields=["name", "description", "organization"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(path="/api/gateway/v1/teams/{id}/", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1),
            "get": EndpointOperation(path="/api/gateway/v1/teams/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path="/api/gateway/v1/teams/", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def get_find_list_query_params(cls, ansible_data) -> Dict[str, Any]:
        """Extra query params for list find (e.g. organization scoping)."""
        # ansible_data is an APITeam_v1 instance whose 'organization' field already
        # holds the resolved integer FK (set by from_ansible_data).  The old name
        # 'organization_id' doesn't exist on the dataclass and always returned None,
        # causing the org filter to be silently omitted from every list query.
        org_id = getattr(ansible_data, "organization", None)
        if org_id is not None:
            return {"organization": org_id}
        return {}

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleTeam":
        """Transform from API format to Ansible format."""
        from ...ansible_models.team import AnsibleTeam

        org_id = api_data.get("organization")
        if isinstance(org_id, dict):
            org_id = org_id.get("id")
        organization = str(org_id) if org_id is not None else ""
        manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
        if manager and org_id is not None:
            try:
                names = manager.lookup_organization_names([org_id])
                if names:
                    organization = names[0]
            except Exception:
                pass

        ansible_data = {
            "name": api_data.get("name", ""),
            "organization": organization,
            "description": api_data.get("description"),
            "id": api_data.get("id"),
            "created": api_data.get("created"),
            "modified": api_data.get("modified"),
            "url": api_data.get("url"),
        }
        return AnsibleTeam(**ansible_data)
