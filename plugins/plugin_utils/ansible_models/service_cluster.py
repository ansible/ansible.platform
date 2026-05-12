"""
Ansible Service Cluster dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleServiceCluster:
    """Ansible representation of a service cluster."""

    name: str
    new_name: Optional[str] = None
    service_type: Optional[str] = None
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
    state: str = "present"

    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
