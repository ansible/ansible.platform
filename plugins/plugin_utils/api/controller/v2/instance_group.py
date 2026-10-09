"""
API v2 InstanceGroup dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIInstanceGroup_v2(BaseTransformMixin):
    """API v2 representation of a Controller instance group."""

    name: Optional[str] = None
    credential: Optional[int] = None
    is_container_group: Optional[bool] = None
    policy_instance_percentage: Optional[int] = None
    policy_instance_minimum: Optional[int] = None
    max_concurrent_jobs: Optional[int] = None
    max_forks: Optional[int] = None
    policy_instance_list: Optional[List[Any]] = None
    pod_spec_override: Optional[str] = None

    # Read-only fields from API
    id: Optional[int] = None


class InstanceGroupTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for InstanceGroup API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APIInstanceGroup_v2":
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

        # FK resolution: credential name → ID (Controller-owned)
        credential = getattr(ansible_instance, "credential", None)
        if credential is not None:
            manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
            if manager is not None and not str(credential).strip().isdigit():
                api_data["credential"] = manager.lookup_resource_id("credentials", "name", credential, service="controller")
            else:
                api_data["credential"] = int(credential) if credential is not None else None

        for field in (
            "is_container_group",
            "policy_instance_percentage",
            "policy_instance_minimum",
            "max_concurrent_jobs",
            "max_forks",
            "policy_instance_list",
            "pod_spec_override",
        ):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        # Read-only from API (for building URL in execute)
        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIInstanceGroup_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/instance_groups/",
                method="POST",
                fields=[
                    "name",
                    "credential",
                    "is_container_group",
                    "policy_instance_percentage",
                    "policy_instance_minimum",
                    "max_concurrent_jobs",
                    "max_forks",
                    "policy_instance_list",
                    "pod_spec_override",
                ],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/instance_groups/{id}/",
                method="PATCH",
                fields=[
                    "name",
                    "credential",
                    "is_container_group",
                    "policy_instance_percentage",
                    "policy_instance_minimum",
                    "max_concurrent_jobs",
                    "max_forks",
                    "policy_instance_list",
                    "pod_spec_override",
                ],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/instance_groups/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/instance_groups/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/instance_groups/",
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
        from ....ansible_models.instance_group import AnsibleInstanceGroup

        credential_val = api_data.get("credential")
        credential_str = str(credential_val) if credential_val is not None else None

        return AnsibleInstanceGroup(
            name=api_data.get("name", ""),
            credential=credential_str,
            is_container_group=api_data.get("is_container_group"),
            policy_instance_percentage=api_data.get("policy_instance_percentage"),
            policy_instance_minimum=api_data.get("policy_instance_minimum"),
            max_concurrent_jobs=api_data.get("max_concurrent_jobs"),
            max_forks=api_data.get("max_forks"),
            policy_instance_list=api_data.get("policy_instance_list"),
            pod_spec_override=api_data.get("pod_spec_override"),
            id=api_data.get("id"),
        )
