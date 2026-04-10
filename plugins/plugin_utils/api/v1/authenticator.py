"""
API v1 Authenticator dataclass and transform mixin.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIAuthenticator_v1(BaseTransformMixin):
    """API v1 representation of an authenticator."""

    name: Optional[str] = None
    slug: Optional[str] = None
    enabled: Optional[bool] = None
    create_objects: Optional[bool] = None
    remove_users: Optional[bool] = None
    type: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    order: Optional[int] = None
    auto_migrate_users_to: Optional[int] = None

    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class AuthenticatorTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for Authenticator API v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIAuthenticator_v1":
        api_data = {}
        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
        op = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")
        if op == "create":
            api_data["name"] = name or new_name
        elif op == "update":
            if new_name is not None:
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                api_data["name"] = name
        for field in ("slug", "enabled", "create_objects", "remove_users", "type", "configuration", "order"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
        auto_migrate = getattr(ansible_instance, "auto_migrate_users_to", None)
        if auto_migrate is not None:
            manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
            if manager:
                try:
                    api_data["auto_migrate_users_to"] = manager.lookup_resource_id("authenticators", "name", str(auto_migrate))
                except Exception as e:
                    logger.debug("Lookup auto_migrate_users_to for authenticator: %s", e)
            if "auto_migrate_users_to" not in api_data and str(auto_migrate).isdigit():
                api_data["auto_migrate_users_to"] = int(auto_migrate)
        for field in ("id", "created", "modified", "url"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
        return APIAuthenticator_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = ["name", "slug", "enabled", "create_objects", "remove_users", "type", "configuration", "order", "auto_migrate_users_to"]
        return {
            "create": EndpointOperation(path="/api/gateway/v1/authenticators/", method="POST", fields=fields, required_for="create", order=1),
            "update": EndpointOperation(
                path="/api/gateway/v1/authenticators/{id}/", method="PATCH", fields=fields, path_params=["id"], required_for="update", order=1
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/authenticators/{id}/", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1
            ),
            "get": EndpointOperation(path="/api/gateway/v1/authenticators/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path="/api/gateway/v1/authenticators/", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleAuthenticator":
        from ...ansible_models.authenticator import AnsibleAuthenticator

        am = api_data.get("auto_migrate_users_to")
        return AnsibleAuthenticator(
            name=api_data.get("name", ""),
            slug=api_data.get("slug"),
            enabled=api_data.get("enabled"),
            create_objects=api_data.get("create_objects"),
            remove_users=api_data.get("remove_users"),
            type=api_data.get("type"),
            configuration=api_data.get("configuration"),
            order=api_data.get("order"),
            auto_migrate_users_to=str(am) if am is not None else None,
            id=api_data.get("id"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )
