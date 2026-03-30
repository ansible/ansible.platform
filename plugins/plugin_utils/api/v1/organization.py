"""
API v1 Organization dataclass and transform mixin.

Handles transformations between Ansible format and Gateway API v1 format.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIOrganization_v1(BaseTransformMixin):
    """
    API v1 representation of an organization.
    """

    name: Optional[str] = None
    description: Optional[str] = None

    # Read-only fields from API
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class OrganizationTransformMixin_v1(BaseTransformMixin):
    """
    Transform mixin for Organization API v1.
    """

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIOrganization_v1":
        """
        Create API instance from Ansible dataclass.

        For update we send new_name as name if provided; the API expects 'name' in the body.
        """
        api_data = {}
        # Create: use name; Update: use new_name if set, else keep existing (we don't send name on PATCH if no rename)
        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
        description = getattr(ansible_instance, "description", None)
        op = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")
        include_nulls = (
            getattr(context, "include_nulls_for_update", False) if isinstance(context, TransformContext) else context.get("include_nulls_for_update", False)
        )

        if op == "create":
            api_data["name"] = name or new_name
        elif op == "update":
            if new_name is not None:
                # Explicit rename: send new_name as the new name field in the PATCH body.
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                # Regular update looked up by name: echo the name back so the record
                # keeps its current name (API is fine with name==current_name in PATCH).
                api_data["name"] = name
            # If name is a digit string the caller used the integer PK for lookup only
            # (e.g. name: "1001").  Don't include name in the PATCH body so we don't
            # accidentally rename the org to its own ID string.

        if description is not None:
            api_data["description"] = description
        elif op == "update" and include_nulls:
            api_data["description"] = ""

        # Read-only from API (for building URL in execute)
        for field in ("id", "created", "modified", "url"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIOrganization_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for organization operations."""
        return {
            "create": EndpointOperation(path="/api/gateway/v1/organizations/", method="POST", fields=["name", "description"], required_for="create", order=1),
            "update": EndpointOperation(
                path="/api/gateway/v1/organizations/{id}/", method="PATCH", fields=["name", "description"], path_params=["id"], required_for="update", order=1
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/organizations/{id}/", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1
            ),
            "get": EndpointOperation(path="/api/gateway/v1/organizations/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path="/api/gateway/v1/organizations/", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleOrganization":
        """Transform from API format to Ansible format."""
        from ...ansible_models.organization import AnsibleOrganization

        ansible_data = {
            "name": api_data.get("name", ""),
            "description": api_data.get("description"),
            "id": api_data.get("id"),
            "created": api_data.get("created"),
            "modified": api_data.get("modified"),
            "url": api_data.get("url"),
        }
        return AnsibleOrganization(**ansible_data)
