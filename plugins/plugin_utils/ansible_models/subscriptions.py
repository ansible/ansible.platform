"""
Ansible Subscriptions dataclass - user-facing stable interface.

Singleton resource: no id field, no state field.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AnsibleSubscriptions:
    """Ansible representation of subscriptions (singleton config)."""

    # Input: Red Hat credentials (mutually exclusive pairs)
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

    # Input: client-side filters
    filters: Optional[Dict[str, Any]] = field(default_factory=dict)

    # Output: list of subscription objects returned from the API
    subscriptions: Optional[List[Dict[str, Any]]] = field(default_factory=list)
