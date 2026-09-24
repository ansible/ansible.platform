"""
Ansible JobLaunch dataclass - user-facing stable interface.

This dataclass represents a job launch request as seen by Ansible playbooks.
Fields match the DOCUMENTATION options that are sent to the API. The
wait/interval/timeout parameters control polling in
PlatformService/DirectHTTPClient.execute() (platform_manager.py,
direct_client.py) — they are popped from the ansible_data dict before this
dataclass is constructed, so they are not fields here.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AnsibleJobLaunch:
    """Ansible representation of a job template launch request."""

    name: str
    job_type: Optional[str] = None
    inventory: Optional[str] = None
    credentials: Optional[List[str]] = None
    extra_vars: Optional[dict] = None
    limit: Optional[str] = None
    tags: Optional[List[str]] = None
    scm_branch: Optional[str] = None
    skip_tags: Optional[List[str]] = None
    verbosity: Optional[int] = None
    diff_mode: Optional[bool] = None
    credential_passwords: Optional[dict] = None
    execution_environment: Optional[str] = None
    forks: Optional[int] = None
    instance_groups: Optional[List[str]] = None
    job_slice_count: Optional[int] = None
    labels: Optional[List[str]] = None
    job_timeout: Optional[int] = None

    # Read-only fields from API response (of the launched job)
    id: Optional[int] = None
    status: Optional[str] = None
    finished: Optional[str] = None
