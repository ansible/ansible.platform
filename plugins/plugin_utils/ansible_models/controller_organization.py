"""Internal Ansible model for Controller-side organization settings."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AnsibleControllerOrganization:
    """Represent the Controller-side settings attached to an organization.

    This model supports updates to existing Controller organizations. Gateway
    owns organization lifecycle and RBAC, so there is no Controller create or
    delete operation here.
    """

    name: Optional[str] = None
    description: Optional[str] = None
    default_environment: Optional[str] = None
    max_hosts: Optional[int] = None
    galaxy_credentials: Optional[List[str]] = None
    instance_groups: Optional[List[str]] = None
    state: str = "present"
    id: Optional[int] = None
