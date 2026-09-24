"""
Ansible Schedule dataclass - user-facing stable interface.

This dataclass represents the schedule as seen by Ansible playbooks.
Field names and types remain stable across API versions.

credentials/labels/instance_groups are handled by the action plugin
(association sync) — they are popped from ansible_data before this dataclass
is constructed, so they are not fields here.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleSchedule:
    """Ansible representation of a Controller schedule."""

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    rrule: Optional[str] = None
    description: Optional[str] = None
    # unified_job_template is required at the DOCUMENTATION/argspec level for
    # create; defaults to None here so internal callers building a partial
    # instance for a lookup don't need to supply it (matches
    # AnsibleInventory's organization precedent).
    unified_job_template: Optional[str] = None
    execution_environment: Optional[str] = None
    extra_data: Optional[dict] = None
    forks: Optional[int] = None
    inventory: Optional[str] = None
    job_slice_count: Optional[int] = None
    timeout: Optional[int] = None
    scm_branch: Optional[str] = None
    job_type: Optional[str] = None
    job_tags: Optional[str] = None
    skip_tags: Optional[str] = None
    limit: Optional[str] = None
    diff_mode: Optional[bool] = None
    verbosity: Optional[int] = None
    enabled: Optional[bool] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
