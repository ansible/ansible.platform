"""
Ansible Schedule dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleSchedule:
    """Ansible representation of a Controller schedule."""

    name: str
    new_name: Optional[str] = None
    description: Optional[str] = None
    rrule: Optional[str] = None
    unified_job_template: Optional[str] = None
    enabled: Optional[bool] = None
    state: str = "present"
    id: Optional[int] = None
