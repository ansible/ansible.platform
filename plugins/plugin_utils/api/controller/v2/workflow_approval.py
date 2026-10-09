"""
API v2 Workflow Approval dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format
for workflow approval operations (approve/deny).

This is a non-CRUD module: it does not manage a persistent resource via
standard create/update/delete operations. Instead, it polls for an approval
node in a workflow job and POSTs to approve or deny it. The transform mixin
exists primarily for registry discovery.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


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

    This is a non-CRUD module. The transform mixin provides minimal
    endpoint definitions for registry discovery. The actual workflow
    approval logic is implemented in the custom action plugin.
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
                path="/api/controller/v2/workflow_approvals/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/workflow_approvals/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
        }

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
