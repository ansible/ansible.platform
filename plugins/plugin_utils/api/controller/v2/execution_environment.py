"""
API v2 ExecutionEnvironment dataclass and transform mixin.

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
class APIExecutionEnvironment_v2(BaseTransformMixin):
    """API v2 representation of a Controller execution environment."""

    name: Optional[str] = None
    image: Optional[str] = None
    description: Optional[str] = None
    organization: Optional[int] = None
    credential: Optional[int] = None
    pull: Optional[str] = None

    # Read-only fields from API
    id: Optional[int] = None


class ExecutionEnvironmentTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for ExecutionEnvironment API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APIExecutionEnvironment_v2":
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

        manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")

        # FK resolution: organization (Gateway-owned, default service)
        organization = getattr(ansible_instance, "organization", None)
        if organization is not None:
            if manager is not None and not str(organization).strip().isdigit():
                api_data["organization"] = manager.lookup_resource_id("organizations", "name", organization)
            else:
                api_data["organization"] = int(organization) if organization is not None else None

        # FK resolution: credential (Controller-owned)
        credential = getattr(ansible_instance, "credential", None)
        if credential is not None:
            if manager is not None and not str(credential).strip().isdigit():
                api_data["credential"] = manager.lookup_resource_id("credentials", "name", credential, service="controller")
            else:
                api_data["credential"] = int(credential) if credential is not None else None

        for field in ("image", "description", "pull"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
            elif op == "update" and include_nulls and field == "description":
                api_data[field] = ""

        # Read-only from API (for building URL in execute)
        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIExecutionEnvironment_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/execution_environments/",
                method="POST",
                fields=["name", "image", "description", "organization", "credential", "pull"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/execution_environments/{id}/",
                method="PATCH",
                fields=["name", "image", "description", "organization", "credential", "pull"],
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

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.execution_environment import AnsibleExecutionEnvironment

        organization_val = api_data.get("organization")
        organization_str = str(organization_val) if organization_val is not None else None

        credential_val = api_data.get("credential")
        credential_str = str(credential_val) if credential_val is not None else None

        return AnsibleExecutionEnvironment(
            name=api_data.get("name", ""),
            image=api_data.get("image"),
            description=api_data.get("description"),
            organization=organization_str,
            credential=credential_str,
            pull=api_data.get("pull"),
            id=api_data.get("id"),
        )
