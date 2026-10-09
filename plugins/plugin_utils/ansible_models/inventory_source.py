"""
Ansible InventorySource dataclass - user-facing stable interface.

This dataclass represents the inventory source as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

import json
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class AnsibleInventorySource:
    """Ansible representation of a Controller inventory source."""

    # Required / identity
    name: str
    inventory: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    source_path: Optional[str] = None
    source_vars: Optional[Any] = None
    enabled_var: Optional[str] = None
    enabled_value: Optional[str] = None
    host_filter: Optional[str] = None
    limit: Optional[str] = None
    credential: Optional[str] = None
    execution_environment: Optional[str] = None
    overwrite: Optional[bool] = None
    overwrite_vars: Optional[bool] = None
    timeout: Optional[int] = None
    verbosity: Optional[int] = None
    update_on_launch: Optional[bool] = None
    update_cache_timeout: Optional[int] = None
    source_project: Optional[str] = None
    scm_branch: Optional[str] = None
    state: str = "present"

    # Association fields (not sent to API directly, handled by action plugin)
    notification_templates_started: Optional[List[str]] = field(default=None)
    notification_templates_success: Optional[List[str]] = field(default=None)
    notification_templates_error: Optional[List[str]] = field(default=None)

    # Read-only fields (populated from API responses)
    id: Optional[int] = None

    def __post_init__(self):
        if isinstance(self.source_vars, dict):
            self.source_vars = json.dumps(self.source_vars)
