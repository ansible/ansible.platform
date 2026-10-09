"""
Ansible JobList dataclass - user-facing stable interface for listing controller jobs.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class AnsibleJobList:
    """Ansible representation of job list query parameters."""

    status: Optional[str] = None
    page: Optional[int] = None
    all_pages: bool = False
    query: Optional[Dict] = field(default_factory=lambda: None)
