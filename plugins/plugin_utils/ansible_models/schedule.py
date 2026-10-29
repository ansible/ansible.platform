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
    extra_data: Optional[dict] = None
    inventory: Optional[str] = None
    scm_branch: Optional[str] = None
    job_type: Optional[str] = None
    job_tags: Optional[str] = None
    skip_tags: Optional[str] = None
    limit: Optional[str] = None
    diff_mode: Optional[bool] = None
    verbosity: Optional[int] = None
    forks: Optional[int] = None
    job_slice_count: Optional[int] = None
    timeout: Optional[int] = None
    execution_environment: Optional[str] = None
    state: str = "present"
    id: Optional[int] = None
