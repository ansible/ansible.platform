"""
Ansible ControllerCredentialType dataclass - user-facing stable interface.

This dataclass represents the credential type as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AnsibleControllerCredentialType:
    """Ansible representation of a Controller credential type."""

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    kind: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    injectors: Optional[Dict[str, Any]] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
