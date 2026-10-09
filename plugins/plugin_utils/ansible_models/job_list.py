"""
Ansible JobList dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class AnsibleJobList:
    """
    Ansible representation of a job list query.
    """

    status: Optional[str] = None
    page: Optional[int] = None
    all_pages: bool = False
    query: Optional[Dict] = None
