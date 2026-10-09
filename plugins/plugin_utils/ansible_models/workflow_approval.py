"""
Ansible WorkflowApproval dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleWorkflowApproval:
    """
    Ansible representation of a workflow approval operation.
    """

    workflow_job_id: int = 0
    name: Optional[str] = None
    action: str = "approve"
    interval: float = 1.0
    timeout: int = 10
