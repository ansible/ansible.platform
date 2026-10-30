"""API v1 EDA Credential Type dataclass and transform mixin."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIEdaCredentialType_v1(BaseTransformMixin):
    """API v1 representation of an EDA credential type."""

    name: Optional[str] = None
    description: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    injectors: Optional[Dict[str, Any]] = None

    # Read-only fields from API
    id: Optional[int] = None


class EdaCredentialTypeTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for EDA Credential Type API v1.

    Handles forward (Ansible -> API) and reverse (API -> Ansible) transforms
    for EDA credential types.  The ``test`` sub-endpoint is driven directly by
    the action plugin via ``launch_resource``; this mixin covers standard CRUD.
    """

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIEdaCredentialType_v1":
        """Create API instance from Ansible dataclass.

        Args:
            ansible_instance: AnsibleEdaCredentialType instance.
            context: Transform context with manager, session, and operation.

        Returns:
            APIEdaCredentialType_v1 populated with API-ready fields.
        """
        api_data: Dict[str, Any] = {}
        op = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")

        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)

        if op == "create":
            api_data["name"] = name
        elif op == "update":
            if new_name is not None:
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                api_data["name"] = name

        for field in ("description", "inputs", "injectors"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIEdaCredentialType_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for EDA credential type operations."""
        fields = ["name", "description", "inputs", "injectors"]
        return {
            "create": EndpointOperation(
                path="/api/eda/v1/credential-types/",
                method="POST",
                fields=fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/eda/v1/credential-types/{id}/",
                method="PATCH",
                fields=fields,
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/eda/v1/credential-types/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/eda/v1/credential-types/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/eda/v1/credential-types/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        """Return the field used for existence checks."""
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleEdaCredentialType":
        """Transform from API format to Ansible format.

        Args:
            api_data: Raw API response dictionary.
            context: Transform context.

        Returns:
            AnsibleEdaCredentialType instance populated from API data.
        """
        from ....ansible_models.eda_credential_type import AnsibleEdaCredentialType

        return AnsibleEdaCredentialType(
            name=api_data.get("name", ""),
            description=api_data.get("description"),
            inputs=api_data.get("inputs"),
            injectors=api_data.get("injectors"),
            id=api_data.get("id"),
        )
