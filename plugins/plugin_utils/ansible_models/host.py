"""
Ansible Host dataclass - user-facing stable interface.

This dataclass represents the host as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleHost:
    """Ansible representation of a Controller host."""

    # Required / identity
    name: str

    # Optional fields
    # inventory is required at the DOCUMENTATION/argspec level; defaults to None
    # here so internal callers building a partial instance for a lookup don't
    # need to supply it (matches AnsibleInventory's organization precedent).
    inventory: Optional[str] = None
    new_name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    instance_id: Optional[str] = None
    variables: Optional[dict] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
