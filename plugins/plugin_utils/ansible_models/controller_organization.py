"""Internal Ansible model for Controller-side organization settings."""

from dataclasses import dataclass
from typing import Optional


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
    id: Optional[int] = None
