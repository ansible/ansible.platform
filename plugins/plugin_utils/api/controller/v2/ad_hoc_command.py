"""Transform and endpoint definitions for Controller ad hoc command launches."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....ansible_models.ad_hoc_command import AnsibleAdHocCommand
from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

AD_HOC_COMMANDS_ENDPOINT = "/api/controller/v2/ad_hoc_commands/"
AD_HOC_COMMANDS_DETAIL_ENDPOINT = "/api/controller/v2/ad_hoc_commands/{id}/"


@dataclass
class APIAdHocCommand_v2(BaseTransformMixin):
    """Controller API v2 representation of an ad hoc command launch."""

    inventory: Optional[int] = None
    credential: Optional[int] = None
    execution_environment: Optional[int] = None
    module_name: Optional[str] = None
    module_args: Optional[str] = None
    job_type: Optional[str] = None
    limit: Optional[str] = None
    forks: Optional[int] = None
    verbosity: Optional[int] = None
    become_enabled: Optional[bool] = None
    diff_mode: Optional[bool] = None
    extra_vars: Optional[str] = None


class AdHocCommandTransformMixin_v2(BaseTransformMixin):
    """Map Ansible ad hoc command inputs to the Controller launch request."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance: AnsibleAdHocCommand,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIAdHocCommand_v2:
        """Resolve resource references and serialize fields for Controller."""
        manager = cls._normalize_context(context).manager
        inventory = manager.lookup_resource_id("inventories", "name", ansible_instance.inventory or "", service="controller", require_unique=True)
        credential = manager.lookup_resource_id("credentials", "name", ansible_instance.credential or "", service="controller", require_unique=True)

        execution_environment = None
        if ansible_instance.execution_environment:
            execution_environment = manager.lookup_resource_id(
                "execution_environments", "name", ansible_instance.execution_environment, service="controller", require_unique=True
            )

        extra_vars = ansible_instance.extra_vars
        if extra_vars is not None:
            extra_vars = json.dumps(extra_vars) if isinstance(extra_vars, dict) else str(extra_vars)

        return APIAdHocCommand_v2(
            inventory=inventory,
            credential=credential,
            execution_environment=execution_environment,
            module_name=ansible_instance.module_name,
            module_args=ansible_instance.module_args,
            job_type=ansible_instance.job_type,
            limit=ansible_instance.limit,
            forks=ansible_instance.forks,
            verbosity=ansible_instance.verbosity,
            become_enabled=ansible_instance.become_enabled,
            diff_mode=ansible_instance.diff_mode,
            extra_vars=extra_vars,
        )

    @classmethod
    def to_payload(
        cls,
        ansible_instance: AnsibleAdHocCommand,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Return only populated API request fields in endpoint order."""
        api_data = cls.from_ansible_data(ansible_instance, context)
        fields = cls.get_endpoint_operations()["create"].fields
        return {field_name: getattr(api_data, field_name) for field_name in fields if getattr(api_data, field_name) is not None}

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> AnsibleAdHocCommand:
        """Map a Controller ad hoc command response to the Ansible model."""
        return AnsibleAdHocCommand(id=api_data.get("id"), status=api_data.get("status"))

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Describe the launch and detail endpoints used by this module."""
        return {
            "create": EndpointOperation(
                path=AD_HOC_COMMANDS_ENDPOINT,
                method="POST",
                fields=[
                    "inventory",
                    "credential",
                    "execution_environment",
                    "module_name",
                    "module_args",
                    "job_type",
                    "limit",
                    "forks",
                    "verbosity",
                    "become_enabled",
                    "diff_mode",
                    "extra_vars",
                ],
                required_for="create",
                order=1,
            ),
            "get": EndpointOperation(
                path=AD_HOC_COMMANDS_DETAIL_ENDPOINT,
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        """Use the launch response ID for detail lookups."""
        return "id"
