"""
Ansible Label dataclass - user-facing stable interface.

This dataclass represents the label as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleLabel:
    """Ansible representation of a Controller label."""

    # Required / identity
    name: str
    organization: str

    # Optional fields
    new_name: Optional[str] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
