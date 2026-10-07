"""
Ansible NotificationTemplate dataclass - user-facing stable interface.

This dataclass represents the notification template as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AnsibleNotificationTemplate:
    """Ansible representation of a Controller notification template."""

    # Required / identity
    name: str
    organization: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    notification_type: Optional[str] = None
    notification_configuration: Optional[Dict[str, Any]] = None
    messages: Optional[Dict[str, Any]] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
