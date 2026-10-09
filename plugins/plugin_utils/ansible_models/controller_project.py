"""
Ansible ControllerProject dataclass - user-facing stable interface.

This dataclass represents the project as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleControllerProject:
    """Ansible representation of a Controller project."""

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    scm_type: Optional[str] = None
    scm_url: Optional[str] = None
    local_path: Optional[str] = None
    scm_branch: Optional[str] = None
    scm_refspec: Optional[str] = None
    credential: Optional[str] = None
    scm_clean: Optional[bool] = None
    scm_delete_on_update: Optional[bool] = None
    scm_track_submodules: Optional[bool] = None
    scm_update_on_launch: Optional[bool] = None
    scm_update_cache_timeout: Optional[int] = None
    allow_override: Optional[bool] = None
    timeout: Optional[int] = None
    default_environment: Optional[str] = None
    organization: Optional[str] = None
    signature_validation_credential: Optional[str] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
