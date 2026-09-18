"""
Ansible WorkflowJobTemplate dataclass - user-facing stable interface.

This dataclass represents the workflow_job_template as seen by Ansible
playbooks. Field names and types remain stable across API versions.

copy_from, survey_spec, labels, and the four notification_templates_* fields
are handled by the action plugin (copy operation / sub-resource / association
sync) — they are popped from ansible_data before this dataclass is
constructed, so they are not fields here.

Building the workflow's node graph (the legacy module's workflow_nodes /
schema option) is out of scope for this migration — it is a separate
resource (workflow_job_template_node) with its own CRUD/association surface,
not a field of the workflow_job_template itself.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleWorkflowJobTemplate:
    """Ansible representation of a Controller workflow_job_template."""

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    extra_vars: Optional[dict] = None
    job_tags: Optional[str] = None
    skip_tags: Optional[str] = None
    ask_tags_on_launch: Optional[bool] = None
    organization: Optional[str] = None
    allow_simultaneous: Optional[bool] = None
    ask_variables_on_launch: Optional[bool] = None
    inventory: Optional[str] = None
    limit: Optional[str] = None
    scm_branch: Optional[str] = None
    ask_inventory_on_launch: Optional[bool] = None
    ask_scm_branch_on_launch: Optional[bool] = None
    ask_limit_on_launch: Optional[bool] = None
    ask_labels_on_launch: Optional[bool] = None
    ask_skip_tags_on_launch: Optional[bool] = None
    webhook_service: Optional[str] = None
    webhook_credential: Optional[str] = None
    survey_enabled: Optional[bool] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
