"""
API v1 Inventory dataclass and transform mixin.

Handles transformations between Ansible format and the Controller API format
for inventory resources.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...ansible_models.inventory import AnsibleInventory
from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIInventory_v1:
    """Wire format for Controller inventories."""

    name: str
    organization: Optional[int] = None
    description: Optional[str] = None
    kind: Optional[str] = None
    host_filter: Optional[str] = None
    variables: Optional[str] = None
    prevent_instance_group_fallback: Optional[bool] = None
    opa_query_path: Optional[str] = None
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class InventoryTransformMixin_v1(BaseTransformMixin):
    """Transforms between AnsibleInventory and APIInventory_v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance: AnsibleInventory, context: TransformContext) -> APIInventory_v1:
        """Forward: Ansible model -> API wire format."""
        params: Dict[str, Any] = {
            "name": ansible_instance.new_name or ansible_instance.name,
        }

        if ansible_instance.organization is not None:
            params["organization"] = context.manager.lookup_resource_id("/api/controller/v2/organizations/", "name", ansible_instance.organization)

        for field in ("description", "kind", "host_filter", "prevent_instance_group_fallback", "opa_query_path"):
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

        return APIInventory_v1(**params)

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: TransformContext) -> AnsibleInventory:
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

        org = api_data.get("organization")

        return AnsibleInventory(
            id=api_data.get("id"),
            name=api_data.get("name", ""),
            organization=str(org) if org is not None else "",
            description=api_data.get("description"),
            kind=api_data.get("kind"),
            host_filter=api_data.get("host_filter"),
            variables=variables,
            prevent_instance_group_fallback=api_data.get("prevent_instance_group_fallback"),
            opa_query_path=api_data.get("opa_query_path"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = [
            "name",
            "description",
            "organization",
            "kind",
            "host_filter",
            "variables",
            "prevent_instance_group_fallback",
            "opa_query_path",
        ]

        return {
            "create": EndpointOperation(
                path="/api/controller/v2/inventories/",
                method="POST",
                fields=fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/inventories/{id}/",
                method="PATCH",
                fields=fields,
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/inventories/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/inventories/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/inventories/",
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
    def get_find_list_query_params(cls, ansible_data: APIInventory_v1) -> Dict[str, Any]:
        """Scope name lookups by organization — inventory names are only unique per-org."""
        org_id = getattr(ansible_data, "organization", None)
        if org_id is not None:
            return {"organization": org_id}
        return {}
