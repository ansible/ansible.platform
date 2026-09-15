"""
Ansible NotificationTemplate dataclass - user-facing stable interface.

This dataclass represents the notification_template as seen by Ansible
playbooks. Field names and types remain stable across API versions.

copy_from is handled by the action plugin (copy operation) — it is popped
from ansible_data before this dataclass is constructed, so it is not a field
here.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleNotificationTemplate:
    """Ansible representation of a Controller notification_template."""

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    organization: Optional[str] = None
    notification_type: Optional[str] = None
    notification_configuration: Optional[dict] = None
    messages: Optional[dict] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
