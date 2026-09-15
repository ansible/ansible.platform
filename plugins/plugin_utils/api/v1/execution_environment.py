"""
API v1 ExecutionEnvironment dataclass and transform mixin.

Handles transformations between Ansible format and the Controller API format
for execution_environment resources.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...ansible_models.execution_environment import AnsibleExecutionEnvironment
from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIExecutionEnvironment_v1:
    """Wire format for Controller execution_environments."""

    name: str
    image: Optional[str] = None
    description: Optional[str] = None
    organization: Optional[int] = None
    credential: Optional[int] = None
    pull: Optional[str] = None
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class ExecutionEnvironmentTransformMixin_v1(BaseTransformMixin):
    """Transforms between AnsibleExecutionEnvironment and APIExecutionEnvironment_v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance: AnsibleExecutionEnvironment, context: TransformContext) -> APIExecutionEnvironment_v1:
        """Forward: Ansible model -> API wire format."""
        params: Dict[str, Any] = {
            "name": ansible_instance.new_name or ansible_instance.name,
        }

        if ansible_instance.organization is not None:
            params["organization"] = context.manager.lookup_resource_id("/api/controller/v2/organizations/", "name", ansible_instance.organization)

        if ansible_instance.credential is not None:
            params["credential"] = context.manager.lookup_resource_id("/api/controller/v2/credentials/", "name", ansible_instance.credential)

        for field in ("image", "description", "pull"):
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = value

        # Read-only from API (for building the {id} URL path param in execute)
        for field in ("id", "created", "modified", "url"):
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = value

        return APIExecutionEnvironment_v1(**params)

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: TransformContext) -> AnsibleExecutionEnvironment:
        """Reverse: API response -> Ansible model."""
        org = api_data.get("organization")
        credential = api_data.get("credential")

        return AnsibleExecutionEnvironment(
            id=api_data.get("id"),
            name=api_data.get("name", ""),
            image=api_data.get("image"),
            description=api_data.get("description"),
            organization=str(org) if org is not None else None,
            credential=str(credential) if credential is not None else None,
            pull=api_data.get("pull"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = ["name", "image", "description", "organization", "credential", "pull"]

        return {
            "create": EndpointOperation(
                path="/api/controller/v2/execution_environments/",
                method="POST",
                fields=fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/execution_environments/{id}/",
                method="PATCH",
                fields=fields,
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/execution_environments/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/execution_environments/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/execution_environments/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"
