"""
Ansible JobWait dataclass - user-facing stable interface.

This dataclass represents a "wait for an existing job to finish" request as
seen by Ansible playbooks. The wait/interval/timeout parameters control
polling in PlatformService/DirectHTTPClient.execute() (platform_manager.py,
direct_client.py) — interval/timeout are popped from the ansible_data dict
before this dataclass is constructed, so only interval/timeout are absent
here; wait is always forced True by the action plugin (this module always
waits — that is its entire purpose).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleJobWait:
    """Ansible representation of a "wait for job" request."""

    job_id: int
    job_type: str = "jobs"

    # Read-only fields from API response (of the job/update being waited on)
    id: Optional[int] = None
    status: Optional[str] = None
    started: Optional[str] = None
    finished: Optional[str] = None
    elapsed: Optional[float] = None
