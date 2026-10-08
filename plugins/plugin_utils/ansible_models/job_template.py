"""
Ansible ControllerJobTemplate dataclass - user-facing stable interface.

This dataclass represents the job template as seen by Ansible playbooks.
Field names and types remain stable across API versions. Association fields
(credentials, labels, notification templates, instance groups), copy_from,
and survey_spec are not part of core CRUD and are added in a follow-up PR.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AnsibleControllerJobTemplate:
    """Ansible representation of a controller job template."""

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    job_type: Optional[str] = None
    inventory: Optional[str] = None
    organization: Optional[str] = None
    project: Optional[str] = None
    playbook: Optional[str] = None
    scm_branch: Optional[str] = None
    forks: Optional[int] = None
    limit: Optional[str] = None
    verbosity: Optional[int] = None
    extra_vars: Optional[Dict[str, Any]] = None
    job_tags: Optional[str] = None
    force_handlers: Optional[bool] = None
    skip_tags: Optional[str] = None
    start_at_task: Optional[str] = None
    timeout: Optional[int] = None
    use_fact_cache: Optional[bool] = None
    execution_environment: Optional[str] = None
    host_config_key: Optional[str] = None
    ask_scm_branch_on_launch: Optional[bool] = None
    ask_diff_mode_on_launch: Optional[bool] = None
    ask_variables_on_launch: Optional[bool] = None
    ask_limit_on_launch: Optional[bool] = None
    ask_tags_on_launch: Optional[bool] = None
    ask_skip_tags_on_launch: Optional[bool] = None
    ask_job_type_on_launch: Optional[bool] = None
    ask_verbosity_on_launch: Optional[bool] = None
    ask_inventory_on_launch: Optional[bool] = None
    ask_credential_on_launch: Optional[bool] = None
    ask_execution_environment_on_launch: Optional[bool] = None
    ask_labels_on_launch: Optional[bool] = None
    ask_forks_on_launch: Optional[bool] = None
    ask_job_slice_count_on_launch: Optional[bool] = None
    ask_timeout_on_launch: Optional[bool] = None
    ask_instance_groups_on_launch: Optional[bool] = None
    survey_enabled: Optional[bool] = None
    become_enabled: Optional[bool] = None
    diff_mode: Optional[bool] = None
    allow_simultaneous: Optional[bool] = None
    job_slice_count: Optional[int] = None
    webhook_service: Optional[str] = None
    webhook_credential: Optional[str] = None
    prevent_instance_group_fallback: Optional[bool] = None
    opa_query_path: Optional[str] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
