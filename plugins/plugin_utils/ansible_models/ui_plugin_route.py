"""
Ansible UIPluginRoute dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class AnsibleUIPluginRoute:
    """Ansible representation of a gateway UI plugin route."""

    # Required
    name: Union[str, int]

    # Optional / update fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    ui_plugin_path: Optional[str] = None
    http_port: Optional[Union[str, int]] = None
    service_cluster: Optional[Union[str, int]] = None
    is_service_https: Optional[bool] = False
    service_port: Optional[int] = None
    node_tags: Optional[str] = None
    order: Optional[int] = None
    idle_timeout_seconds: Optional[int] = None
    request_timeout_seconds: Optional[int] = None

    state: str = "present"

    # Read-only / auto-generated fields
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
    gateway_path: Optional[str] = None
    service_path: Optional[str] = None
    enable_gateway_auth: Optional[bool] = None
    is_internal_route: Optional[bool] = None
