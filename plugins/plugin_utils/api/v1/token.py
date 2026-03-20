"""
API v1 Token dataclass and transform mixin.

Tokens are non-idempotent: each POST creates a new token regardless of params.
Delete uses either the token id or the id from a previously created token dict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, Union

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
class APIToken_v1(BaseTransformMixin):
    """API v1 representation of a gateway OAuth2 token."""

    description: Optional[str] = None
    application: Optional[int] = None
    scope: Optional[str] = None

    # Read-only
    id: Optional[int] = None
    token: Optional[str] = None
    url: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None


class TokenTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for Token API v1."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIToken_v1:
        api_data: Dict[str, Any] = {}
        manager = context.manager if isinstance(context, TransformContext) else context.get("manager")

        for field in ("description", "scope"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        # Resolve FK: application name -> id
        application = getattr(ansible_instance, "application", None)
        if application is not None and manager:
            resolved = _resolve_fk(manager, "applications", "name", application)
            if resolved is not None:
                api_data["application"] = resolved

        for ro in ("id", "token", "url", "created", "modified"):
            val = getattr(ansible_instance, ro, None)
            if val is not None:
                api_data[ro] = val

        return APIToken_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/gateway/v1/tokens/",
                method="POST",
                fields=["description", "application", "scope"],
                required_for="create",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/tokens/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/gateway/v1/tokens/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/gateway/v1/tokens/",
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
        from ...ansible_models.token import AnsibleToken

        return AnsibleToken(
            description=api_data.get("description"),
            application=api_data.get("application"),
            scope=api_data.get("scope"),
            id=api_data.get("id"),
            token=api_data.get("token"),
            url=api_data.get("url"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
        )
