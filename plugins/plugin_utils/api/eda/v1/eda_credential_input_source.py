"""API v1 EDA Credential Input Source dataclass and transform mixin.

Handles transformations between Ansible format and EDA API v1 format.

This resource uses a composite key (target_credential + source_credential +
input_field_name) instead of a ``name`` field.  The lookup is driven by
``get_find_list_query_params`` which filters by ``target_credential`` (as an
ID) and ``get_lookup_field`` which returns ``input_field_name``.  The SDK's
find logic matches the remaining ``source_credential`` via
``get_find_list_query_params`` as well.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIEdaCredentialInputSource_v1(BaseTransformMixin):
    """API v1 representation of an EDA credential input source."""

    description: Optional[str] = None
    input_field_name: Optional[str] = None
    target_credential: Optional[int] = None
    source_credential: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    organization_id: Optional[int] = None

    # Read-only fields from API
    id: Optional[int] = None


class EdaCredentialInputSourceTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for EDA Credential Input Source API v1."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APIEdaCredentialInputSource_v1":
        """Create API instance from Ansible dataclass.

        Args:
            ansible_instance: AnsibleEdaCredentialInputSource instance.
            context: Transform context with manager for FK resolution.

        Returns:
            APIEdaCredentialInputSource_v1 with resolved FK IDs.
        """
        api_data: Dict[str, Any] = {}

        # input_field_name: pass through directly
        input_field_name = getattr(ansible_instance, "input_field_name", None)
        if input_field_name is not None:
            api_data["input_field_name"] = input_field_name

        # FK resolution: target_credential name -> ID via EDA credentials endpoint
        target_credential = getattr(ansible_instance, "target_credential", None)
        if target_credential is not None:
            manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
            if manager is not None and not str(target_credential).strip().isdigit():
                api_data["target_credential"] = manager.lookup_resource_id("eda-credentials", "name", target_credential, service="eda")
            else:
                api_data["target_credential"] = int(target_credential) if target_credential is not None else None

        # FK resolution: source_credential name -> ID via EDA credentials endpoint
        source_credential = getattr(ansible_instance, "source_credential", None)
        if source_credential is not None:
            manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
            if manager is not None and not str(source_credential).strip().isdigit():
                api_data["source_credential"] = manager.lookup_resource_id("eda-credentials", "name", source_credential, service="eda")
            else:
                api_data["source_credential"] = int(source_credential) if source_credential is not None else None

        # Simple fields
        for field_name in ("description",):
            val = getattr(ansible_instance, field_name, None)
            if val is not None:
                api_data[field_name] = val

        # metadata: dict passed through directly (API accepts dicts)
        metadata = getattr(ansible_instance, "metadata", None)
        if metadata is not None:
            api_data["metadata"] = metadata

        # FK resolution: organization_name -> organization_id
        organization_name = getattr(ansible_instance, "organization_name", None)
        if organization_name is not None:
            manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
            if manager is not None:
                api_data["organization_id"] = manager.lookup_resource_id("organizations", "name", organization_name)

        # Read-only from API (for building URL in execute)
        for field_name in ("id",):
            val = getattr(ansible_instance, field_name, None)
            if val is not None:
                api_data[field_name] = val

        return APIEdaCredentialInputSource_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for EDA credential input source operations.

        Returns:
            Dict mapping operation names to EndpointOperation instances.
        """
        return {
            "create": EndpointOperation(
                path="/api/eda/v1/credential-input-sources/",
                method="POST",
                fields=["description", "input_field_name", "metadata", "target_credential", "source_credential", "organization_id"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/eda/v1/credential-input-sources/{id}/",
                method="PATCH",
                fields=["description", "metadata"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/eda/v1/credential-input-sources/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/eda/v1/credential-input-sources/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/eda/v1/credential-input-sources/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        """Return the field used to match resources during find.

        Returns:
            The lookup field name — ``input_field_name`` for composite key matching.
        """
        return "input_field_name"

    @classmethod
    def get_find_list_query_params(cls, api_data) -> Dict[str, Any]:
        """Return query parameters for filtering the list endpoint.

        For composite-key resources, the list endpoint is filtered by
        ``target_credential`` (and ``source_credential`` when available)
        so the SDK's find logic can match by ``input_field_name``.

        Args:
            api_data: API dataclass instance with resolved FK IDs.

        Returns:
            Query parameters dict for the list endpoint.
        """
        params: Dict[str, Any] = {}
        target_credential = getattr(api_data, "target_credential", None)
        if target_credential is not None:
            try:
                params["target_credential"] = int(str(target_credential).strip())
            except (ValueError, TypeError):
                pass
        source_credential = getattr(api_data, "source_credential", None)
        if source_credential is not None:
            try:
                params["source_credential"] = int(str(source_credential).strip())
            except (ValueError, TypeError):
                pass
        return params

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "AnsibleEdaCredentialInputSource":
        """Transform from API format to Ansible format.

        Args:
            api_data: Raw API response dict.
            context: Transform context (unused for this resource).

        Returns:
            AnsibleEdaCredentialInputSource instance.
        """
        from ....ansible_models.eda_credential_input_source import AnsibleEdaCredentialInputSource

        target_val = api_data.get("target_credential")
        target_str = str(target_val) if target_val is not None else ""

        source_val = api_data.get("source_credential")
        source_str = str(source_val) if source_val is not None else ""

        return AnsibleEdaCredentialInputSource(
            input_field_name=api_data.get("input_field_name", ""),
            target_credential=target_str,
            source_credential=source_str,
            description=api_data.get("description"),
            metadata=api_data.get("metadata"),
            id=api_data.get("id"),
        )
