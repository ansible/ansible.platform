"""API v1 DecisionEnvironment dataclass and transform mixin.

Handles transformations between Ansible format and EDA API v1 format.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIDecisionEnvironment_v1(BaseTransformMixin):
    """API v1 representation of an EDA decision environment."""

    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    pull_policy: Optional[str] = None
    eda_credential_id: Optional[int] = None
    organization_id: Optional[int] = None

    # Read-only fields from API
    id: Optional[int] = None


class DecisionEnvironmentTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for DecisionEnvironment API v1."""

    # The legacy module required a single exact name match. Names can be
    # duplicated across organizations, but this API's list endpoint only
    # supports filtering by name, so reject ambiguity rather than choosing one.
    require_unique_lookup = True

    @classmethod
    def resolve_reference_id(cls, manager, endpoint: str, value: Any, service: str = "gateway") -> Optional[int]:
        """Resolve a reference name or ID to a numeric resource ID."""
        if value is None:
            return None

        value_str = str(value).strip()
        if value_str.isdigit():
            return int(value_str)
        if manager is None:
            raise ValueError("Cannot resolve %s '%s' without an API manager" % (endpoint, value))

        resource_id = manager.lookup_resource_id(endpoint, "name", value, service=service, require_unique=True)
        if resource_id is None:
            raise ValueError("Resource '%s' with name=%s not found" % (endpoint, value))
        return int(resource_id)

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APIDecisionEnvironment_v1":
        """Create API instance from Ansible dataclass."""
        api_data: Dict[str, Any] = {}

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

        manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")

        # FK resolution: credential (EDA-owned, eda-credentials endpoint)
        credential = getattr(ansible_instance, "credential", None)
        if credential is not None:
            api_data["eda_credential_id"] = cls.resolve_reference_id(manager, "eda-credentials", credential, service="eda")

        # FK resolution: organization (Gateway-owned, default service)
        organization_name = getattr(ansible_instance, "organization_name", None)
        if organization_name is not None:
            api_data["organization_id"] = cls.resolve_reference_id(manager, "organizations", organization_name)

        for field in ("description", "image_url", "pull_policy"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        # Read-only from API (for building URL in execute)
        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIDecisionEnvironment_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for EDA decision environment operations."""
        return {
            "create": EndpointOperation(
                path="/api/eda/v1/decision-environments/",
                method="POST",
                fields=["name", "description", "image_url", "pull_policy", "eda_credential_id", "organization_id"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/eda/v1/decision-environments/{id}/",
                method="PATCH",
                fields=["name", "description", "image_url", "pull_policy", "eda_credential_id", "organization_id"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/eda/v1/decision-environments/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/eda/v1/decision-environments/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/eda/v1/decision-environments/",
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
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        """Transform from API format to Ansible format."""
        from ....ansible_models.decision_environment import AnsibleDecisionEnvironment

        credential_val = api_data.get("eda_credential_id")
        if credential_val is None:
            credential = api_data.get("eda_credential")
            credential_val = credential.get("id") if isinstance(credential, dict) else None
        credential_str = str(credential_val) if credential_val is not None else None

        organization_val = api_data.get("organization_id")
        if organization_val is None:
            organization = api_data.get("organization")
            organization_val = organization.get("id") if isinstance(organization, dict) else None
        organization_str = str(organization_val) if organization_val is not None else None

        return AnsibleDecisionEnvironment(
            name=api_data.get("name", ""),
            description=api_data.get("description"),
            image_url=api_data.get("image_url"),
            credential=credential_str,
            pull_policy=api_data.get("pull_policy"),
            organization_name=organization_str,
            id=api_data.get("id"),
        )
