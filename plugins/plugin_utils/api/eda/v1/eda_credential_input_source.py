"""API v1 EDA Credential Input Source dataclass and transform mixin.

Handles transformations between Ansible format and EDA API v1 format.

This resource uses a composite key (target_credential + source_credential +
input_field_name) instead of a ``name`` field. The list query filters by both
credential IDs, then matches ``input_field_name`` in the returned results.
"""

from __future__ import annotations

import ast
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


def _context_manager(context: Union[TransformContext, Dict[str, Any]]):
    """Return the resource manager from either supported transform context."""
    if isinstance(context, TransformContext):
        return context.manager
    return context.get("manager")


def _resolve_id(
    manager,
    endpoint: str,
    value: Any,
    label: str,
    extra_query_params: Optional[Dict[str, Any]] = None,
    service: str = "eda",
) -> Optional[int]:
    """Resolve a numeric ID or an unambiguous EDA resource reference."""
    if value is None:
        return None

    reference = str(value).strip()
    if not reference:
        raise ValueError("%s must not be empty" % label)
    if reference.isdigit():
        return int(reference)
    if manager is None:
        raise ValueError("A manager is required to resolve %s '%s'" % (label, reference))

    lookup_kwargs: Dict[str, Any] = {"service": service, "require_unique": True}
    # Named URLs are unambiguous references handled by lookup_resource_id;
    # list filters apply only to ordinary name lookups.
    if extra_query_params and "++" not in reference:
        lookup_kwargs["extra_query_params"] = extra_query_params
    resource_id = manager.lookup_resource_id(endpoint, "name", reference, **lookup_kwargs)
    if resource_id is None:
        raise ValueError("Could not resolve %s '%s'" % (label, reference))
    return int(resource_id)


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

    find_list_requires_all_results = True
    find_list_max_objects = 100000

    @classmethod
    def resolve_reference_id(
        cls,
        manager,
        endpoint: str,
        value: Any,
        label: str,
        extra_query_params: Optional[Dict[str, Any]] = None,
        service: str = "eda",
    ) -> Optional[int]:
        """Resolve an Ansible name, URL, or ID reference to its API ID."""
        return _resolve_id(manager, endpoint, value, label, extra_query_params, service)

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
        manager = _context_manager(context)
        operation = context.operation if isinstance(context, TransformContext) else context.get("operation")
        include_nulls = (
            getattr(context, "include_nulls_for_update", False) if isinstance(context, TransformContext) else context.get("include_nulls_for_update", False)
        )

        organization_name = getattr(ansible_instance, "organization_name", None)
        organization_id = cls.resolve_reference_id(manager, "organizations", organization_name, "organization", service="eda")
        if organization_id is not None:
            api_data["organization_id"] = organization_id

        credential_scope = {"organization": organization_id} if organization_id is not None else None

        # input_field_name: pass through directly
        input_field_name = getattr(ansible_instance, "input_field_name", None)
        if input_field_name is not None:
            api_data["input_field_name"] = input_field_name

        # FK resolution: credential name or named URL -> ID via EDA endpoint.
        target_credential = getattr(ansible_instance, "target_credential", None)
        if target_credential is not None:
            api_data["target_credential"] = cls.resolve_reference_id(manager, "eda-credentials", target_credential, "target credential", credential_scope)

        # FK resolution: source_credential name -> ID via EDA credentials endpoint
        source_credential = getattr(ansible_instance, "source_credential", None)
        if source_credential is not None:
            api_data["source_credential"] = cls.resolve_reference_id(manager, "eda-credentials", source_credential, "source credential", credential_scope)

        # Simple fields
        for field_name in ("description",):
            val = getattr(ansible_instance, field_name, None)
            if val is not None:
                api_data[field_name] = val
            elif operation == "update" and include_nulls:
                api_data[field_name] = None

        # metadata: dict passed through directly (API accepts dicts)
        metadata = getattr(ansible_instance, "metadata", None)
        if metadata is not None:
            api_data["metadata"] = metadata
        elif operation == "update" and include_nulls:
            api_data["metadata"] = None

        # Read-only from API (for building URL in execute)
        for field_name in ("id",):
            val = getattr(ansible_instance, field_name, None)
            if val is not None:
                api_data[field_name] = val

        return APIEdaCredentialInputSource_v1(**api_data)

    @classmethod
    def get_fields_to_null_for_update(cls, api_data, context: Union[TransformContext, Dict[str, Any]]) -> frozenset:
        """Return optional fields that enforced updates should explicitly clear."""
        include_nulls = (
            getattr(context, "include_nulls_for_update", False) if isinstance(context, TransformContext) else context.get("include_nulls_for_update", False)
        )
        return frozenset({"description", "metadata"}) if include_nulls else frozenset()

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
        ``target_credential`` and ``source_credential``. The API does not
        support filtering this endpoint by ``input_field_name``; that part of
        the composite key is matched locally by ``select_find_result``.

        Args:
            api_data: API dataclass instance with resolved FK IDs.

        Returns:
            Query parameters dict for the list endpoint.
        """
        params: Dict[str, Any] = {}
        target_credential = getattr(api_data, "target_credential", None)
        if target_credential is not None:
            params["target_credential"] = int(str(target_credential).strip())
        source_credential = getattr(api_data, "source_credential", None)
        if source_credential is not None:
            params["source_credential"] = int(str(source_credential).strip())
        return params

    @classmethod
    def select_find_result(cls, list_result: dict, lookup_field: str, lookup_value: Any) -> dict:
        """Select the exact input source from the credential-scoped results."""
        results = list_result.get("results", [])
        matches = [item for item in results if str(item.get(lookup_field)) == str(lookup_value)]
        if not matches:
            raise ValueError(f"Resource with {lookup_field}={lookup_value} not found")
        if len(matches) > 1:
            raise ValueError(f"Resource with {lookup_field}={lookup_value} matched multiple resources")
        return matches[0]

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
        target_id = int(target_val) if target_val is not None else None

        source_val = api_data.get("source_credential")
        source_id = int(source_val) if source_val is not None else None

        metadata = api_data.get("metadata")
        if isinstance(metadata, str):
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                try:
                    # Some EDA releases serialize the JSONField through a text
                    # serializer and return Python's mapping representation.
                    parsed_metadata = ast.literal_eval(metadata)
                except (ValueError, SyntaxError):
                    parsed_metadata = metadata
            if isinstance(parsed_metadata, dict):
                metadata = parsed_metadata

        return AnsibleEdaCredentialInputSource(
            input_field_name=api_data.get("input_field_name", ""),
            target_credential=target_id,
            source_credential=source_id,
            description=api_data.get("description"),
            metadata=metadata,
            id=api_data.get("id"),
        )
