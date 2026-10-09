"""
Ansible ControllerJobWait dataclass - user-facing stable interface.

This dataclass represents the controller_job_wait parameters as seen by Ansible playbooks.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleControllerJobWait:
    """
    Ansible representation of a controller job wait operation.

    This is a Shape 3 (wait-only) resource — it polls an existing job
    by ID and never creates or modifies resources.
    """

    job_id: int = 0
    job_type: str = "jobs"
    timeout: Optional[int] = None
    interval: float = 2.0

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    status: Optional[str] = None
    elapsed: Optional[float] = None
    started: Optional[str] = None
    finished: Optional[str] = None
