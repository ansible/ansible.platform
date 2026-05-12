"""
API v1 Service Node dataclass and transform mixin.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIServiceNode_v1(BaseTransformMixin):
    """API v1 representation of a service node."""

    name: Optional[str] = None
    address: Optional[str] = None
    service_cluster: Optional[int] = None
    tags: Optional[str] = None

    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class ServiceNodeTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for Service Node API v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIServiceNode_v1":
        api_data = {}
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
        for field in ("address", "tags"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
        sc = getattr(ansible_instance, "service_cluster", None)
        if sc is not None:
            manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
            if manager:
                try:
                    api_data["service_cluster"] = manager.lookup_resource_id("service_clusters", "name", str(sc))
                except Exception as e:
                    logger.debug("Lookup service_cluster for service_node: %s", e)
            if "service_cluster" not in api_data and str(sc).isdigit():
                api_data["service_cluster"] = int(sc)
        for field in ("id", "created", "modified", "url"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
        return APIServiceNode_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/gateway/v1/service_nodes/", method="POST", fields=["name", "address", "service_cluster", "tags"], required_for="create", order=1
            ),
            "update": EndpointOperation(
                path="/api/gateway/v1/service_nodes/{id}/",
                method="PATCH",
                fields=["name", "address", "service_cluster", "tags"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/service_nodes/{id}/", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1
            ),
            "get": EndpointOperation(path="/api/gateway/v1/service_nodes/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path="/api/gateway/v1/service_nodes/", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleServiceNode":
        from ...ansible_models.service_node import AnsibleServiceNode

        sc = api_data.get("service_cluster")
        return AnsibleServiceNode(
            name=api_data.get("name", ""),
            address=api_data.get("address"),
            service_cluster=str(sc) if sc is not None else None,
            tags=api_data.get("tags"),
            id=api_data.get("id"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )
