"""
API v1 Role Definition dataclass and transform mixin.

Handles transformations between Ansible format and Gateway API v1 format.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIRoleDefinition_v1(BaseTransformMixin):
    """
    API v1 representation of a role definition.
    """

    name: Optional[str] = None
    description: Optional[str] = None
    content_type: Optional[str] = None
    permissions: Optional[List[str]] = None

    # Read-only fields from API
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class RoleDefinitionTransformMixin_v1(BaseTransformMixin):
    """
    Transform mixin for Role Definition API v1.
    """

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIRoleDefinition_v1":
        """Create API instance from Ansible dataclass."""
        api_data = {}
        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
        description = getattr(ansible_instance, "description", None)
        content_type = getattr(ansible_instance, "content_type", None)
        permissions = getattr(ansible_instance, "permissions", None)
        op = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")
        include_nulls = (
            getattr(context, "include_nulls_for_update", False) if isinstance(context, TransformContext) else context.get("include_nulls_for_update", False)
        )

        if op == "create":
            api_data["name"] = name or new_name
        elif op == "update":
            if new_name is not None:
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                api_data["name"] = name

        if description is not None:
            api_data["description"] = description
        elif op == "update" and include_nulls:
            api_data["description"] = ""

        if content_type is not None:
            api_data["content_type"] = content_type
        elif op == "update" and include_nulls:
            api_data["content_type"] = ""

        if permissions is not None:
            api_data["permissions"] = permissions
        elif op == "update" and include_nulls:
            api_data["permissions"] = []

        for field in ("id", "created", "modified", "url"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIRoleDefinition_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for role definition operations."""
        return {
            "create": EndpointOperation(
                path="/api/gateway/v1/role_definitions/",
                method="POST",
                fields=["name", "description", "content_type", "permissions"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/gateway/v1/role_definitions/{id}/",
                method="PATCH",
                fields=["name", "description", "content_type", "permissions"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/role_definitions/{id}/", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1
            ),
            "get": EndpointOperation(path="/api/gateway/v1/role_definitions/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path="/api/gateway/v1/role_definitions/", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleRoleDefinition":
        """Transform from API format to Ansible format."""
        from ...ansible_models.role_definition import AnsibleRoleDefinition

        ansible_data = {
            "name": api_data.get("name", ""),
            "description": api_data.get("description"),
            "content_type": api_data.get("content_type"),
            "permissions": api_data.get("permissions") or [],
            "id": api_data.get("id"),
            "created": api_data.get("created"),
            "modified": api_data.get("modified"),
            "url": api_data.get("url"),
        }
        return AnsibleRoleDefinition(**ansible_data)
