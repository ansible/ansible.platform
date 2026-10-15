"""
Ansible WorkflowJobTemplateNode dataclass - user-facing stable interface.

This dataclass represents the workflow job template node as seen by Ansible playbooks.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleWorkflowJobTemplateNode:
    """Ansible representation of a Controller workflow job template node."""

    # Required / identity
    identifier: str
    workflow_job_template: str

    # Optional fields
    unified_job_template: Optional[str] = None
    all_parents_must_converge: Optional[bool] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
