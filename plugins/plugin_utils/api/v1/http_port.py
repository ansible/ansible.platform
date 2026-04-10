"""
API v1 Http Port dataclass and transform mixin.

Handles transformations between Ansible format and Gateway API v1 format.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIHttpPort_v1(BaseTransformMixin):
    """
    API v1 representation of an http port.
    """

    name: Optional[str] = None
    number: Optional[int] = None
    use_https: bool = False
    is_api_port: bool = False

    # Read-only fields from API
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class HttpPortTransformMixin_v1(BaseTransformMixin):
    """
    Transform mixin for Http Port API v1.
    """

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIHttpPort_v1":
        """Create API instance from Ansible dataclass."""
        api_data = {}
        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
        number = getattr(ansible_instance, "number", None)
        use_https = getattr(ansible_instance, "use_https", False)
        is_api_port = getattr(ansible_instance, "is_api_port", False)
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
                # Regular update by name: keep it (idempotent).
                # Digit-string names are integer PK lookups — omit from PATCH
                # to avoid accidentally renaming the port to its own ID string.
                api_data["name"] = name

        if number is not None:
            api_data["number"] = number
        elif op == "update" and include_nulls:
            api_data["number"] = None

        if op in ("create", "update"):
            api_data["use_https"] = use_https
            api_data["is_api_port"] = is_api_port

        for field in ("id", "created", "modified", "url"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIHttpPort_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for http port operations."""
        return {
            "create": EndpointOperation(
                path="/api/gateway/v1/http_ports/", method="POST", fields=["name", "number", "use_https", "is_api_port"], required_for="create", order=1
            ),
            "update": EndpointOperation(
                path="/api/gateway/v1/http_ports/{id}/",
                method="PATCH",
                fields=["name", "number", "use_https", "is_api_port"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/http_ports/{id}/", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1
            ),
            "get": EndpointOperation(path="/api/gateway/v1/http_ports/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path="/api/gateway/v1/http_ports/", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleHttpPort":
        """Transform from API format to Ansible format."""
        from ...ansible_models.http_port import AnsibleHttpPort

        ansible_data = {
            "name": api_data.get("name", ""),
            "number": api_data.get("number"),
            "use_https": api_data.get("use_https", False),
            "is_api_port": api_data.get("is_api_port", False),
            "id": api_data.get("id"),
            "created": api_data.get("created"),
            "modified": api_data.get("modified"),
            "url": api_data.get("url"),
        }
        return AnsibleHttpPort(**ansible_data)


# Alias so loader finds mixin when module_name is "http_port" (title() -> "Http_Port").
