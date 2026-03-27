"""
Ansible RoleUserAssignment dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AnsibleRoleUserAssignment:
    """Ansible representation of a role-user assignment."""

    # Required for create/find; optional internally (delete only needs id)
    role_definition: Optional[str] = None

    # Target user (mutually exclusive)
    user: Optional[str] = None
    user_ansible_id: Optional[str] = None

    # Object selector (mutually exclusive groups)
    object_id: Optional[int] = None
    object_ids: Optional[List[str]] = None
    object_ansible_id: Optional[str] = None

    state: str = "present"

    # Read-only (returned from API)
    id: Optional[int] = None
    url: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None

    # Multi-object result
    assignments: Optional[List[dict]] = None
