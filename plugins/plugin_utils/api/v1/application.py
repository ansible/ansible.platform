"""
API v1 Application dataclass and transform mixin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext


@dataclass
class APIApplication_v1(BaseTransformMixin):
    """API v1 representation of a gateway application."""

    name: Optional[str] = None
    organization: Optional[int] = None

    description: Optional[str] = None
    algorithm: Optional[str] = None
    authorization_grant_type: Optional[str] = None
    client_type: Optional[str] = None

    redirect_uris: Optional[str] = None
    post_logout_redirect_uris: Optional[str] = None

    skip_authorization: Optional[bool] = None
    app_url: Optional[str] = None

    user: Optional[int] = None

    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None

    # API-generated; present in POST/PATCH responses, never sent as input.
    client_id: Optional[str] = None


def _join_uri_list(value: Union[str, List[str], None]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        return " ".join(value)
    return str(value)


class ApplicationTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for Application API v1."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIApplication_v1:
        api_data: Dict[str, Any] = {}

        # Determine operation from context
        op = context.operation if isinstance(context, TransformContext) else context.get("operation")

        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)

        if op == "create":
            api_data["name"] = name or new_name or ""
        elif op in ("update", "enforced"):
            if new_name is not None:
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                api_data["name"] = name
        else:
            api_data["name"] = name or new_name or ""

        # Determine which organization field to use based on operation.
        if op in ("update", "enforced") and getattr(ansible_instance, "new_organization", None) is not None:
            organization = getattr(ansible_instance, "new_organization", None)
        else:
            organization = getattr(ansible_instance, "organization", None)

        if organization is not None:
            org_str = str(organization).strip()
            if org_str.isdigit():
                api_data["organization"] = int(org_str)
            else:
                # Resolve organization name -> id via manager (context.manager is PlatformService directly).
                mgr = context.manager if isinstance(context, TransformContext) else context.get("manager")
                if mgr is not None:
                    try:
                        api_data["organization"] = mgr.lookup_resource_id("organizations", "name", org_str)
                    except Exception:
                        pass
                # If resolution failed, pass the raw value and let the API return a descriptive error.
                if "organization" not in api_data:
                    api_data["organization"] = organization

        # Simple fields
        for field in (
            "description",
            "algorithm",
            "authorization_grant_type",
            "client_type",
            "skip_authorization",
            "app_url",
        ):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        redirect_uris = getattr(ansible_instance, "redirect_uris", None)
        if redirect_uris is not None:
            api_data["redirect_uris"] = _join_uri_list(redirect_uris)

        post_logout_redirect_uris = getattr(ansible_instance, "post_logout_redirect_uris", None)
        if post_logout_redirect_uris is not None:
            api_data["post_logout_redirect_uris"] = _join_uri_list(post_logout_redirect_uris)

        # User is resolved to id by action plugin to avoid name/id mismatches.
        user = getattr(ansible_instance, "user", None)
        if user is not None:
            # Allow passing numeric strings as well.
            if str(user).strip().isdigit():
                api_data["user"] = int(str(user).strip())
            else:
                # Best-effort fallback: resolve username -> id via manager lookup.
                manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
                if manager:
                    try:
                        api_data["user"] = manager.lookup_resource_id("users", "username", str(user))
                    except Exception:
                        pass

        # Include read-only fields on updates if they are present in the dataclass.
        for ro in ("id", "created", "modified", "url"):
            val = getattr(ansible_instance, ro, None)
            if val is not None:
                api_data[ro] = val

        return APIApplication_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        # PATCH fields: include everything that could be required by the API.
        fields = [
            "name",
            "organization",
            "description",
            "algorithm",
            "authorization_grant_type",
            "client_type",
            "redirect_uris",
            "post_logout_redirect_uris",
            "skip_authorization",
            "app_url",
            "user",
        ]

        return {
            "create": EndpointOperation(
                path="/api/gateway/v1/applications/",
                method="POST",
                fields=fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/gateway/v1/applications/{id}/",
                method="PATCH",
                fields=fields,
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/applications/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/gateway/v1/applications/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/gateway/v1/applications/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        # We use the same composite identity as AAPModule:
        # name + organization.
        return "name"

    @classmethod
    def get_find_list_query_params(cls, ansible_data) -> Dict[str, Any]:
        org_id = getattr(ansible_data, "organization", None)
        if org_id is not None:
            try:
                return {"organization": int(str(org_id).strip())}
            except Exception:
                pass
        return {}

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ...ansible_models.application import AnsibleApplication

        # Redirect URI fields are stored as space-separated strings by the API.
        # We keep them as strings here so _update_resource()'s fallback merge
        # can safely copy them back onto APIApplication_v1 without bypassing
        # _join_uri_list().  The string->list conversion for user-facing output
        # is done in the action plugin via _LIST_FIELDS (output layer only).
        return AnsibleApplication(
            name=api_data.get("name", ""),
            organization=api_data.get("organization"),
            description=api_data.get("description"),
            algorithm=api_data.get("algorithm"),
            authorization_grant_type=api_data.get("authorization_grant_type"),
            client_type=api_data.get("client_type"),
            redirect_uris=api_data.get("redirect_uris"),
            post_logout_redirect_uris=api_data.get("post_logout_redirect_uris"),
            skip_authorization=api_data.get("skip_authorization"),
            app_url=api_data.get("app_url"),
            user=api_data.get("user"),
            id=api_data.get("id"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
            # API-generated OAuth credential — surfaced flat only, not in nested dict.
            client_id=api_data.get("client_id"),
        )
