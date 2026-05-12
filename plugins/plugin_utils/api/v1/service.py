"""
API v1 Service dataclass and transform mixin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

_API_PREFIX = "/api/"


@dataclass
class APIService_v1(BaseTransformMixin):
    """API v1 representation of a gateway service."""

    name: Optional[str] = None

    description: Optional[str] = None
    api_slug: Optional[str] = None
    gateway_path: Optional[str] = None
    http_port: Optional[int] = None
    service_cluster: Optional[int] = None
    is_service_https: Optional[bool] = None
    is_internal_route: Optional[bool] = None
    enable_gateway_auth: Optional[bool] = None
    enable_mtls: Optional[bool] = None
    service_path: Optional[str] = None
    service_port: Optional[int] = None
    node_tags: Optional[str] = None
    order: Optional[int] = None
    idle_timeout_seconds: Optional[int] = None
    request_timeout_seconds: Optional[int] = None

    # Read-only
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


def _resolve_fk(manager, endpoint: str, lookup_field: str, value) -> Optional[int]:
    """Resolve a name or id to an integer id."""
    if value is None:
        return None
    if str(value).isdigit():
        return int(value)
    try:
        return manager.lookup_resource_id(endpoint, lookup_field, str(value))
    except Exception:
        return None


def _compute_gateway_path(api_slug: Optional[str]) -> Optional[str]:
    """Derive the gateway_path from api_slug, matching server-side logic."""
    if api_slug is None:
        return None
    if api_slug == "gateway":
        return "/"
    return _API_PREFIX + api_slug + "/"


class ServiceTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for Service API v1."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIService_v1:
        api_data: Dict[str, Any] = {}
        manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
        op = context.operation if isinstance(context, TransformContext) else context.get("operation")

        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
        if op in ("update", "enforced"):
            if new_name is not None:
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                api_data["name"] = str(name)
        elif name is not None:
            api_data["name"] = str(name)

        for field in (
            "description",
            "is_service_https",
            "is_internal_route",
            "enable_gateway_auth",
            "enable_mtls",
            "service_path",
            "service_port",
            "node_tags",
            "order",
            "idle_timeout_seconds",
            "request_timeout_seconds",
        ):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        # api_slug also determines gateway_path (computed server-side on create)
        api_slug = getattr(ansible_instance, "api_slug", None)
        if api_slug is not None:
            api_data["api_slug"] = api_slug
            # Only derive gateway_path for create; on update the server manages it
            if op == "create":
                gp = _compute_gateway_path(api_slug)
                if gp is not None:
                    api_data["gateway_path"] = gp

        # Resolve FK: http_port name -> id
        http_port = getattr(ansible_instance, "http_port", None)
        if http_port is not None and manager:
            resolved = _resolve_fk(manager, "http_ports", "name", http_port)
            if resolved is not None:
                api_data["http_port"] = resolved

        # Resolve FK: service_cluster name -> id
        service_cluster = getattr(ansible_instance, "service_cluster", None)
        if service_cluster is not None and manager:
            resolved = _resolve_fk(manager, "service_clusters", "name", service_cluster)
            if resolved is not None:
                api_data["service_cluster"] = resolved

        for ro in ("id", "created", "modified", "url"):
            val = getattr(ansible_instance, ro, None)
            if val is not None:
                api_data[ro] = val

        return APIService_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = [
            "name",
            "description",
            "api_slug",
            "gateway_path",
            "http_port",
            "service_cluster",
            "is_service_https",
            "is_internal_route",
            "enable_gateway_auth",
            "enable_mtls",
            "service_path",
            "service_port",
            "node_tags",
            "order",
            "idle_timeout_seconds",
            "request_timeout_seconds",
        ]
        return {
            "create": EndpointOperation(
                path="/api/gateway/v1/services/",
                method="POST",
                fields=fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/gateway/v1/services/{id}/",
                method="PATCH",
                fields=fields,
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/services/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/gateway/v1/services/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/gateway/v1/services/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    #: After a list-based find returns a match, perform a follow-up GET-by-ID
    #: to retrieve the full resource state.  The services list endpoint omits or
    #: null-out certain fields (e.g. idle_timeout_seconds, request_timeout_seconds)
    #: that the individual GET endpoint returns correctly.  Setting this to True
    #: ensures idempotency comparisons use complete resource data.
    full_resource_lookup: bool = True

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ...ansible_models.service import AnsibleService

        return AnsibleService(
            name=api_data.get("name", ""),
            description=api_data.get("description"),
            api_slug=api_data.get("api_slug"),
            gateway_path=api_data.get("gateway_path"),
            http_port=api_data.get("http_port"),
            service_cluster=api_data.get("service_cluster"),
            is_service_https=api_data.get("is_service_https"),
            is_internal_route=api_data.get("is_internal_route"),
            enable_gateway_auth=api_data.get("enable_gateway_auth"),
            enable_mtls=api_data.get("enable_mtls"),
            service_path=api_data.get("service_path"),
            service_port=api_data.get("service_port"),
            node_tags=api_data.get("node_tags"),
            order=api_data.get("order"),
            idle_timeout_seconds=api_data.get("idle_timeout_seconds"),
            request_timeout_seconds=api_data.get("request_timeout_seconds"),
            id=api_data.get("id"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )
