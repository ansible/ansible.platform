"""
API v2 CredentialInputSource dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APICredentialInputSource_v2(BaseTransformMixin):
    """API v2 representation of a Controller credential input source."""

    description: Optional[str] = None
    input_field_name: Optional[str] = None
    target_credential: Optional[int] = None
    source_credential: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    # Read-only fields from API
    id: Optional[int] = None


class CredentialInputSourceTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for CredentialInputSource API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APICredentialInputSource_v2":
        api_data: Dict[str, Any] = {}

        # input_field_name: pass through directly
        input_field_name = getattr(ansible_instance, "input_field_name", None)
        if input_field_name is not None:
            api_data["input_field_name"] = input_field_name

        # FK resolution: target_credential name → ID
        target_credential = getattr(ansible_instance, "target_credential", None)
        if target_credential is not None:
            manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
            if manager is not None and not str(target_credential).strip().isdigit():
                api_data["target_credential"] = manager.lookup_resource_id("credentials", "name", target_credential, service="controller")
            else:
                api_data["target_credential"] = int(target_credential) if target_credential is not None else None

        # FK resolution: source_credential name → ID
        source_credential = getattr(ansible_instance, "source_credential", None)
        if source_credential is not None:
            manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
            if manager is not None and not str(source_credential).strip().isdigit():
                api_data["source_credential"] = manager.lookup_resource_id("credentials", "name", source_credential, service="controller")
            else:
                api_data["source_credential"] = int(source_credential) if source_credential is not None else None

        # Simple fields
        for field in ("description",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        # metadata: dict passed through directly (API accepts dicts)
        metadata = getattr(ansible_instance, "metadata", None)
        if metadata is not None:
            api_data["metadata"] = metadata

        # Read-only from API (for building URL in execute)
        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APICredentialInputSource_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/credential_input_sources/",
                method="POST",
                fields=["description", "input_field_name", "metadata", "target_credential", "source_credential"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/credential_input_sources/{id}/",
                method="PATCH",
                fields=["description", "input_field_name", "metadata", "target_credential", "source_credential"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/credential_input_sources/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/credential_input_sources/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/credential_input_sources/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "input_field_name"

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.credential_input_source import AnsibleCredentialInputSource

        target_val = api_data.get("target_credential")
        target_str = str(target_val) if target_val is not None else ""

        source_val = api_data.get("source_credential")
        source_str = str(source_val) if source_val is not None else None

        return AnsibleCredentialInputSource(
            input_field_name=api_data.get("input_field_name", ""),
            target_credential=target_str,
            description=api_data.get("description"),
            source_credential=source_str,
            metadata=api_data.get("metadata"),
            id=api_data.get("id"),
        )
