"""Ansible DecisionEnvironment dataclass - user-facing stable interface.

This dataclass represents the EDA decision environment as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleDecisionEnvironment:
    """Ansible representation of an EDA decision environment."""

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    credential: Optional[str] = None
    pull_policy: Optional[str] = None
    organization_name: Optional[str] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
