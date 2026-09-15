"""
Ansible Group dataclass - user-facing stable interface.

This dataclass represents the group as seen by Ansible playbooks.
Field names and types remain stable across API versions.

hosts/children/preserve_existing_hosts/preserve_existing_children are handled
by the action plugin (association sync) — they are popped from ansible_data
before this dataclass is constructed, so they are not fields here.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleGroup:
    """Ansible representation of a Controller group."""

    # Required / identity
    name: str

    # inventory is required at the DOCUMENTATION/argspec level; defaults to
    # None here so internal callers building a partial instance for a
    # lookup-only "find" don't need to supply it (matches AnsibleInventory's
    # organization precedent).
    inventory: Optional[str] = None
    new_name: Optional[str] = None
    description: Optional[str] = None
    variables: Optional[dict] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
