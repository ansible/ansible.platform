"""
Ansible Team dataclass - user-facing stable interface.

This dataclass represents the team as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleTeam:
    """
    Ansible representation of a team.

    This is the stable interface that playbooks interact with.
    Field names match the DOCUMENTATION and remain consistent
    across different platform API versions.
    """

    # Required / identity
    name: str
    organization: str  # organization name or id

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    new_organization: Optional[str] = None
    state: str = "present"

    # Resolved id for API (set by action plugin for find; not from playbook)
    organization_id: Optional[int] = None

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
