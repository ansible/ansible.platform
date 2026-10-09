"""
API v2 WorkflowApproval dataclass and transform mixin.

WorkflowApproval polls workflow job nodes until the named approval node
appears, then POSTs approve or deny. There is no standard CRUD lifecycle.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIWorkflowApproval_v2(BaseTransformMixin):
    """API v2 representation of a workflow approval request."""

    workflow_job_id: Optional[int] = None
    name: Optional[str] = None
    action: str = "approve"


class WorkflowApprovalTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for WorkflowApproval API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIWorkflowApproval_v2:
        return APIWorkflowApproval_v2(
            workflow_job_id=getattr(ansible_instance, "workflow_job_id", None),
            name=getattr(ansible_instance, "name", None),
            action=getattr(ansible_instance, "action", "approve"),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "list_nodes": EndpointOperation(
                path="/api/controller/v2/workflow_jobs/{id}/workflow_nodes/",
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
    def resolve(cls, ansible_instance, context: TransformContext) -> dict:
        """Wait for an approval node and approve or deny it."""
        workflow_job_id = getattr(ansible_instance, "workflow_job_id", None)
        name = getattr(ansible_instance, "name", None)
        action = getattr(ansible_instance, "action", "approve")
        interval = getattr(ansible_instance, "interval", 1)
        timeout = getattr(ansible_instance, "timeout", 10)

        if not workflow_job_id:
            raise ValueError("workflow_job_id is required")
        if not name:
            raise ValueError("name is required")

        nodes_url = context.manager._build_url(
            f"/api/controller/v2/workflow_jobs/{workflow_job_id}/workflow_nodes/",
            service="controller",
            api_version=context.api_version,
        )

        start_time = time.monotonic()
        approval_job = None

        while True:
            response = context.manager.session.get(
                nodes_url,
                params={"job__name": name},
                timeout=context.manager.request_timeout,
                verify=context.manager.requests_verify,
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            for node in results:
                summary = node.get("summary_fields", {})
                job_info = summary.get("job", {})
                if job_info.get("name") == name and job_info.get("type") == "workflow_approval":
                    if job_info.get("status") == "pending":
                        approval_job = node
                        break

            if approval_job:
                break

            elapsed = time.monotonic() - start_time
            if elapsed >= timeout:
                raise ValueError(
                    f"Timed out waiting for approval node '{name}' in workflow job {workflow_job_id} "
                    f"after {timeout}s"
                )

            time.sleep(interval)

        job_detail = approval_job.get("summary_fields", {}).get("job", {})
        job_url = f"/api/controller/v2/workflow_approvals/{job_detail['id']}/{action}/"
        action_url = context.manager._build_url(
            job_url,
            service="controller",
            api_version=context.api_version,
        )

        result = context.manager.session.post(
            action_url,
            json={},
            timeout=context.manager.request_timeout,
            verify=context.manager.requests_verify,
        )

        if result.status_code == 204:
            return {"changed": True}

        raise ValueError(
            f"Failed to {action} approval node '{name}' (status {result.status_code})"
        )

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.workflow_approval import AnsibleWorkflowApproval

        return AnsibleWorkflowApproval()
