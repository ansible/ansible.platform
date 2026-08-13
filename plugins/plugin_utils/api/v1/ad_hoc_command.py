"""
API v1 AdHocCommand dataclass and transform mixin.

Handles transformations between Ansible format and the Controller API format
for ad hoc command resources.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...ansible_models.ad_hoc_command import AnsibleAdHocCommand
from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIAdHocCommand_v1:
    """Wire format for ad hoc commands."""

    module_name: str
    inventory: Optional[int] = None
    credential: Optional[int] = None
    job_type: Optional[str] = None
    limit: Optional[str] = None
    module_args: Optional[str] = None
    forks: Optional[int] = None
    verbosity: Optional[int] = None
    extra_vars: Optional[str] = None
    become_enabled: Optional[bool] = None
    diff_mode: Optional[bool] = None
    execution_environment: Optional[int] = None
    id: Optional[int] = None
    status: Optional[str] = None


class AdHocCommandTransformMixin_v1(BaseTransformMixin):
    """Transforms between AnsibleAdHocCommand and APIAdHocCommand_v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance: AnsibleAdHocCommand, context: TransformContext) -> APIAdHocCommand_v1:
        """Forward: Ansible model -> API wire format."""
        params: Dict[str, Any] = {
            "module_name": ansible_instance.module_name,
        }

        if ansible_instance.module_args is not None:
            params["module_args"] = ansible_instance.module_args

        if ansible_instance.inventory is not None:
            params["inventory"] = context.manager.lookup_resource_id("inventories", "name", ansible_instance.inventory)

        if ansible_instance.credential is not None:
            params["credential"] = context.manager.lookup_resource_id("credentials", "name", ansible_instance.credential)

        if ansible_instance.execution_environment is not None:
            params["execution_environment"] = context.manager.lookup_resource_id("execution_environments", "name", ansible_instance.execution_environment)

        for field in ("job_type", "limit", "forks", "verbosity", "become_enabled", "diff_mode"):
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = value

        # Convert extra_vars dict to JSON string for the API
        if ansible_instance.extra_vars is not None:
            if isinstance(ansible_instance.extra_vars, dict):
                params["extra_vars"] = json.dumps(ansible_instance.extra_vars)
            else:
                params["extra_vars"] = str(ansible_instance.extra_vars)

        return APIAdHocCommand_v1(**params)

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: TransformContext) -> AnsibleAdHocCommand:
        """Reverse: API response -> Ansible model."""
        return AnsibleAdHocCommand(
            id=api_data.get("id"),
            inventory=str(api_data.get("inventory", "")),
            credential=str(api_data.get("credential", "")),
            module_name=api_data.get("module_name", ""),
            module_args=api_data.get("module_args"),
            status=api_data.get("status"),
            job_type=api_data.get("job_type"),
            limit=api_data.get("limit"),
            forks=api_data.get("forks"),
            verbosity=api_data.get("verbosity"),
            become_enabled=api_data.get("become_enabled"),
            diff_mode=api_data.get("diff_mode"),
            finished=api_data.get("finished"),
            event_processing_finished=api_data.get("event_processing_finished"),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = [
            "module_name",
            "module_args",
            "inventory",
            "credential",
            "job_type",
            "limit",
            "forks",
            "verbosity",
            "extra_vars",
            "become_enabled",
            "diff_mode",
            "execution_environment",
        ]

        return {
            "create": EndpointOperation(
                path="/api/controller/v2/ad_hoc_commands/",
                method="POST",
                fields=fields,
                required_for="create",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/ad_hoc_commands/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "id"
