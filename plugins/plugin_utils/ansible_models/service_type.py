"""
Ansible Service Type dataclass - user-facing stable interface.

This dataclass represents the service type as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleServiceType:
    """
    Ansible representation of a service type.

    This is the stable interface that playbooks interact with.
    Field names match the DOCUMENTATION and remain consistent
    across different platform API versions.
    """

    # Required / identity
    name: str

    # Optional / CRUD fields
    new_name: Optional[str] = None
    ping_url: Optional[str] = None
    login_path: Optional[str] = None
    logout_path: Optional[str] = None
    service_index_path: Optional[str] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
