"""
Ansible Controller Bulk Host Create dataclass - user-facing stable interface.

This dataclass represents the bulk host create request as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AnsibleControllerBulkHostCreate:
    """
    Ansible representation of a bulk host create request.

    This is the stable interface that playbooks interact with.
    Field names match the DOCUMENTATION and remain consistent
    across different platform API versions.
    """

    # Required fields
    hosts: List[dict] = field(default_factory=list)
    inventory: Optional[str] = None
