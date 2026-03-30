"""
API v1 Service Cluster dataclass and transform mixin.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

_SCALAR_FIELDS = (
    "name",
    "service_type",
    "auth_type",
    "upstream_hostname",
    "dns_discovery_type",
    "dns_lookup_family",
    "outlier_detection_enabled",
    "outlier_detection_consecutive_5xx",
    "outlier_detection_interval_seconds",
    "outlier_detection_base_ejection_time_seconds",
    "outlier_detection_max_ejection_percent",
    "health_checks_enabled",
    "health_check_timeout_seconds",
    "health_check_interval_seconds",
    "health_check_unhealthy_threshold",
    "health_check_healthy_threshold",
    "healthy_panic_threshold",
)


@dataclass
class APIServiceCluster_v1(BaseTransformMixin):
    """API v1 representation of a service cluster."""

    name: Optional[str] = None
    service_type: Optional[int] = None
    auth_type: Optional[str] = None
    upstream_hostname: Optional[str] = None
    dns_discovery_type: Optional[str] = None
    dns_lookup_family: Optional[str] = None
    outlier_detection_enabled: Optional[bool] = None
    outlier_detection_consecutive_5xx: Optional[int] = None
    outlier_detection_interval_seconds: Optional[int] = None
    outlier_detection_base_ejection_time_seconds: Optional[int] = None
    outlier_detection_max_ejection_percent: Optional[int] = None
    health_checks_enabled: Optional[bool] = None
    health_check_timeout_seconds: Optional[int] = None
    health_check_interval_seconds: Optional[int] = None
    health_check_unhealthy_threshold: Optional[int] = None
    health_check_healthy_threshold: Optional[int] = None
    healthy_panic_threshold: Optional[int] = None

    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class ServiceClusterTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for Service Cluster API v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIServiceCluster_v1":
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
        st = getattr(ansible_instance, "service_type", None)
        if st is not None:
            manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
            if manager:
                try:
                    api_data["service_type"] = manager.lookup_resource_id("service_types", "name", str(st))
                except Exception as e:
                    logger.debug("Lookup service_type for service_cluster: %s", e)
            if "service_type" not in api_data and str(st).isdigit():
                api_data["service_type"] = int(st)
        for field in _SCALAR_FIELDS:
            if field in ("name", "service_type"):
                continue
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
        for field in ("id", "created", "modified", "url"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
        return APIServiceCluster_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = [
            "name",
            "service_type",
            "auth_type",
            "upstream_hostname",
            "dns_discovery_type",
            "dns_lookup_family",
            "outlier_detection_enabled",
            "outlier_detection_consecutive_5xx",
            "outlier_detection_interval_seconds",
            "outlier_detection_base_ejection_time_seconds",
            "outlier_detection_max_ejection_percent",
            "health_checks_enabled",
            "health_check_timeout_seconds",
            "health_check_interval_seconds",
            "health_check_unhealthy_threshold",
            "health_check_healthy_threshold",
            "healthy_panic_threshold",
        ]
        return {
            "create": EndpointOperation(path="/api/gateway/v1/service_clusters/", method="POST", fields=fields, required_for="create", order=1),
            "update": EndpointOperation(
                path="/api/gateway/v1/service_clusters/{id}/", method="PATCH", fields=fields, path_params=["id"], required_for="update", order=1
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/service_clusters/{id}/", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1
            ),
            "get": EndpointOperation(path="/api/gateway/v1/service_clusters/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path="/api/gateway/v1/service_clusters/", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleServiceCluster":
        from ...ansible_models.service_cluster import AnsibleServiceCluster

        st = api_data.get("service_type")
        return AnsibleServiceCluster(
            name=api_data.get("name", ""),
            service_type=str(st) if st is not None else None,
            auth_type=api_data.get("auth_type"),
            upstream_hostname=api_data.get("upstream_hostname"),
            dns_discovery_type=api_data.get("dns_discovery_type"),
            dns_lookup_family=api_data.get("dns_lookup_family"),
            outlier_detection_enabled=api_data.get("outlier_detection_enabled"),
            outlier_detection_consecutive_5xx=api_data.get("outlier_detection_consecutive_5xx"),
            outlier_detection_interval_seconds=api_data.get("outlier_detection_interval_seconds"),
            outlier_detection_base_ejection_time_seconds=api_data.get("outlier_detection_base_ejection_time_seconds"),
            outlier_detection_max_ejection_percent=api_data.get("outlier_detection_max_ejection_percent"),
            health_checks_enabled=api_data.get("health_checks_enabled"),
            health_check_timeout_seconds=api_data.get("health_check_timeout_seconds"),
            health_check_interval_seconds=api_data.get("health_check_interval_seconds"),
            health_check_unhealthy_threshold=api_data.get("health_check_unhealthy_threshold"),
            health_check_healthy_threshold=api_data.get("health_check_healthy_threshold"),
            healthy_panic_threshold=api_data.get("healthy_panic_threshold"),
            id=api_data.get("id"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )
