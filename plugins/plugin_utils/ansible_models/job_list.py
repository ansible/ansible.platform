"""
Ansible Controller Job List dataclass - user-facing stable interface.

This dataclass represents the query parameters for listing Controller jobs.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class AnsibleJobList:
    """
    Ansible representation of a Controller job list query.

    This is a read-only query dataclass. It holds filter parameters
    that are sent to the Controller jobs API endpoint.
    """

    # Optional filter fields
    status: Optional[str] = None
    page: Optional[int] = None
    all_pages: bool = False
    query: Optional[Dict] = field(default=None)
