"""Ansible EDA Project dataclass - user-facing stable interface."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleEdaProject:
    """Ansible representation of an EDA project."""

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    proxy: Optional[str] = None
    credential: Optional[str] = None
    organization_name: Optional[str] = None
    scm_branch: Optional[str] = None
    update_revision_on_launch: Optional[bool] = None
    scm_update_cache_timeout: Optional[int] = None

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
