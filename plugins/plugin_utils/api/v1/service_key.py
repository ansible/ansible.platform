"""
API v1 Service Key dataclass and transform mixin.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIServiceKey_v1:
    """API v1 representation of a service key."""

    name: Optional[str] = None
    is_active: Optional[bool] = None
    service_cluster: Optional[int] = None
    algorithm: Optional[str] = None
    secret: Optional[str] = None
    secret_length: Optional[int] = None
    mark_previous_inactive: Optional[bool] = None

    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class ServiceKeyTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for Service Key API v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIServiceKey_v1":
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
        for field in ("is_active", "algorithm", "secret", "secret_length", "mark_previous_inactive"):
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
                    logger.debug("Lookup service_cluster for service_key: %s", e)
            if "service_cluster" not in api_data and str(sc).isdigit():
                api_data["service_cluster"] = int(sc)
        for field in ("id", "created", "modified", "url"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
        return APIServiceKey_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/gateway/v1/service_keys/",
                method="POST",
                fields=["name", "is_active", "service_cluster", "algorithm", "secret", "secret_length", "mark_previous_inactive"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/gateway/v1/service_keys/{id}/",
                method="PATCH",
                fields=["name", "is_active", "service_cluster", "algorithm", "secret_length", "mark_previous_inactive"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/service_keys/{id}/", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1
            ),
            "get": EndpointOperation(path="/api/gateway/v1/service_keys/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path="/api/gateway/v1/service_keys/", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleServiceKey":
        from ...ansible_models.service_key import AnsibleServiceKey

        sc = api_data.get("service_cluster")
        secret = api_data.get("secret")
        if secret == "$encrypted$":
            secret = None

        return AnsibleServiceKey(
            name=api_data.get("name", ""),
            is_active=api_data.get("is_active"),
            service_cluster=str(sc) if sc is not None else None,
            algorithm=api_data.get("algorithm"),
            secret=secret,
            secret_length=api_data.get("secret_length"),
            mark_previous_inactive=api_data.get("mark_previous_inactive"),
            id=api_data.get("id"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )
