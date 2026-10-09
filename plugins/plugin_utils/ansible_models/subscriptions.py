"""
Ansible Subscriptions dataclass - user-facing stable interface.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AnsibleSubscriptions:
    """Ansible representation of controller subscription data."""

    # Credentials for Red Hat subscription lookup
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

    # Client-side filters
    filters: Optional[Dict[str, Any]] = field(default_factory=dict)

    # Output: list of subscription dicts returned by the API
    subscriptions: Optional[List[Dict[str, Any]]] = field(default_factory=list)
