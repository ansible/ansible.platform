"""
Ansible InventorySource dataclass - user-facing stable interface.

This dataclass represents the inventory source as seen by Ansible playbooks.
Field names and types remain stable across API versions.

notification_templates_started/success/error are handled by the action plugin
(association sync) — they are popped from ansible_data before this dataclass
is constructed, so they are not fields here.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleInventorySource:
    """Ansible representation of a Controller inventory source."""

    # Required / identity
    name: str

    # Optional fields
    # inventory is required at the DOCUMENTATION/argspec level; defaults to None
    # here so internal callers building a partial instance for a lookup don't
    # need to supply it (matches AnsibleInventory's organization precedent).
    inventory: Optional[str] = None
    new_name: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    source_path: Optional[str] = None
    source_vars: Optional[dict] = None
    scm_branch: Optional[str] = None
    credential: Optional[str] = None
    enabled_var: Optional[str] = None
    enabled_value: Optional[str] = None
    host_filter: Optional[str] = None
    overwrite: Optional[bool] = None
    overwrite_vars: Optional[bool] = None
    timeout: Optional[int] = None
    verbosity: Optional[int] = None
    limit: Optional[str] = None
    execution_environment: Optional[str] = None
    update_on_launch: Optional[bool] = None
    update_cache_timeout: Optional[int] = None
    source_project: Optional[str] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
