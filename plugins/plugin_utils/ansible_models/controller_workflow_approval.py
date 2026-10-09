"""
Ansible Controller Workflow Approval dataclass - user-facing stable interface.

This dataclass represents the workflow approval action as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleControllerWorkflowApproval:
    """
    Ansible representation of a controller workflow approval action.

    This is the stable interface that playbooks interact with.
    Field names match the DOCUMENTATION and remain consistent
    across different platform API versions.
    """

    # Required fields
    workflow_job_id: int = 0
    name: str = ""

    # Optional fields
    action: str = "approve"
    interval: float = 1.0
    timeout: int = 10

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
