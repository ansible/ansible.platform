"""
API v2 ControllerCredentialType dataclass and transform mixin.

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
class APIControllerCredentialType_v2(BaseTransformMixin):
    """API v2 representation of a Controller credential type."""

    name: Optional[str] = None
    description: Optional[str] = None
    kind: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    injectors: Optional[Dict[str, Any]] = None
    managed: Optional[bool] = None

    # Read-only fields from API
    id: Optional[int] = None


class ControllerCredentialTypeTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for ControllerCredentialType API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APIControllerCredentialType_v2":
        api_data: Dict[str, Any] = {}

        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
        op = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")
        include_nulls = (
            getattr(context, "include_nulls_for_update", False) if isinstance(context, TransformContext) else context.get("include_nulls_for_update", False)
        )

        if op == "create":
            api_data["name"] = name or new_name
            # Custom credential types are always non-managed
            api_data["managed"] = False
        elif op == "update":
            if new_name is not None:
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                api_data["name"] = name

        for field in ("description", "kind", "inputs", "injectors"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
            elif op == "update" and include_nulls:
                api_data[field] = "" if field in ("description",) else None

        # Read-only from API (for building URL in execute)
        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIControllerCredentialType_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/credential_types/",
                method="POST",
                fields=["name", "description", "kind", "inputs", "injectors", "managed"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/credential_types/{id}/",
                method="PATCH",
                fields=["name", "description", "kind", "inputs", "injectors"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/credential_types/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/credential_types/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/credential_types/",
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
        from ....ansible_models.controller_credential_type import (
            AnsibleControllerCredentialType,
        )

        return AnsibleControllerCredentialType(
            name=api_data.get("name", ""),
            description=api_data.get("description"),
            kind=api_data.get("kind"),
            inputs=api_data.get("inputs"),
            injectors=api_data.get("injectors"),
            id=api_data.get("id"),
        )
