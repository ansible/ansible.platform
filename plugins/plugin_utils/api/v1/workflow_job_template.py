"""
API v1 WorkflowJobTemplate dataclass and transform mixin.

Handles transformations between Ansible format and the Controller API format
for workflow_job_template resources.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...ansible_models.workflow_job_template import AnsibleWorkflowJobTemplate
from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

_NAME_LOOKUP_FIELDS = (
    ("organization", "/api/controller/v2/organizations/"),
    ("inventory", "/api/controller/v2/inventories/"),
    ("webhook_credential", "/api/controller/v2/credentials/"),
)

_DIRECT_FIELDS = (
    "description",
    "job_tags",
    "skip_tags",
    "ask_tags_on_launch",
    "allow_simultaneous",
    "ask_variables_on_launch",
    "limit",
    "scm_branch",
    "ask_inventory_on_launch",
    "ask_scm_branch_on_launch",
    "ask_limit_on_launch",
    "ask_labels_on_launch",
    "ask_skip_tags_on_launch",
    "webhook_service",
    "survey_enabled",
)


@dataclass
class APIWorkflowJobTemplate_v1:
    """Wire format for Controller workflow_job_templates."""

    name: str
    description: Optional[str] = None
    extra_vars: Optional[str] = None
    job_tags: Optional[str] = None
    skip_tags: Optional[str] = None
    ask_tags_on_launch: Optional[bool] = None
    organization: Optional[int] = None
    allow_simultaneous: Optional[bool] = None
    ask_variables_on_launch: Optional[bool] = None
    inventory: Optional[int] = None
    limit: Optional[str] = None
    scm_branch: Optional[str] = None
    ask_inventory_on_launch: Optional[bool] = None
    ask_scm_branch_on_launch: Optional[bool] = None
    ask_limit_on_launch: Optional[bool] = None
    ask_labels_on_launch: Optional[bool] = None
    ask_skip_tags_on_launch: Optional[bool] = None
    webhook_service: Optional[str] = None
    webhook_credential: Optional[int] = None
    survey_enabled: Optional[bool] = None
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class WorkflowJobTemplateTransformMixin_v1(BaseTransformMixin):
    """Transforms between AnsibleWorkflowJobTemplate and APIWorkflowJobTemplate_v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance: AnsibleWorkflowJobTemplate, context: TransformContext) -> APIWorkflowJobTemplate_v1:
        """Forward: Ansible model -> API wire format."""
        params: Dict[str, Any] = {
            "name": ansible_instance.new_name or ansible_instance.name,
        }

        for field, endpoint in _NAME_LOOKUP_FIELDS:
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = context.manager.lookup_resource_id(endpoint, "name", value)

        for field in _DIRECT_FIELDS:
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = value

        if ansible_instance.extra_vars is not None:
            if isinstance(ansible_instance.extra_vars, dict):
                params["extra_vars"] = json.dumps(ansible_instance.extra_vars)
            else:
                params["extra_vars"] = str(ansible_instance.extra_vars)

        # Read-only from API (for building the {id} URL path param in execute)
        for field in ("id", "created", "modified", "url"):
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = value

        return APIWorkflowJobTemplate_v1(**params)

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: TransformContext) -> AnsibleWorkflowJobTemplate:
        """Reverse: API response -> Ansible model."""

        def _str_or_none(val: Any) -> Optional[str]:
            return str(val) if val is not None else None

        raw_vars = api_data.get("extra_vars")
        extra_vars: Optional[dict] = None
        if isinstance(raw_vars, dict):
            extra_vars = raw_vars
        elif isinstance(raw_vars, str) and raw_vars.strip():
            try:
                extra_vars = json.loads(raw_vars)
            except ValueError:
                extra_vars = None

        return AnsibleWorkflowJobTemplate(
            id=api_data.get("id"),
            name=api_data.get("name", ""),
            description=api_data.get("description"),
            extra_vars=extra_vars,
            job_tags=api_data.get("job_tags"),
            skip_tags=api_data.get("skip_tags"),
            ask_tags_on_launch=api_data.get("ask_tags_on_launch"),
            organization=_str_or_none(api_data.get("organization")),
            allow_simultaneous=api_data.get("allow_simultaneous"),
            ask_variables_on_launch=api_data.get("ask_variables_on_launch"),
            inventory=_str_or_none(api_data.get("inventory")),
            limit=api_data.get("limit"),
            scm_branch=api_data.get("scm_branch"),
            ask_inventory_on_launch=api_data.get("ask_inventory_on_launch"),
            ask_scm_branch_on_launch=api_data.get("ask_scm_branch_on_launch"),
            ask_limit_on_launch=api_data.get("ask_limit_on_launch"),
            ask_labels_on_launch=api_data.get("ask_labels_on_launch"),
            ask_skip_tags_on_launch=api_data.get("ask_skip_tags_on_launch"),
            webhook_service=api_data.get("webhook_service"),
            webhook_credential=_str_or_none(api_data.get("webhook_credential")),
            survey_enabled=api_data.get("survey_enabled"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = [
            "name",
            "description",
            "extra_vars",
            "job_tags",
            "skip_tags",
            "ask_tags_on_launch",
            "organization",
            "allow_simultaneous",
            "ask_variables_on_launch",
            "inventory",
            "limit",
            "scm_branch",
            "ask_inventory_on_launch",
            "ask_scm_branch_on_launch",
            "ask_limit_on_launch",
            "ask_labels_on_launch",
            "ask_skip_tags_on_launch",
            "webhook_service",
            "webhook_credential",
            "survey_enabled",
        ]

        return {
            "create": EndpointOperation(
                path="/api/controller/v2/workflow_job_templates/",
                method="POST",
                fields=fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/workflow_job_templates/{id}/",
                method="PATCH",
                fields=fields,
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
    def get_find_list_query_params(cls, ansible_data: APIWorkflowJobTemplate_v1) -> Dict[str, Any]:
        """Scope name lookups by organization — workflow_job_template names are only unique per-org."""
        org_id = getattr(ansible_data, "organization", None)
        if org_id is not None:
            return {"organization": org_id}
        return {}
