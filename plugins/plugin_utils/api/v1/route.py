"""
API v1 Route dataclass and transform mixin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext


@dataclass
class APIRoute_v1(BaseTransformMixin):
    """API v1 representation of a gateway route."""

    name: Optional[str] = None

    description: Optional[str] = None
    gateway_path: Optional[str] = None
    http_port: Optional[int] = None
    service_cluster: Optional[int] = None
    is_service_https: Optional[bool] = None
    enable_gateway_auth: Optional[bool] = None
    enable_mtls: Optional[bool] = None
    is_internal_route: Optional[bool] = None
    service_path: Optional[str] = None
    service_port: Optional[int] = None
    node_tags: Optional[str] = None
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


class RouteTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for Route API v1."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIRoute_v1:
        api_data: Dict[str, Any] = {}
        manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
        op = context.operation if isinstance(context, TransformContext) else context.get("operation")

        # Client-side validation: mTLS requires gateway auth to be disabled
        enable_gateway_auth = getattr(ansible_instance, "enable_gateway_auth", None)
        enable_mtls = getattr(ansible_instance, "enable_mtls", None)
        if op in ("create", "update", "enforced") and enable_gateway_auth and enable_mtls:
            raise ValueError("Mutual TLS can only be enabled when gateway auth is disabled")

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
            "gateway_path",
            "is_service_https",
            "enable_gateway_auth",
            "enable_mtls",
            "is_internal_route",
            "service_path",
            "service_port",
            "node_tags",
            "idle_timeout_seconds",
            "request_timeout_seconds",
        ):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

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

        # Read-only fields for URL construction
        for ro in ("id", "created", "modified", "url"):
            val = getattr(ansible_instance, ro, None)
            if val is not None:
                api_data[ro] = val

        return APIRoute_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = [
            "name",
            "description",
            "gateway_path",
            "http_port",
            "service_cluster",
            "is_service_https",
            "enable_gateway_auth",
            "enable_mtls",
            "is_internal_route",
            "service_path",
            "service_port",
            "node_tags",
            "idle_timeout_seconds",
            "request_timeout_seconds",
        ]
        return {
            "create": EndpointOperation(
                path="/api/gateway/v1/routes/",
                method="POST",
                fields=fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/gateway/v1/routes/{id}/",
                method="PATCH",
                fields=fields,
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/routes/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/gateway/v1/routes/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/gateway/v1/routes/",
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
    #: to retrieve the full resource state.  Some API list endpoints omit or
    #: null-out certain fields (e.g. idle_timeout_seconds, request_timeout_seconds
    #: on routes) that the individual GET endpoint returns correctly.  Setting
    #: this to True ensures idempotency comparisons use complete resource data.
    full_resource_lookup: bool = True

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ...ansible_models.route import AnsibleRoute

        return AnsibleRoute(
            name=api_data.get("name", ""),
            description=api_data.get("description"),
            gateway_path=api_data.get("gateway_path"),
            http_port=api_data.get("http_port"),
            service_cluster=api_data.get("service_cluster"),
            is_service_https=api_data.get("is_service_https"),
            enable_gateway_auth=api_data.get("enable_gateway_auth"),
            enable_mtls=api_data.get("enable_mtls"),
            is_internal_route=api_data.get("is_internal_route"),
            service_path=api_data.get("service_path"),
            service_port=api_data.get("service_port"),
            node_tags=api_data.get("node_tags"),
            idle_timeout_seconds=api_data.get("idle_timeout_seconds"),
            request_timeout_seconds=api_data.get("request_timeout_seconds"),
            id=api_data.get("id"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )
