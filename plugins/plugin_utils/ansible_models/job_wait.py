"""
Ansible JobWait dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleJobWait:
    """Ansible representation of a job wait operation."""

    # Required fields
    job_id: Optional[int] = None

    # Optional fields
    job_type: str = "jobs"
    interval: Optional[float] = 2
    timeout: Optional[int] = None

    # Read-only (returned after wait completes)
    id: Optional[int] = None
    status: Optional[str] = None
    elapsed: Optional[float] = None
    started: Optional[str] = None
    finished: Optional[str] = None
