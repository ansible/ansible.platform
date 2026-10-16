"""
Ansible CredentialInputSource dataclass - user-facing stable interface.

This dataclass represents the credential input source as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AnsibleCredentialInputSource:
    """Ansible representation of a Controller credential input source."""

    # Required / identity (composite key: target_credential + input_field_name)
    input_field_name: str
    target_credential: str

    # Optional fields
    description: Optional[str] = None
    source_credential: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
