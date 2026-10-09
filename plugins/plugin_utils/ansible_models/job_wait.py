"""
Ansible JobWait dataclass - user-facing stable interface.

This dataclass represents a job wait query as seen by Ansible playbooks.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleJobWait:
    """
    Ansible representation of a job wait operation.

    This is a non-CRUD module that polls a job until completion.
    """

    job_id: int = 0
    interval: float = 2.0
    timeout: Optional[int] = None
    job_type: str = "jobs"
