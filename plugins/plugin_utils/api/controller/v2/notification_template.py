from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

BASE_PATH = "/api/controller/v2/notification_templates"


@dataclass
class APINotificationTemplate_v2(BaseTransformMixin):
    name: Optional[str] = None
    description: Optional[str] = None
    organization: Optional[int] = None
    notification_type: Optional[str] = None
    notification_configuration: Optional[Dict[str, Any]] = None
    messages: Optional[Dict[str, Any]] = None
    id: Optional[int] = None


class NotificationTemplateTransformMixin_v2(BaseTransformMixin):
    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APINotificationTemplate_v2":
        api_data: Dict[str, Any] = {}
        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
        op = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")
        include_nulls = (
            getattr(context, "include_nulls_for_update", False) if isinstance(context, TransformContext) else context.get("include_nulls_for_update", False)
        )
        if op == "create":
            api_data["name"] = name or new_name
        elif op == "update":
            if new_name is not None:
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                api_data["name"] = name
        organization = getattr(ansible_instance, "organization", None)
        if organization is not None:
            manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
            if manager is not None and not str(organization).strip().isdigit():
                api_data["organization"] = manager.lookup_resource_id("organizations", "name", organization)
            else:
                api_data["organization"] = int(organization) if organization is not None else None
        for field in ("description", "notification_type", "notification_configuration", "messages"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
            elif op == "update" and include_nulls and field == "description":
                api_data[field] = ""
        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
        return APINotificationTemplate_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/notification_templates/",
                method="POST",
                fields=["name", "description", "organization", "notification_type", "notification_configuration", "messages"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/notification_templates/{id}/",
                method="PATCH",
                fields=["name", "description", "organization", "notification_type", "notification_configuration", "messages"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/notification_templates/{id}/", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/notification_templates/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1
            ),
            "list": EndpointOperation(path="/api/controller/v2/notification_templates/", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def get_find_list_query_params(cls, api_data) -> Dict[str, Any]:
        organization_id = getattr(api_data, "organization", None)
        if organization_id is not None:
            try:
                return {"organization": int(str(organization_id).strip())}
            except (ValueError, TypeError):
                pass
        return {}

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]):
        from ....ansible_models.notification_template import AnsibleNotificationTemplate

        org_id = api_data.get("organization")
        organization = str(org_id) if org_id is not None else None
        manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
        if manager and org_id is not None:
            try:
                names = manager.lookup_organization_names([org_id])
                if names:
                    organization = names[0]
            except Exception:
                pass

        return AnsibleNotificationTemplate(
            name=api_data.get("name", ""),
            organization=organization,
            description=api_data.get("description"),
            notification_type=api_data.get("notification_type"),
            notification_configuration=api_data.get("notification_configuration"),
            messages=api_data.get("messages"),
            id=api_data.get("id"),
        )
