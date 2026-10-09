"""
API v2 WorkflowApproval dataclass and transform mixin.

Workflow approvals are non-CRUD: the action plugin polls for a pending
approval node in a workflow job, then POSTs to its approve or deny
sub-endpoint.  The 'create' operation maps to approve; the 'delete'
operation maps to deny.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext


@dataclass
class APIWorkflowApproval_v2(BaseTransformMixin):
    """API v2 representation of a workflow approval action."""

    id: Optional[int] = None


class WorkflowApprovalTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for Workflow Approval API v2.

    This mixin maps:
    - create -> POST /api/controller/v2/workflow_approvals/{id}/approve/
    - delete -> POST /api/controller/v2/workflow_approvals/{id}/deny/

    Both endpoints accept an empty body and return 204 No Content.
    """

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIWorkflowApproval_v2:
        api_data = APIWorkflowApproval_v2()
        approval_id = getattr(ansible_instance, "id", None)
        if approval_id is not None:
            api_data.id = approval_id
        return api_data

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/workflow_approvals/{id}/approve/",
                method="POST",
                fields=[],
                path_params=["id"],
                required_for="create",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/workflow_approvals/{id}/deny/",
                method="POST",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "id"

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.workflow_approval import AnsibleWorkflowApproval

        return AnsibleWorkflowApproval(
            id=api_data.get("id"),
        )
