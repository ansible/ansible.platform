"""
Ansible WorkflowJobTemplateNode dataclass - user-facing stable interface.

This dataclass represents the workflow job template node as seen by Ansible playbooks.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleWorkflowJobTemplateNode:
    """Ansible representation of a Controller workflow job template node."""

    identifier: str
    workflow_job_template: str

    unified_job_template: Optional[str] = None
    all_parents_must_converge: Optional[bool] = None
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
