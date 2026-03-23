"""
Ansible RoleTeamAssignment dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class AnsibleRoleTeamAssignment:
    """
    Ansible representation of a role-team assignment.

    This is the stable interface that playbooks interact with.
    Field names match the DOCUMENTATION and remain consistent
    across different platform API versions.
    """

    # Required
    role_definition: str

    # Target team (mutually exclusive: team name OR team_ansible_id)
    team: Optional[str] = None
    team_ansible_id: Optional[str] = None

    # Object selector (mutually exclusive groups)
    object_id: Optional[int] = None
    object_ids: Optional[List] = None          # multi-object iteration
    object_ansible_id: Optional[str] = None

    state: str = "present"

    # Read-only (populated from API response)
    id: Optional[int] = None
    url: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None

    # Multi-object result list (populated by action plugin)
    assignments: Optional[List[dict]] = None
