"""
API v1 AuthenticatorUser dataclass and transform mixin.

AuthenticatorUser supports moving a user to a new authenticator via the
POST /authenticator_users/{id}/move/ sub-resource (the spec does not expose
a PATCH on the detail endpoint).
Lookup is done by authenticator_user_id (the numeric ID in the API).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext


def _resolve_fk(manager, endpoint: str, lookup_field: str, value) -> Optional[int]:
    """Resolve a name or id to an integer id."""
    if value is None:
        return None
    if str(value).isdigit():
        return int(value)
    try:
        return manager.lookup_resource_id(endpoint, lookup_field, str(value))
    except Exception:
        return None


@dataclass
class APIAuthenticatorUser_v1(BaseTransformMixin):
    """API v1 representation of a gateway authenticator user."""

    # Fields for POST /authenticator_users/{id}/move/
    new_authenticator: Optional[int] = None  # required by spec (was: authenticator)
    keep_memberships: Optional[bool] = None  # required by spec
    merge_accounts_with_same_uid: Optional[bool] = None  # required by spec
    remove_other_authenticators: Optional[bool] = None  # required by spec
    new_uid: Optional[str] = None
    merge_with_user: Optional[str] = None

    # Read-only / path param
    id: Optional[int] = None
    uid: Optional[str] = None
    user: Optional[int] = None


class AuthenticatorUserTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for AuthenticatorUser API v1."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIAuthenticatorUser_v1:
        api_data: Dict[str, Any] = {}
        manager = context.manager if isinstance(context, TransformContext) else context.get("manager")

        # authenticator_user_id is the API resource id for path param
        authenticator_user_id = getattr(ansible_instance, "authenticator_user_id", None)
        if authenticator_user_id is not None:
            if str(authenticator_user_id).isdigit():
                api_data["id"] = int(authenticator_user_id)

        # Resolve FK: new_authenticator name/id -> int
        # The spec field is "new_authenticator"; the module exposes it as
        # "authenticator" for user-facing simplicity.
        authenticator = getattr(ansible_instance, "authenticator", None)
        if authenticator is not None and manager:
            resolved = _resolve_fk(manager, "authenticators", "name", authenticator)
            if resolved is not None:
                api_data["new_authenticator"] = resolved
        elif authenticator is not None:
            if str(authenticator).isdigit():
                api_data["new_authenticator"] = int(authenticator)

        for field in (
            "new_uid",
            "keep_memberships",
            "merge_with_user",
            "merge_accounts_with_same_uid",
            "remove_other_authenticators",
        ):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIAuthenticatorUser_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        # The spec exposes a dedicated POST /move/ sub-resource for updating an
        # authenticator user's authenticator.  There is no PATCH on the detail
        # endpoint — the spec only allows GET there.
        return {
            "update": EndpointOperation(
                path="/api/gateway/v1/authenticator_users/{id}/move/",
                method="POST",
                fields=[
                    "new_authenticator",
                    "new_uid",
                    "keep_memberships",
                    "merge_with_user",
                    "merge_accounts_with_same_uid",
                    "remove_other_authenticators",
                ],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/gateway/v1/authenticator_users/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/gateway/v1/authenticator_users/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "id"

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ...ansible_models.authenticator_user import AnsibleAuthenticatorUser

        return AnsibleAuthenticatorUser(
            authenticator_user_id=str(api_data.get("id", "")),
            authenticator=str(api_data.get("authenticator", "")),
            new_uid=api_data.get("new_uid"),
            keep_memberships=api_data.get("keep_memberships", False),
            merge_with_user=api_data.get("merge_with_user"),
            merge_accounts_with_same_uid=api_data.get("merge_accounts_with_same_uid", False),
            remove_other_authenticators=api_data.get("remove_other_authenticators", False),
            id=api_data.get("id"),
            uid=api_data.get("uid"),
            user=api_data.get("user"),
        )
