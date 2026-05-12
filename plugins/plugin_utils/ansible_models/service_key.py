"""
Ansible Service Key dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleServiceKey:
    """Ansible representation of a service key."""

    name: str
    new_name: Optional[str] = None
    is_active: Optional[bool] = None
    service_cluster: Optional[str] = None
    algorithm: Optional[str] = None
    secret: Optional[str] = None
    secret_length: Optional[int] = None
    mark_previous_inactive: Optional[bool] = None
    state: str = "present"

    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
