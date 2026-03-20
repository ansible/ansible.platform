"""
Ansible AuthenticatorUser dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleAuthenticatorUser:
    """Ansible representation of a gateway authenticator user (move operation)."""

    # Required
    authenticator_user_id: str
    authenticator: str

    # Optional move fields
    new_uid: Optional[str] = None
    keep_memberships: bool = False
    merge_with_user: Optional[str] = None
    merge_accounts_with_same_uid: bool = False
    remove_other_authenticators: bool = False

    state: str = "present"

    # Read-only fields (populated from API)
    id: Optional[int] = None
    uid: Optional[str] = None
    user: Optional[int] = None
