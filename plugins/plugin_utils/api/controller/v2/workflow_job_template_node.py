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


@dataclass
class APIWorkflowJobTemplateNode_v2(BaseTransformMixin):
    """API v2 representation of a Controller workflow job template node."""

    identifier: Optional[str] = None
    workflow_job_template: Optional[int] = None
    unified_job_template: Optional[int] = None
    all_parents_must_converge: Optional[bool] = None

    # Read-only fields from API
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

        # Simple fields
        all_converge = getattr(ansible_instance, "all_parents_must_converge", None)
        if all_converge is not None:
            api_data["all_parents_must_converge"] = all_converge

        # Read-only from API (for building URL in execute)
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
                fields=["identifier", "workflow_job_template", "unified_job_template", "all_parents_must_converge"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/workflow_job_template_nodes/{id}/",
                method="PATCH",
                fields=["identifier", "workflow_job_template", "unified_job_template", "all_parents_must_converge"],
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

        return AnsibleWorkflowJobTemplateNode(
            identifier=api_data.get("identifier", ""),
            workflow_job_template=wfjt_str,
            unified_job_template=ujt_str,
            all_parents_must_converge=api_data.get("all_parents_must_converge"),
            id=api_data.get("id"),
        )
