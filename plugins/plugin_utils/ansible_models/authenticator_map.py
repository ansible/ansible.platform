"""
Ansible Authenticator Map dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AnsibleAuthenticatorMap:
    """Ansible representation of an authenticator map."""

    name: str
    authenticator: str  # name or id
    new_name: Optional[str] = None
    new_authenticator: Optional[str] = None
    revoke: Optional[bool] = None
    map_type: Optional[str] = None
    team: Optional[str] = None
    organization: Optional[str] = None
    role: Optional[str] = None
    triggers: Optional[Dict[str, Any]] = None
    order: Optional[int] = None
    state: str = "present"

    # For find: resolved authenticator id (set by action plugin before find)
    authenticator_id: Optional[int] = None

    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
