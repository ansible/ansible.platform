"""
Ansible Inventory dataclass - user-facing stable interface.

This dataclass represents the inventory as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

import json
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AnsibleInventory:
    """Ansible representation of a Controller inventory."""

    # Required / identity
    name: str
    organization: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    kind: Optional[str] = None
    host_filter: Optional[str] = None
    variables: Optional[Any] = None
    prevent_instance_group_fallback: Optional[bool] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None

    def __post_init__(self):
        if isinstance(self.variables, dict):
            self.variables = json.dumps(self.variables)
