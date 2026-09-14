"""
API v1 Host dataclass and transform mixin.

Handles transformations between Ansible format and the Controller API format
for host resources.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...ansible_models.host import AnsibleHost
from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIHost_v1:
    """Wire format for Controller hosts."""

    name: str
    inventory: Optional[int] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    instance_id: Optional[str] = None
    variables: Optional[str] = None
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class HostTransformMixin_v1(BaseTransformMixin):
    """Transforms between AnsibleHost and APIHost_v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance: AnsibleHost, context: TransformContext) -> APIHost_v1:
        """Forward: Ansible model -> API wire format."""
        params: Dict[str, Any] = {
            "name": ansible_instance.new_name or ansible_instance.name,
        }

        if ansible_instance.inventory is not None:
            params["inventory"] = context.manager.lookup_resource_id("/api/controller/v2/inventories/", "name", ansible_instance.inventory)

        for field in ("description", "enabled", "instance_id"):
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = value

        # Convert variables dict to JSON string for the API
        if ansible_instance.variables is not None:
            if isinstance(ansible_instance.variables, dict):
                params["variables"] = json.dumps(ansible_instance.variables)
            else:
                params["variables"] = str(ansible_instance.variables)

        # Read-only from API (for building the {id} URL path param in execute)
        for field in ("id", "created", "modified", "url"):
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = value

        return APIHost_v1(**params)

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: TransformContext) -> AnsibleHost:
        """Reverse: API response -> Ansible model."""
        raw_vars = api_data.get("variables")
        variables: Optional[dict] = None
        if isinstance(raw_vars, dict):
            variables = raw_vars
        elif isinstance(raw_vars, str) and raw_vars.strip():
            try:
                variables = json.loads(raw_vars)
            except ValueError:
                variables = None

        inventory = api_data.get("inventory")

        return AnsibleHost(
            id=api_data.get("id"),
            name=api_data.get("name", ""),
            inventory=str(inventory) if inventory is not None else "",
            description=api_data.get("description"),
            enabled=api_data.get("enabled"),
            instance_id=api_data.get("instance_id"),
            variables=variables,
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = [
            "name",
            "description",
            "inventory",
            "enabled",
            "instance_id",
            "variables",
        ]

        return {
            "create": EndpointOperation(
                path="/api/controller/v2/hosts/",
                method="POST",
                fields=fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/hosts/{id}/",
                method="PATCH",
                fields=fields,
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/hosts/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/hosts/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/hosts/",
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
    def get_find_list_query_params(cls, ansible_data: APIHost_v1) -> Dict[str, Any]:
        """Scope name lookups by inventory — host names are only unique per-inventory."""
        inventory_id = getattr(ansible_data, "inventory", None)
        if inventory_id is not None:
            return {"inventory": inventory_id}
        return {}
