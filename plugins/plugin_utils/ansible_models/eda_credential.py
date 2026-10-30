"""Ansible EDA Credential dataclass - user-facing stable interface."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AnsibleEdaCredential:
    """Ansible representation of an EDA credential."""

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    credential_type: Optional[str] = None
    organization: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    copy_from: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
