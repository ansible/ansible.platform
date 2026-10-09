"""
API v2 Instance dataclass and transform mixin.

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
class APIInstance_v2(BaseTransformMixin):
    """API v2 representation of a Controller instance."""

    hostname: Optional[str] = None
    capacity_adjustment: Optional[float] = None
    enabled: Optional[bool] = None
    managed_by_policy: Optional[bool] = None
    node_type: Optional[str] = None
    node_state: Optional[str] = None
    listener_port: Optional[int] = None
    peers_from_control_nodes: Optional[bool] = None

    # Read-only fields from API
    id: Optional[int] = None


class InstanceTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for Instance API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APIInstance_v2":
        api_data: Dict[str, Any] = {}

        hostname = getattr(ansible_instance, "hostname", None)
        op = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")

        if op == "create":
            api_data["hostname"] = hostname
        elif op == "update":
            if hostname is not None and not str(hostname).strip().isdigit():
                api_data["hostname"] = hostname

        for field in ("capacity_adjustment", "enabled", "managed_by_policy", "node_type", "node_state", "listener_port", "peers_from_control_nodes"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        # Read-only from API (for building URL in execute)
        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIInstance_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/instances/",
                method="POST",
                fields=[
                    "hostname",
                    "capacity_adjustment",
                    "enabled",
                    "managed_by_policy",
                    "node_type",
                    "node_state",
                    "listener_port",
                    "peers_from_control_nodes",
                ],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/instances/{id}/",
                method="PATCH",
                fields=[
                    "hostname",
                    "capacity_adjustment",
                    "enabled",
                    "managed_by_policy",
                    "node_type",
                    "node_state",
                    "listener_port",
                    "peers_from_control_nodes",
                ],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/instances/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/instances/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "hostname"

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.instance import AnsibleInstance

        # capacity_adjustment: API returns string "0.90", normalize to float for idempotency
        cap_adj = api_data.get("capacity_adjustment")
        if cap_adj is not None:
            try:
                cap_adj = float(cap_adj)
            except (ValueError, TypeError):
                pass

        return AnsibleInstance(
            hostname=api_data.get("hostname", ""),
            capacity_adjustment=cap_adj,
            enabled=api_data.get("enabled"),
            managed_by_policy=api_data.get("managed_by_policy"),
            node_type=api_data.get("node_type"),
            node_state=api_data.get("node_state"),
            listener_port=api_data.get("listener_port"),
            peers_from_control_nodes=api_data.get("peers_from_control_nodes"),
            id=api_data.get("id"),
        )
