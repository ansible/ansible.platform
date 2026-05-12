"""
Ansible Route dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class AnsibleRoute:
    """Ansible representation of a gateway custom (non-api) route."""

    # Required
    name: Union[str, int]

    # Optional / update fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    gateway_path: Optional[str] = None
    http_port: Optional[Union[str, int]] = None
    service_cluster: Optional[Union[str, int]] = None
    is_service_https: Optional[bool] = False
    enable_gateway_auth: Optional[bool] = True
    enable_mtls: Optional[bool] = False
    is_internal_route: Optional[bool] = None
    service_path: Optional[str] = None
    service_port: Optional[int] = None
    node_tags: Optional[str] = None
    idle_timeout_seconds: Optional[int] = None
    request_timeout_seconds: Optional[int] = None

    state: str = "present"

    # Read-only fields (populated from API)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
