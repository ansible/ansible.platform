"""Ansible ControllerCredential dataclass - user-facing stable interface."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AnsibleControllerCredential:
    """Ansible representation of a Controller credential."""

    name: str
    credential_type: str

    new_name: Optional[str] = None
    description: Optional[str] = None
    organization: Optional[str] = None
    user: Optional[str] = None
    team: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    update_secrets: Optional[bool] = True
    state: str = "present"

    id: Optional[int] = None
