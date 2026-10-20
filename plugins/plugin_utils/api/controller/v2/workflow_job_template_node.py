"""
API v2 WorkflowJobTemplateNode dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

BASE_PATH = "/api/controller/v2/workflow_job_template_nodes"


@dataclass
class APIWorkflowJobTemplateNode_v2(BaseTransformMixin):
    """API v2 representation of a Controller workflow job template node."""

    identifier: Optional[str] = None
    workflow_job_template: Optional[int] = None
    unified_job_template: Optional[int] = None
    all_parents_must_converge: Optional[bool] = None
    extra_data: Optional[str] = None
    inventory: Optional[int] = None
    scm_branch: Optional[str] = None
    job_type: Optional[str] = None
    job_tags: Optional[str] = None
    skip_tags: Optional[str] = None
    limit: Optional[str] = None
    diff_mode: Optional[bool] = None
    verbosity: Optional[int] = None
    forks: Optional[int] = None
    job_slice_count: Optional[int] = None
    timeout: Optional[int] = None
    execution_environment: Optional[int] = None
    id: Optional[int] = None


class WorkflowJobTemplateNodeTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for WorkflowJobTemplateNode API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APIWorkflowJobTemplateNode_v2":
        api_data: Dict[str, Any] = {}

        # identifier is the lookup field
        identifier = getattr(ansible_instance, "identifier", None)
        if identifier is not None:
            api_data["identifier"] = identifier

        # FK resolution: workflow_job_template name → ID
        wfjt = getattr(ansible_instance, "workflow_job_template", None)
        if wfjt is not None:
            manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
            if manager is not None and not str(wfjt).strip().isdigit():
                api_data["workflow_job_template"] = manager.lookup_resource_id("workflow_job_templates", "name", wfjt, service="controller")
            else:
                api_data["workflow_job_template"] = int(wfjt) if wfjt is not None else None

        # FK resolution: unified_job_template name → ID
        ujt = getattr(ansible_instance, "unified_job_template", None)
        if ujt is not None:
            manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
            if manager is not None and not str(ujt).strip().isdigit():
                api_data["unified_job_template"] = manager.lookup_resource_id("unified_job_templates", "name", ujt, service="controller")
            else:
                api_data["unified_job_template"] = int(ujt) if ujt is not None else None

        _SCALAR_FIELDS = (
            "all_parents_must_converge", "scm_branch", "job_type", "job_tags",
            "skip_tags", "limit", "diff_mode", "verbosity", "forks", "job_slice_count", "timeout",
        )
        for field in _SCALAR_FIELDS:
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        extra_data = getattr(ansible_instance, "extra_data", None)
        if extra_data is not None:
            import json

            api_data["extra_data"] = json.dumps(extra_data) if isinstance(extra_data, dict) else extra_data

        inventory = getattr(ansible_instance, "inventory", None)
        if inventory is not None:
            if manager is not None and not str(inventory).strip().isdigit():
                api_data["inventory"] = manager.lookup_resource_id("inventories", "name", inventory, service="controller")
            else:
                api_data["inventory"] = int(inventory)

        execution_environment = getattr(ansible_instance, "execution_environment", None)
        if execution_environment is not None:
            if manager is not None and not str(execution_environment).strip().isdigit():
                api_data["execution_environment"] = manager.lookup_resource_id(
                    "execution_environments", "name", execution_environment, service="controller"
                )
            else:
                api_data["execution_environment"] = int(execution_environment)

        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIWorkflowJobTemplateNode_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/workflow_job_template_nodes/",
                method="POST",
                fields=[
                    "identifier", "workflow_job_template", "unified_job_template",
                    "all_parents_must_converge", "extra_data", "inventory", "scm_branch",
                    "job_type", "job_tags", "skip_tags", "limit", "diff_mode", "verbosity",
                    "forks", "job_slice_count", "timeout", "execution_environment",
                ],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/workflow_job_template_nodes/{id}/",
                method="PATCH",
                fields=[
                    "identifier", "workflow_job_template", "unified_job_template",
                    "all_parents_must_converge", "extra_data", "inventory", "scm_branch",
                    "job_type", "job_tags", "skip_tags", "limit", "diff_mode", "verbosity",
                    "forks", "job_slice_count", "timeout", "execution_environment",
                ],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/workflow_job_template_nodes/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/workflow_job_template_nodes/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/workflow_job_template_nodes/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "identifier"

    @classmethod
    def get_find_list_query_params(cls, ansible_data) -> Dict[str, Any]:
        """Scope node lookups to the workflow when it is provided."""
        workflow_job_template = getattr(ansible_data, "workflow_job_template", None)
        if workflow_job_template is not None:
            return {"workflow_job_template": workflow_job_template}
        return {}

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.workflow_job_template_node import AnsibleWorkflowJobTemplateNode

        wfjt_val = api_data.get("workflow_job_template")
        wfjt_str = str(wfjt_val) if wfjt_val is not None else ""

        ujt_val = api_data.get("unified_job_template")
        ujt_str = str(ujt_val) if ujt_val is not None else None

        extra_data = api_data.get("extra_data")
        if isinstance(extra_data, str) and extra_data.strip():
            import json as _json

            try:
                extra_data = _json.loads(extra_data)
            except ValueError:
                extra_data = None
        elif not isinstance(extra_data, dict):
            extra_data = None

        inv_val = api_data.get("inventory")
        ee_val = api_data.get("execution_environment")

        return AnsibleWorkflowJobTemplateNode(
            identifier=api_data.get("identifier", ""),
            workflow_job_template=wfjt_str,
            unified_job_template=ujt_str,
            all_parents_must_converge=api_data.get("all_parents_must_converge"),
            extra_data=extra_data if extra_data else None,
            inventory=str(inv_val) if inv_val is not None else None,
            scm_branch=api_data.get("scm_branch") or None,
            job_type=api_data.get("job_type") or None,
            job_tags=api_data.get("job_tags") or None,
            skip_tags=api_data.get("skip_tags") or None,
            limit=api_data.get("limit") or None,
            diff_mode=api_data.get("diff_mode"),
            verbosity=api_data.get("verbosity"),
            forks=api_data.get("forks"),
            job_slice_count=api_data.get("job_slice_count"),
            timeout=api_data.get("timeout"),
            execution_environment=str(ee_val) if ee_val is not None else None,
            id=api_data.get("id"),
        )
