"""
Ansible User dataclass - user-facing stable interface.

This dataclass represents the user as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class AnsibleUser:
    """
    Ansible representation of a user.

    This is the stable interface that playbooks interact with.
    Field names match the DOCUMENTATION and remain consistent
    across different platform API versions.
    """

    # Required fields
    username: str

    # Optional fields
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    is_superuser: Optional[bool] = None
    is_platform_auditor: Optional[bool] = None
    organizations: Optional[List[str]] = None
    associated_authenticators: Optional[Dict[str, Any]] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None

    def __post_init__(self):
        """Validate and normalize data after initialization."""
        # Ensure organizations is a list
        if self.organizations is None:
            self.organizations = []
        elif not isinstance(self.organizations, list):
            self.organizations = [self.organizations]
