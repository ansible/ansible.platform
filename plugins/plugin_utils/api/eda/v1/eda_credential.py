"""API v1 EDA Credential dataclass and transform mixin."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

BASE_PATH = "/api/eda/v1/eda-credentials"


@dataclass
class APIEdaCredential_v1(BaseTransformMixin):
    """API v1 representation of an EDA credential."""

    name: Optional[str] = None
    description: Optional[str] = None
    credential_type_id: Optional[int] = None
    organization_id: Optional[int] = None
    inputs: Optional[Dict[str, Any]] = None

    # Read-only fields from API
    id: Optional[int] = None


class EdaCredentialTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for EDA Credential API v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIEdaCredential_v1":
        """Create API instance from Ansible dataclass."""
        api_data: Dict[str, Any] = {}

        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
        op = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")

        if op == "create":
            api_data["name"] = name
        elif op == "update":
            if new_name is not None:
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                api_data["name"] = name

        manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")

        # Resolve credential_type name -> credential_type_id
        credential_type = getattr(ansible_instance, "credential_type", None)
        if credential_type is not None:
            if manager is not None and not str(credential_type).strip().isdigit():
                api_data["credential_type_id"] = manager.lookup_resource_id("credential-types", "name", credential_type, service="eda")
            else:
                api_data["credential_type_id"] = int(credential_type) if credential_type is not None else None

        # Resolve organization name -> organization_id
        organization = getattr(ansible_instance, "organization", None)
        if organization is not None:
            if manager is not None and not str(organization).strip().isdigit():
                api_data["organization_id"] = manager.lookup_resource_id("organizations", "name", organization)
            else:
                api_data["organization_id"] = int(organization)

        description = getattr(ansible_instance, "description", None)
        if description is not None:
            api_data["description"] = description

        inputs = getattr(ansible_instance, "inputs", None)
        if inputs is not None:
            api_data["inputs"] = inputs

        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIEdaCredential_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for EDA credential operations."""
        return {
            "create": EndpointOperation(
                path="/api/eda/v1/eda-credentials/",
                method="POST",
                fields=["name", "description", "credential_type_id", "organization_id", "inputs"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/eda/v1/eda-credentials/{id}/",
                method="PATCH",
                fields=["name", "description", "credential_type_id", "organization_id", "inputs"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/eda/v1/eda-credentials/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/eda/v1/eda-credentials/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/eda/v1/eda-credentials/",
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
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleEdaCredential":
        """Transform from API format to Ansible format.

        The EDA API returns credential_type and organization as nested
        objects (e.g. ``{"id": 1, "name": "..."}``).  Extract the ID
        so the Ansible model stores a comparable string representation.
        """
        from ....ansible_models.eda_credential import AnsibleEdaCredential

        # credential_type is a nested object: {"id": 28, "name": "..."}
        credential_type_obj = api_data.get("credential_type")
        if isinstance(credential_type_obj, dict):
            credential_type_str = str(credential_type_obj["id"])
        elif credential_type_obj is not None:
            credential_type_str = str(credential_type_obj)
        else:
            credential_type_str = None

        # organization is a nested object: {"id": 1, "name": "..."}
        organization_obj = api_data.get("organization")
        if isinstance(organization_obj, dict):
            organization_str = str(organization_obj["id"])
        elif organization_obj is not None:
            organization_str = str(organization_obj)
        else:
            organization_str = None

        ansible_data = {
            "name": api_data.get("name", ""),
            "description": api_data.get("description"),
            "credential_type": credential_type_str,
            "organization": organization_str,
            "id": api_data.get("id"),
        }
        return AnsibleEdaCredential(**ansible_data)
