"""
Ansible Organization dataclass - user-facing stable interface.

This dataclass represents the organization as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleOrganization:
    """
    Ansible representation of an organization.

    This is the stable interface that playbooks interact with.
    Field names match the DOCUMENTATION and remain consistent
    across different platform API versions.
    """

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
