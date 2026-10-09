"""
API v2 Label dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APILabel_v2(BaseTransformMixin):
    """API v2 representation of a Controller label."""

    name: Optional[str] = None
    organization: Optional[int] = None

    # Read-only fields from API
    id: Optional[int] = None


class LabelTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for Label API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APILabel_v2":
        api_data: Dict[str, Any] = {}

        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
        op = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")

        if op == "create":
            api_data["name"] = name or new_name
        elif op == "update":
            if new_name is not None:
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                api_data["name"] = name

        # FK resolution: organization name → ID (Gateway-owned, use default service)
        organization = getattr(ansible_instance, "organization", None)
        if organization is not None:
            manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
            if manager is not None and not str(organization).strip().isdigit():
                api_data["organization"] = manager.lookup_resource_id("organizations", "name", organization)
            else:
                api_data["organization"] = int(organization) if organization is not None else None

        # Read-only from API (for building URL in execute)
        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APILabel_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/labels/",
                method="POST",
                fields=["name", "organization"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/labels/{id}/",
                method="PATCH",
                fields=["name", "organization"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/labels/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/labels/",
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
        from ....ansible_models.label import AnsibleLabel

        organization_val = api_data.get("organization")
        organization_str = str(organization_val) if organization_val is not None else ""

        return AnsibleLabel(
            name=api_data.get("name", ""),
            organization=organization_str,
            id=api_data.get("id"),
        )
