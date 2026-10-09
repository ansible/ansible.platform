"""
API v2 Group dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIGroup_v2(BaseTransformMixin):
    """API v2 representation of a Controller inventory group."""

    name: Optional[str] = None
    description: Optional[str] = None
    inventory: Optional[int] = None
    variables: Optional[str] = None

    # Read-only fields from API
    id: Optional[int] = None


class GroupTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for Group API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APIGroup_v2":
        api_data: Dict[str, Any] = {}

        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
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

        # FK resolution: inventory name → ID
        inventory = getattr(ansible_instance, "inventory", None)
        if inventory is not None:
            manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
            if manager is not None and not str(inventory).strip().isdigit():
                api_data["inventory"] = manager.lookup_resource_id("inventories", "name", inventory, service="controller")
            else:
                api_data["inventory"] = int(inventory) if inventory is not None else None

        for field in ("description",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
            elif op == "update" and include_nulls:
                api_data[field] = ""

        # variables: already normalized to JSON string by __post_init__
        variables = getattr(ansible_instance, "variables", None)
        if variables is not None:
            api_data["variables"] = json.dumps(variables) if isinstance(variables, dict) else variables

        # Read-only from API (for building URL in execute)
        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIGroup_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/groups/",
                method="POST",
                fields=["name", "description", "inventory", "variables"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/groups/{id}/",
                method="PATCH",
                fields=["name", "description", "inventory", "variables"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/groups/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/groups/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/groups/",
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
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.group import AnsibleGroup

        inventory_val = api_data.get("inventory")
        inventory_str = str(inventory_val) if inventory_val is not None else ""

        return AnsibleGroup(
            name=api_data.get("name", ""),
            inventory=inventory_str,
            description=api_data.get("description"),
            variables=api_data.get("variables"),
            id=api_data.get("id"),
        )
