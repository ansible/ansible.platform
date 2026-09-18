"""
Ansible ExecutionEnvironment dataclass - user-facing stable interface.

This dataclass represents the execution_environment as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleExecutionEnvironment:
    """Ansible representation of a Controller execution_environment."""

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    image: Optional[str] = None
    description: Optional[str] = None
    organization: Optional[str] = None
    credential: Optional[str] = None
    pull: Optional[str] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
