"""
Ansible WorkflowApproval dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleWorkflowApproval:
    """Ansible representation of a workflow approval action."""

    # The approval node ID (determined at runtime by polling)
    id: Optional[int] = None

    # Module parameters (used for module logic in the action plugin)
    workflow_job_id: Optional[int] = None
    name: Optional[str] = None
    action: Optional[str] = None
    timeout: Optional[int] = None
    interval: Optional[float] = None
