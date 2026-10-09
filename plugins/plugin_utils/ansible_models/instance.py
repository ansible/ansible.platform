"""
Ansible Instance dataclass - user-facing stable interface.

This dataclass represents the instance as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleInstance:
    """Ansible representation of a Controller instance."""

    # Required / identity
    hostname: str

    # Optional fields
    capacity_adjustment: Optional[float] = None
    enabled: Optional[bool] = None
    managed_by_policy: Optional[bool] = None
    node_type: Optional[str] = None
    node_state: Optional[str] = None
    listener_port: Optional[int] = None
    peers_from_control_nodes: Optional[bool] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
