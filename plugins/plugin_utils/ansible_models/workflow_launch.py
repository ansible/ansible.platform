"""
Ansible WorkflowLaunch dataclass - user-facing stable interface.

This dataclass represents the workflow launch request as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class AnsibleWorkflowLaunch:
    """Ansible representation of a workflow launch request."""

    # Required fields
    name: str = ""

    # Optional launch parameters
    organization: Optional[str] = None
    inventory: Optional[str] = None
    limit: Optional[str] = None
    tags: Optional[List[str]] = None
    skip_tags: Optional[List[str]] = None
    scm_branch: Optional[str] = None
    extra_vars: Optional[Dict] = None

    # Wait/poll control
    wait: bool = True
    interval: float = 2.0
    timeout: Optional[int] = None

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
