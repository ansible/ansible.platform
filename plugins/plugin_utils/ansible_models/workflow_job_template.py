"""
Ansible WorkflowJobTemplate dataclass - user-facing stable interface.
"""

import json
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AnsibleWorkflowJobTemplate:
    """Ansible representation of a Controller workflow job template."""

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    organization: Optional[str] = None
    extra_vars: Optional[Any] = None
    survey_enabled: Optional[bool] = None
    allow_simultaneous: Optional[bool] = None
    ask_variables_on_launch: Optional[bool] = None
    ask_inventory_on_launch: Optional[bool] = None
    ask_scm_branch_on_launch: Optional[bool] = None
    ask_limit_on_launch: Optional[bool] = None
    ask_labels_on_launch: Optional[bool] = None
    ask_tags_on_launch: Optional[bool] = None
    ask_skip_tags_on_launch: Optional[bool] = None
    inventory: Optional[str] = None
    limit: Optional[str] = None
    scm_branch: Optional[str] = None
    job_tags: Optional[str] = None
    skip_tags: Optional[str] = None
    webhook_service: Optional[str] = None
    webhook_credential: Optional[str] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None

    def __post_init__(self):
        if isinstance(self.extra_vars, dict):
            self.extra_vars = json.dumps(self.extra_vars)
