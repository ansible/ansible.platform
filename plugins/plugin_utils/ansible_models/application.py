"""
Ansible Application dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import List, Optional, Union


@dataclass
class AnsibleApplication:
    """Ansible representation of a gateway application."""

    name: Union[str, int]
    new_name: Optional[str] = None
    description: Optional[str] = None

    algorithm: Optional[str] = None
    authorization_grant_type: Optional[str] = None
    client_type: Optional[str] = None

    # For organization, the action plugin resolves name -> id so comparisons are stable.
    organization: Optional[Union[str, int]] = None
    new_organization: Optional[Union[str, int]] = None

    # Stored as the API representation (space-separated string). The action plugin
    # accepts list input and the transform joins it into a string on requests.
    redirect_uris: Optional[Union[str, List[str]]] = None
    post_logout_redirect_uris: Optional[Union[str, List[str]]] = None

    skip_authorization: Optional[bool] = None
    app_url: Optional[str] = None

    # For user, the action plugin resolves username -> id so comparisons are stable.
    user: Optional[Union[str, int]] = None

    state: str = "present"

    # Read-only fields
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None

    # API-generated OAuth credentials — returned by the API on create/update,
    # never accepted as module input (not in argument_spec).
    # Surfaced in the flat top-level result only (via _EXTRA_RETURN_FIELDS),
    # NOT included in the nested 'application' round-trip dict.
    # client_secret is intentionally omitted — it is only present in the API
    # response once on initial create and should not be stored or re-emitted.
    client_id: Optional[str] = None
