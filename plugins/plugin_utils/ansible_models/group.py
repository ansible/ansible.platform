"""
Ansible Group dataclass - user-facing stable interface.

This dataclass represents the group as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

import json
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AnsibleGroup:
    """Ansible representation of a Controller inventory group."""

    # Required / identity
    name: str
    inventory: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    variables: Optional[Any] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None

    def __post_init__(self):
        if isinstance(self.variables, dict):
            self.variables = json.dumps(self.variables)
