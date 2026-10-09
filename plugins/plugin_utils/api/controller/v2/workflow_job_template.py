"""
API v2 WorkflowJobTemplate dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIWorkflowJobTemplate_v2(BaseTransformMixin):
    """API v2 representation of a Controller workflow job template."""

    name: Optional[str] = None
    description: Optional[str] = None
    organization: Optional[int] = None
    extra_vars: Optional[str] = None
    survey_enabled: Optional[bool] = None
    allow_simultaneous: Optional[bool] = None
    ask_variables_on_launch: Optional[bool] = None
    ask_inventory_on_launch: Optional[bool] = None
    ask_scm_branch_on_launch: Optional[bool] = None
    ask_limit_on_launch: Optional[bool] = None
    ask_labels_on_launch: Optional[bool] = None
    ask_tags_on_launch: Optional[bool] = None
    ask_skip_tags_on_launch: Optional[bool] = None
    inventory: Optional[int] = None
    limit: Optional[str] = None
    scm_branch: Optional[str] = None
    job_tags: Optional[str] = None
    skip_tags: Optional[str] = None
    webhook_service: Optional[str] = None
    webhook_credential: Optional[int] = None

    # Read-only fields from API
    id: Optional[int] = None


class WorkflowJobTemplateTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for WorkflowJobTemplate API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APIWorkflowJobTemplate_v2":
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

        # FK resolution: inventory (Controller-owned)
        inventory = getattr(ansible_instance, "inventory", None)
        if inventory is not None:
            if manager is not None and not str(inventory).strip().isdigit():
                api_data["inventory"] = manager.lookup_resource_id("inventories", "name", inventory, service="controller")
            else:
                api_data["inventory"] = int(inventory) if inventory is not None else None

        # FK resolution: webhook_credential (Controller-owned)
        webhook_credential = getattr(ansible_instance, "webhook_credential", None)
        if webhook_credential is not None:
            if manager is not None and not str(webhook_credential).strip().isdigit():
                api_data["webhook_credential"] = manager.lookup_resource_id("credentials", "name", webhook_credential, service="controller")
            else:
                api_data["webhook_credential"] = int(webhook_credential) if webhook_credential is not None else None

        # Scalar fields
        for field in (
            "description",
            "survey_enabled",
            "allow_simultaneous",
            "ask_variables_on_launch",
            "ask_inventory_on_launch",
            "ask_scm_branch_on_launch",
            "ask_limit_on_launch",
            "ask_labels_on_launch",
            "ask_tags_on_launch",
            "ask_skip_tags_on_launch",
            "limit",
            "scm_branch",
            "job_tags",
            "skip_tags",
            "webhook_service",
        ):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
            elif op == "update" and include_nulls and field == "description":
                api_data[field] = ""

        # extra_vars: already normalized to JSON string by __post_init__
        extra_vars = getattr(ansible_instance, "extra_vars", None)
        if extra_vars is not None:
            api_data["extra_vars"] = json.dumps(extra_vars) if isinstance(extra_vars, dict) else extra_vars

        # Read-only from API (for building URL in execute)
        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIWorkflowJobTemplate_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/workflow_job_templates/",
                method="POST",
                fields=[
                    "name",
                    "description",
                    "organization",
                    "extra_vars",
                    "survey_enabled",
                    "allow_simultaneous",
                    "ask_variables_on_launch",
                    "ask_inventory_on_launch",
                    "ask_scm_branch_on_launch",
                    "ask_limit_on_launch",
                    "ask_labels_on_launch",
                    "ask_tags_on_launch",
                    "ask_skip_tags_on_launch",
                    "inventory",
                    "limit",
                    "scm_branch",
                    "job_tags",
                    "skip_tags",
                    "webhook_service",
                    "webhook_credential",
                ],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/workflow_job_templates/{id}/",
                method="PATCH",
                fields=[
                    "name",
                    "description",
                    "organization",
                    "extra_vars",
                    "survey_enabled",
                    "allow_simultaneous",
                    "ask_variables_on_launch",
                    "ask_inventory_on_launch",
                    "ask_scm_branch_on_launch",
                    "ask_limit_on_launch",
                    "ask_labels_on_launch",
                    "ask_tags_on_launch",
                    "ask_skip_tags_on_launch",
                    "inventory",
                    "limit",
                    "scm_branch",
                    "job_tags",
                    "skip_tags",
                    "webhook_service",
                    "webhook_credential",
                ],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/workflow_job_templates/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/workflow_job_templates/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/workflow_job_templates/",
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
        from ....ansible_models.workflow_job_template import AnsibleWorkflowJobTemplate

        organization_val = api_data.get("organization")
        organization_str = str(organization_val) if organization_val is not None else None

        inventory_val = api_data.get("inventory")
        inventory_str = str(inventory_val) if inventory_val is not None else None

        webhook_credential_val = api_data.get("webhook_credential")
        webhook_credential_str = str(webhook_credential_val) if webhook_credential_val is not None else None

        return AnsibleWorkflowJobTemplate(
            name=api_data.get("name", ""),
            description=api_data.get("description"),
            organization=organization_str,
            extra_vars=api_data.get("extra_vars"),
            survey_enabled=api_data.get("survey_enabled"),
            allow_simultaneous=api_data.get("allow_simultaneous"),
            ask_variables_on_launch=api_data.get("ask_variables_on_launch"),
            ask_inventory_on_launch=api_data.get("ask_inventory_on_launch"),
            ask_scm_branch_on_launch=api_data.get("ask_scm_branch_on_launch"),
            ask_limit_on_launch=api_data.get("ask_limit_on_launch"),
            ask_labels_on_launch=api_data.get("ask_labels_on_launch"),
            ask_tags_on_launch=api_data.get("ask_tags_on_launch"),
            ask_skip_tags_on_launch=api_data.get("ask_skip_tags_on_launch"),
            inventory=inventory_str,
            limit=api_data.get("limit"),
            scm_branch=api_data.get("scm_branch"),
            job_tags=api_data.get("job_tags"),
            skip_tags=api_data.get("skip_tags"),
            webhook_service=api_data.get("webhook_service"),
            webhook_credential=webhook_credential_str,
            id=api_data.get("id"),
        )
