"""
Ansible Authenticator dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AnsibleAuthenticator:
    """Ansible representation of an authenticator."""

    name: str
    new_name: Optional[str] = None
    slug: Optional[str] = None
    enabled: Optional[bool] = None
    create_objects: Optional[bool] = None
    remove_users: Optional[bool] = None
    type: Optional[str] = None  # auth plugin type (e.g. ansible_base.authentication.authenticator_plugins.ldap)
    configuration: Optional[Dict[str, Any]] = None
    order: Optional[int] = None
    auto_migrate_users_to: Optional[str] = None
    state: str = "present"

    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
