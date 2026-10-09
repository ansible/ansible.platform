"""
Ansible JobCancel dataclass - user-facing stable interface.

This dataclass represents the controller job cancel request as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleJobCancel:
    """
    Ansible representation of a controller job cancel request.

    This is the stable interface that playbooks interact with.
    Field names match the DOCUMENTATION and remain consistent
    across different platform API versions.
    """

    # Required fields
    job_id: int = 0

    # Optional fields
    fail_if_not_running: bool = False

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
