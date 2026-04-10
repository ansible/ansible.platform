"""
Ansible Http Port dataclass - user-facing stable interface.

This dataclass represents the http port as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleHttpPort:
    """
    Ansible representation of an http port.

    This is the stable interface that playbooks interact with.
    Field names match the DOCUMENTATION and remain consistent
    across different platform API versions.
    """

    # Required / identity
    name: str

    # Optional / CRUD fields
    new_name: Optional[str] = None
    number: Optional[int] = None
    use_https: bool = False
    is_api_port: bool = False
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
