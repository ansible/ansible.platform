"""
Ansible Service Node dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleServiceNode:
    """Ansible representation of a service node."""

    name: str
    new_name: Optional[str] = None
    address: Optional[str] = None
    service_cluster: Optional[str] = None
    tags: Optional[str] = None
    state: str = "present"

    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
