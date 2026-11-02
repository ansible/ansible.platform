"""
Ansible JobLaunch dataclass - user-facing stable interface.

This dataclass represents a job launch request as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class AnsibleJobLaunch:
    """Ansible representation of a Controller job launch."""

    # Required / identity
    name: str

    # Scoping
    organization: Optional[str] = None

    # Launch parameters
    job_type: Optional[str] = None
    inventory: Optional[str] = None
    credentials: Optional[List[str]] = None
    extra_vars: Optional[Dict[str, Any]] = None
    limit: Optional[str] = None
    tags: Optional[List[str]] = None
    skip_tags: Optional[List[str]] = None
    scm_branch: Optional[str] = None
    verbosity: Optional[int] = None
    diff_mode: Optional[bool] = None
    credential_passwords: Optional[Dict[str, Any]] = None
    execution_environment: Optional[str] = None
    forks: Optional[int] = None
    instance_groups: Optional[List[str]] = None
    labels: Optional[List[str]] = None
    job_slice_count: Optional[int] = None
    job_timeout: Optional[int] = None

    # Action-only fields (not sent to API, consumed by action plugin)
    wait: bool = False
    interval: float = 2.0
    timeout: Optional[int] = None

    # Read-only (populated from launch response)
    id: Optional[int] = None
    status: Optional[str] = None
