"""API v1 EDA Controller Token dataclass and transform mixin."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIEdaControllerToken_v1(BaseTransformMixin):
    """API v1 representation of an EDA controller (AWX) token."""

    name: Optional[str] = None
    description: Optional[str] = None
    token: Optional[str] = None

    # Read-only fields from API
    id: Optional[int] = None


class EdaControllerTokenTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for EDA Controller Token API v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIEdaControllerToken_v1":
        """Create API instance from Ansible dataclass."""
        api_data = {}

        name = getattr(ansible_instance, "name", None)
        description = getattr(ansible_instance, "description", None)
        token = getattr(ansible_instance, "token", None)

        if name is not None:
            api_data["name"] = name
        if description is not None:
            api_data["description"] = description
        if token is not None:
            api_data["token"] = token

        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIEdaControllerToken_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for EDA controller token operations."""
        return {
            "create": EndpointOperation(
                path="/api/eda/v1/users/me/awx-tokens/",
                method="POST",
                fields=["name", "description", "token"],
                required_for="create",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/eda/v1/users/me/awx-tokens/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/eda/v1/users/me/awx-tokens/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/eda/v1/users/me/awx-tokens/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleEdaControllerToken":
        """Transform from API format to Ansible format."""
        from ....ansible_models.eda_controller_token import AnsibleEdaControllerToken

        ansible_data = {
            "name": api_data.get("name", ""),
            "description": api_data.get("description"),
            "id": api_data.get("id"),
        }
        return AnsibleEdaControllerToken(**ansible_data)
