"""
API v1 Service Type dataclass and transform mixin.

Handles transformations between Ansible format and Gateway API v1 format.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIServiceType_v1(BaseTransformMixin):
    """
    API v1 representation of a service type.
    """

    name: Optional[str] = None
    ping_url: Optional[str] = None
    login_path: Optional[str] = None
    logout_path: Optional[str] = None
    service_index_path: Optional[str] = None

    # Read-only fields from API
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class ServiceTypeTransformMixin_v1(BaseTransformMixin):
    """
    Transform mixin for Service Type API v1.
    """

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIServiceType_v1":
        """Create API instance from Ansible dataclass."""
        api_data = {}
        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
        _ping_url = getattr(ansible_instance, "ping_url", None)
        _login_path = getattr(ansible_instance, "login_path", None)
        _logout_path = getattr(ansible_instance, "logout_path", None)
        _service_index_path = getattr(ansible_instance, "service_index_path", None)
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

        for field in ("ping_url", "login_path", "logout_path", "service_index_path"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
            elif op == "update" and include_nulls:
                api_data[field] = ""

        for field in ("id", "created", "modified", "url"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIServiceType_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for service type operations."""
        return {
            "create": EndpointOperation(
                path="/api/gateway/v1/service_types/",
                method="POST",
                fields=["name", "ping_url", "login_path", "logout_path", "service_index_path"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/gateway/v1/service_types/{id}/",
                method="PATCH",
                fields=["name", "ping_url", "login_path", "logout_path", "service_index_path"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/service_types/{id}/", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1
            ),
            "get": EndpointOperation(path="/api/gateway/v1/service_types/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path="/api/gateway/v1/service_types/", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleServiceType":
        """Transform from API format to Ansible format."""
        from ...ansible_models.service_type import AnsibleServiceType

        ansible_data = {
            "name": api_data.get("name", ""),
            "ping_url": api_data.get("ping_url"),
            "login_path": api_data.get("login_path"),
            "logout_path": api_data.get("logout_path"),
            "service_index_path": api_data.get("service_index_path"),
            "id": api_data.get("id"),
            "created": api_data.get("created"),
            "modified": api_data.get("modified"),
            "url": api_data.get("url"),
        }
        return AnsibleServiceType(**ansible_data)
