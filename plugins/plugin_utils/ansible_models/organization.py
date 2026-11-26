"""
Ansible Organization dataclass - user-facing stable interface.

This dataclass represents the organization as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AnsibleOrganization:
    """
    Ansible representation of an organization.

    This is the stable interface that playbooks interact with.
    Field names match the DOCUMENTATION and remain consistent
    across different platform API versions. Controller-owned organization
    settings and associations are optional and are applied to the linked
    Controller organization when provided.
    """

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    default_environment: Optional[str] = None
    max_hosts: Optional[int] = None
    opa_query_path: Optional[str] = None
    instance_groups: Optional[List[str]] = None
    notification_templates_started: Optional[List[str]] = None
    notification_templates_success: Optional[List[str]] = None
    notification_templates_error: Optional[List[str]] = None
    notification_templates_approvals: Optional[List[str]] = None
    galaxy_credentials: Optional[List[str]] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
