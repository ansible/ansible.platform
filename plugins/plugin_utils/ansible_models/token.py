"""
Ansible Token dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AnsibleToken:
    """Ansible representation of a gateway OAuth2 token."""

    # Optional create fields
    description: Optional[str] = None
    application: Optional[str] = None
    organization: Optional[str] = None
    scope: Optional[str] = None

    # For delete operations
    existing_token: Optional[Dict[str, Any]] = None
    existing_token_id: Optional[str] = None

    state: str = "present"

    # Read-only (returned after create)
    id: Optional[int] = None
    token: Optional[str] = None
    url: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None
