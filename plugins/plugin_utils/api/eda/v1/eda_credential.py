"""API v1 EDA Credential dataclass and transform mixin."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

BASE_PATH = "/api/eda/v1/eda-credentials"
TEST_PATH = "/api/eda/v1/eda-credentials/{id}/test/"


def resolve_eda_credential_fk(manager, endpoint: str, value: Any, resource_label: str) -> Optional[int]:
    """Resolve an EDA credential foreign key from a name or numeric ID.

    Args:
        manager: Platform client used to look up named resources.
        endpoint: EDA API endpoint for the referenced resource.
        value: Resource name or ID supplied by the user.
        resource_label: Label used in lookup errors.

    Returns:
        The resource ID, or ``None`` when no value was supplied.

    Raises:
        ValueError: If a supplied name cannot be resolved unambiguously.
    """
    if value is None or value == "":
        return None

    value_str = str(value).strip()
    if value_str.isdigit():
        return int(value_str)
    if manager is None:
        raise ValueError("A manager is required to resolve %s '%s'" % (resource_label, value))

    resource_id = manager.lookup_resource_id(endpoint, "name", str(value), service="eda", require_unique=True)
    if resource_id is None:
        raise ValueError("%s '%s' was not found" % (resource_label, value))
    return resource_id


def _api_fk_id(api_value: Any, flat_id: Any, manager: Any, endpoint: str, resource_label: str) -> Optional[str]:
    """Return an API foreign key in the string-ID form used by the Ansible model."""
    if isinstance(api_value, dict):
        value = api_value.get("id")
        if value is None:
            value = flat_id if flat_id is not None else api_value.get("name")
    else:
        value = flat_id if flat_id is not None else api_value

    if value is None:
        return None
    if str(value).strip().isdigit():
        return str(int(str(value).strip()))
    return str(resolve_eda_credential_fk(manager, endpoint, value, resource_label))


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
            api_data["credential_type_id"] = resolve_eda_credential_fk(manager, "credential-types", credential_type, "Credential type")

        # Resolve organization name -> organization_id
        organization = getattr(ansible_instance, "organization", None)
        if organization is not None:
            api_data["organization_id"] = resolve_eda_credential_fk(manager, "organizations", organization, "Organization")

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
    def get_find_list_query_params(cls, api_data: APIEdaCredential_v1) -> Dict[str, Any]:
        """Scope credential name lookups to the requested organization."""
        if api_data.organization_id is None:
            return {}
        return {"organization_id": api_data.organization_id}

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleEdaCredential":
        """Transform from API format to Ansible format.

        The EDA API returns credential_type and organization as nested
        objects (e.g. ``{"id": 1, "name": "..."}``).  Extract the ID
        so the Ansible model stores a comparable string representation.
        """
        from ....ansible_models.eda_credential import AnsibleEdaCredential

        manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
        credential_type_str = _api_fk_id(api_data.get("credential_type"), api_data.get("credential_type_id"), manager, "credential-types", "Credential type")
        organization_str = _api_fk_id(api_data.get("organization"), api_data.get("organization_id"), manager, "organizations", "Organization")

        ansible_data = {
            "name": api_data.get("name", ""),
            "description": api_data.get("description"),
            "credential_type": credential_type_str,
            "organization": organization_str,
            "id": api_data.get("id"),
        }
        return AnsibleEdaCredential(**ansible_data)
