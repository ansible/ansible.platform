"""Ansible EDA Credential Input Source dataclass - user-facing stable interface.

This dataclass represents the EDA credential input source as seen by Ansible playbooks.
Field names and types remain stable across API versions.

Unlike most resources, credential input sources do not have a ``name`` field.
They are uniquely identified by the composite key of ``target_credential``,
``source_credential``, and ``input_field_name``.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AnsibleEdaCredentialInputSource:
    """Ansible representation of an EDA credential input source."""

    # Required / identity (composite key)
    input_field_name: str
    target_credential: str
    source_credential: str

    # Optional fields
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    organization_name: Optional[str] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
