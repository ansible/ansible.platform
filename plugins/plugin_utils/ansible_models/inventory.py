"""
Ansible Inventory dataclass - user-facing stable interface.

This dataclass represents the inventory as seen by Ansible playbooks.
Field names and types remain stable across API versions.

instance_groups/input_inventories/copy_from are handled by the action plugin
(association sync / copy operation) — they are popped from ansible_data before
this dataclass is constructed, so they are not fields here.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleInventory:
    """Ansible representation of a Controller inventory."""

    # Required / identity
    name: str

    # Optional fields
    # organization is required at the DOCUMENTATION/argspec level; it defaults
    # to None here (not a bare positional field) so internal callers that
    # build a partial instance for a lookup-only "find" (e.g. copy_resource())
    # don't need to supply it. Matches the AnsibleJobTemplate precedent.
    organization: Optional[str] = None
    new_name: Optional[str] = None
    description: Optional[str] = None
    kind: Optional[str] = None
    host_filter: Optional[str] = None
    variables: Optional[dict] = None
    prevent_instance_group_fallback: Optional[bool] = None
    opa_query_path: Optional[str] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
