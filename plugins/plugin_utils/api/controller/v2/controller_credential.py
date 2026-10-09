"""API v2 ControllerCredential dataclass and transform mixin."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIControllerCredential_v2(BaseTransformMixin):
    """API v2 representation of a Controller credential."""

    name: Optional[str] = None
    description: Optional[str] = None
    credential_type: Optional[int] = None
    organization: Optional[int] = None
    user: Optional[int] = None
    team: Optional[int] = None
    inputs: Optional[Dict[str, Any]] = None
    id: Optional[int] = None


class ControllerCredentialTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for ControllerCredential API v2."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIControllerCredential_v2":
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

        manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")

        credential_type = getattr(ansible_instance, "credential_type", None)
        if credential_type is not None:
            if manager is not None and not str(credential_type).strip().isdigit():
                api_data["credential_type"] = manager.lookup_resource_id("credential_types", "name", credential_type, service="controller")
            else:
                api_data["credential_type"] = int(credential_type) if credential_type is not None else None

        organization = getattr(ansible_instance, "organization", None)
        if organization is not None:
            if manager is not None and not str(organization).strip().isdigit():
                api_data["organization"] = manager.lookup_resource_id("organizations", "name", organization)
            else:
                api_data["organization"] = int(organization)

        user = getattr(ansible_instance, "user", None)
        if user is not None:
            if manager is not None and not str(user).strip().isdigit():
                api_data["user"] = manager.lookup_resource_id("users", "username", user)
            else:
                api_data["user"] = int(user)

        team = getattr(ansible_instance, "team", None)
        if team is not None:
            if manager is not None and not str(team).strip().isdigit():
                api_data["team"] = manager.lookup_resource_id("teams", "name", team)
            else:
                api_data["team"] = int(team)

        description = getattr(ansible_instance, "description", None)
        if description is not None:
            api_data["description"] = description
        elif op == "update" and include_nulls:
            api_data["description"] = ""

        inputs = getattr(ansible_instance, "inputs", None)
        if inputs is not None:
            api_data["inputs"] = inputs

        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIControllerCredential_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/credentials/",
                method="POST",
                fields=["name", "description", "credential_type", "organization", "user", "team", "inputs"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/credentials/{id}/",
                method="PATCH",
                fields=["name", "description", "credential_type", "organization", "user", "team", "inputs"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/credentials/{id}/", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1
            ),
            "get": EndpointOperation(path="/api/controller/v2/credentials/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path="/api/controller/v2/credentials/", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]):
        from ....ansible_models.controller_credential import AnsibleControllerCredential

        credential_type_val = api_data.get("credential_type")
        credential_type_str = str(credential_type_val) if credential_type_val is not None else ""
        organization_val = api_data.get("organization")
        organization_str = str(organization_val) if organization_val is not None else None
        user_val = api_data.get("user")
        user_str = str(user_val) if user_val is not None else None
        team_val = api_data.get("team")
        team_str = str(team_val) if team_val is not None else None

        return AnsibleControllerCredential(
            name=api_data.get("name", ""),
            credential_type=credential_type_str,
            description=api_data.get("description"),
            organization=organization_str,
            user=user_str,
            team=team_str,
            id=api_data.get("id"),
        )
