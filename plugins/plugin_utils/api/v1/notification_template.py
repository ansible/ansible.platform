"""
API v1 NotificationTemplate dataclass and transform mixin.

Handles transformations between Ansible format and the Controller API format
for notification_template resources.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...ansible_models.notification_template import AnsibleNotificationTemplate
from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APINotificationTemplate_v1:
    """Wire format for Controller notification_templates."""

    name: str
    description: Optional[str] = None
    organization: Optional[int] = None
    notification_type: Optional[str] = None
    notification_configuration: Optional[dict] = None
    messages: Optional[dict] = None
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class NotificationTemplateTransformMixin_v1(BaseTransformMixin):
    """Transforms between AnsibleNotificationTemplate and APINotificationTemplate_v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance: AnsibleNotificationTemplate, context: TransformContext) -> APINotificationTemplate_v1:
        """Forward: Ansible model -> API wire format."""
        params: Dict[str, Any] = {
            "name": ansible_instance.new_name or ansible_instance.name,
        }

        if ansible_instance.organization is not None:
            params["organization"] = context.manager.lookup_resource_id("/api/controller/v2/organizations/", "name", ansible_instance.organization)

        for field in ("description", "notification_type", "notification_configuration", "messages"):
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = value

        # Read-only from API (for building the {id} URL path param in execute)
        for field in ("id", "created", "modified", "url"):
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = value

        return APINotificationTemplate_v1(**params)

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: TransformContext) -> AnsibleNotificationTemplate:
        """Reverse: API response -> Ansible model."""
        org = api_data.get("organization")

        return AnsibleNotificationTemplate(
            id=api_data.get("id"),
            name=api_data.get("name", ""),
            description=api_data.get("description"),
            organization=str(org) if org is not None else None,
            notification_type=api_data.get("notification_type"),
            notification_configuration=api_data.get("notification_configuration"),
            messages=api_data.get("messages"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = ["name", "description", "organization", "notification_type", "notification_configuration", "messages"]

        return {
            "create": EndpointOperation(
                path="/api/controller/v2/notification_templates/",
                method="POST",
                fields=fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/notification_templates/{id}/",
                method="PATCH",
                fields=fields,
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/notification_templates/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/notification_templates/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/notification_templates/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def get_find_list_query_params(cls, ansible_data: APINotificationTemplate_v1) -> Dict[str, Any]:
        """Scope name lookups by organization — notification_template names are only unique per-org."""
        org_id = getattr(ansible_data, "organization", None)
        if org_id is not None:
            return {"organization": org_id}
        return {}
