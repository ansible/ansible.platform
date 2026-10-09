"""
Ansible Subscriptions dataclass - user-facing stable interface.

This dataclass represents the subscription query as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class AnsibleSubscriptions:
    """
    Ansible representation of a subscription query.

    This is the stable interface that playbooks interact with.
    Unlike standard CRUD resources, this represents a query operation
    that retrieves available subscriptions from Red Hat.
    """

    # Red Hat credentials (mutually exclusive pairs)
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

    # Client-side filters
    filters: Dict = field(default_factory=dict)
