"""
API v2 Workflow Approval dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format
for workflow approval operations (approve/deny).

This is a non-CRUD module: it does not manage a persistent resource via
standard create/update/delete operations. Instead, it polls for an approval
node in a workflow job and POSTs to approve or deny it. The transform mixin
declares the read and action endpoints used by the action plugin.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

WORKFLOW_APPROVALS_ENDPOINT = "/api/controller/v2/workflow_approvals/"
WORKFLOW_JOB_NODES_ENDPOINT = "/api/controller/v2/workflow_jobs/{workflow_job_id}/workflow_nodes/"
WORKFLOW_APPROVAL_APPROVE_ENDPOINT = "/api/controller/v2/workflow_approvals/{id}/approve/"
WORKFLOW_APPROVAL_DENY_ENDPOINT = "/api/controller/v2/workflow_approvals/{id}/deny/"


@dataclass
class APIWorkflowApproval_v2(BaseTransformMixin):
    """
    API v2 representation of a workflow approval action.
    """

    workflow_job_id: Optional[int] = None
    name: Optional[str] = None
    action: Optional[str] = None
    interval: Optional[float] = None
    timeout: Optional[int] = None

    # Read-only fields from API
    id: Optional[int] = None


class WorkflowApprovalTransformMixin_v2(BaseTransformMixin):
    """
    Transform mixin for Workflow Approval API v2.

    Endpoint definitions and query construction are shared with the custom
    action plugin, which owns polling and approval orchestration.
    """

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIWorkflowApproval_v2":
        """Create API instance from Ansible dataclass."""
        return APIWorkflowApproval_v2(
            workflow_job_id=getattr(ansible_instance, "workflow_job_id", None),
            name=getattr(ansible_instance, "name", None),
            action=getattr(ansible_instance, "action", None),
            interval=getattr(ansible_instance, "interval", None),
            timeout=getattr(ansible_instance, "timeout", None),
            id=getattr(ansible_instance, "id", None),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for workflow approval operations.

        Workflow approval is non-CRUD: the action plugin uses search_api()
        and direct_request() directly. These endpoints are placeholders for
        registry compatibility.
        """
        return {
            "list": EndpointOperation(
                path=WORKFLOW_APPROVALS_ENDPOINT,
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
            "get": EndpointOperation(
                path=WORKFLOW_APPROVALS_ENDPOINT + "{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "workflow_nodes": EndpointOperation(
                path=WORKFLOW_JOB_NODES_ENDPOINT,
                method="GET",
                fields=[],
                path_params=["workflow_job_id"],
                required_for="wait",
                order=1,
            ),
            "approve": EndpointOperation(
                path=WORKFLOW_APPROVAL_APPROVE_ENDPOINT,
                method="POST",
                fields=[],
                path_params=["id"],
                required_for="approve",
                order=1,
            ),
            "deny": EndpointOperation(
                path=WORKFLOW_APPROVAL_DENY_ENDPOINT,
                method="POST",
                fields=[],
                path_params=["id"],
                required_for="deny",
                order=1,
            ),
        }

    @classmethod
    def get_workflow_node_query_params(cls, name: str) -> Dict[str, Any]:
        """Build the workflow-node filter used to find a named approval job."""
        return {"job__name": name}

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleWorkflowApproval":
        """Transform from API format to Ansible format."""
        from ....ansible_models.workflow_approval import (
            AnsibleWorkflowApproval,
        )

        return AnsibleWorkflowApproval(
            workflow_job_id=api_data.get("workflow_job_id", 0),
            name=api_data.get("name", ""),
            action=api_data.get("action", "approve"),
            id=api_data.get("id"),
        )
