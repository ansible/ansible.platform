"""
API v2 ControllerProject dataclass and transform mixin.

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
class APIControllerProject_v2(BaseTransformMixin):
    """API v2 representation of a Controller project."""

    name: Optional[str] = None
    description: Optional[str] = None
    scm_type: Optional[str] = None
    scm_url: Optional[str] = None
    local_path: Optional[str] = None
    scm_branch: Optional[str] = None
    scm_refspec: Optional[str] = None
    credential: Optional[int] = None
    scm_clean: Optional[bool] = None
    scm_delete_on_update: Optional[bool] = None
    scm_track_submodules: Optional[bool] = None
    scm_update_on_launch: Optional[bool] = None
    scm_update_cache_timeout: Optional[int] = None
    allow_override: Optional[bool] = None
    timeout: Optional[int] = None
    default_environment: Optional[int] = None
    organization: Optional[int] = None
    signature_validation_credential: Optional[int] = None

    # Read-only fields from API
    id: Optional[int] = None


class ControllerProjectTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for ControllerProject API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APIControllerProject_v2":
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

        # FK resolution: organization (Gateway-owned, default service)
        organization = getattr(ansible_instance, "organization", None)
        if organization is not None:
            if manager is not None and not str(organization).strip().isdigit():
                api_data["organization"] = manager.lookup_resource_id("organizations", "name", organization)
            else:
                api_data["organization"] = int(organization) if organization is not None else None

        # FK resolution: credential (Controller-owned)
        credential = getattr(ansible_instance, "credential", None)
        if credential is not None:
            if manager is not None and not str(credential).strip().isdigit():
                api_data["credential"] = manager.lookup_resource_id("credentials", "name", credential, service="controller")
            else:
                api_data["credential"] = int(credential) if credential is not None else None

        # FK resolution: default_environment (Controller-owned)
        default_environment = getattr(ansible_instance, "default_environment", None)
        if default_environment is not None:
            if manager is not None and not str(default_environment).strip().isdigit():
                api_data["default_environment"] = manager.lookup_resource_id("execution_environments", "name", default_environment, service="controller")
            else:
                api_data["default_environment"] = int(default_environment) if default_environment is not None else None

        # FK resolution: signature_validation_credential (Controller-owned)
        sig_cred = getattr(ansible_instance, "signature_validation_credential", None)
        if sig_cred is not None:
            if manager is not None and not str(sig_cred).strip().isdigit():
                api_data["signature_validation_credential"] = manager.lookup_resource_id("credentials", "name", sig_cred, service="controller")
            else:
                api_data["signature_validation_credential"] = int(sig_cred) if sig_cred is not None else None

        # Scalar fields
        for field in (
            "description",
            "scm_type",
            "scm_url",
            "local_path",
            "scm_branch",
            "scm_refspec",
            "scm_clean",
            "scm_delete_on_update",
            "scm_track_submodules",
            "scm_update_on_launch",
            "scm_update_cache_timeout",
            "allow_override",
            "timeout",
        ):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
            elif op == "update" and include_nulls and field == "description":
                api_data[field] = ""

        # Read-only from API (for building URL in execute)
        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIControllerProject_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = [
            "name",
            "description",
            "local_path",
            "scm_type",
            "scm_url",
            "scm_branch",
            "scm_refspec",
            "scm_clean",
            "scm_track_submodules",
            "scm_delete_on_update",
            "credential",
            "timeout",
            "organization",
            "scm_update_on_launch",
            "scm_update_cache_timeout",
            "allow_override",
            "default_environment",
            "signature_validation_credential",
        ]
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/projects/",
                method="POST",
                fields=fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/projects/{id}/",
                method="PATCH",
                fields=fields,
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/projects/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/projects/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/projects/",
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
        from ....ansible_models.controller_project import AnsibleControllerProject

        def _str_or_none(val):
            return str(val) if val is not None else None

        return AnsibleControllerProject(
            name=api_data.get("name", ""),
            description=api_data.get("description"),
            scm_type=api_data.get("scm_type"),
            scm_url=api_data.get("scm_url"),
            local_path=api_data.get("local_path"),
            scm_branch=api_data.get("scm_branch"),
            scm_refspec=api_data.get("scm_refspec"),
            credential=_str_or_none(api_data.get("credential")),
            scm_clean=api_data.get("scm_clean"),
            scm_delete_on_update=api_data.get("scm_delete_on_update"),
            scm_track_submodules=api_data.get("scm_track_submodules"),
            scm_update_on_launch=api_data.get("scm_update_on_launch"),
            scm_update_cache_timeout=api_data.get("scm_update_cache_timeout"),
            allow_override=api_data.get("allow_override"),
            timeout=api_data.get("timeout"),
            default_environment=_str_or_none(api_data.get("default_environment")),
            organization=_str_or_none(api_data.get("organization")),
            signature_validation_credential=_str_or_none(api_data.get("signature_validation_credential")),
            id=api_data.get("id"),
        )
