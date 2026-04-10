"""
API v1 UIPluginRoute dataclass and transform mixin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext


@dataclass
class APIUIPluginRoute_v1(BaseTransformMixin):
    """API v1 representation of a gateway UI plugin route."""

    name: Optional[str] = None

    description: Optional[str] = None
    ui_plugin_path: Optional[str] = None
    http_port: Optional[int] = None
    service_cluster: Optional[int] = None
    is_service_https: Optional[bool] = None
    service_port: Optional[int] = None
    node_tags: Optional[str] = None
    order: Optional[int] = None
    idle_timeout_seconds: Optional[int] = None
    request_timeout_seconds: Optional[int] = None

    # Read-only / auto-generated
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
    gateway_path: Optional[str] = None
    service_path: Optional[str] = None
    enable_gateway_auth: Optional[bool] = None
    is_internal_route: Optional[bool] = None


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


class UIPluginRouteTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for UIPluginRoute API v1."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIUIPluginRoute_v1:
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
            "ui_plugin_path",
            "is_service_https",
            "service_port",
            "node_tags",
            "order",
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

        for ro in ("id", "created", "modified", "url"):
            val = getattr(ansible_instance, ro, None)
            if val is not None:
                api_data[ro] = val

        return APIUIPluginRoute_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = [
            "name",
            "description",
            "ui_plugin_path",
            "http_port",
            "service_cluster",
            "is_service_https",
            "service_port",
            "node_tags",
            "order",
            "idle_timeout_seconds",
            "request_timeout_seconds",
        ]
        return {
            "create": EndpointOperation(
                path="/api/gateway/v1/ui_plugin_routes/",
                method="POST",
                fields=fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/gateway/v1/ui_plugin_routes/{id}/",
                method="PATCH",
                fields=fields,
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/ui_plugin_routes/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/gateway/v1/ui_plugin_routes/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/gateway/v1/ui_plugin_routes/",
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
        from ...ansible_models.ui_plugin_route import AnsibleUIPluginRoute

        return AnsibleUIPluginRoute(
            name=api_data.get("name", ""),
            description=api_data.get("description"),
            ui_plugin_path=api_data.get("ui_plugin_path"),
            http_port=api_data.get("http_port"),
            service_cluster=api_data.get("service_cluster"),
            is_service_https=api_data.get("is_service_https"),
            service_port=api_data.get("service_port"),
            node_tags=api_data.get("node_tags"),
            order=api_data.get("order"),
            idle_timeout_seconds=api_data.get("idle_timeout_seconds"),
            request_timeout_seconds=api_data.get("request_timeout_seconds"),
            gateway_path=api_data.get("gateway_path"),
            service_path=api_data.get("service_path"),
            enable_gateway_auth=api_data.get("enable_gateway_auth"),
            is_internal_route=api_data.get("is_internal_route"),
            id=api_data.get("id"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )
