"""
API v2 WorkflowLaunch dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format.
This is a minimal mixin for the launch operation (Shape 2) -- the actual
launch logic lives in the SDK's launch_resource() / wait_for_completion()
methods, not in the standard CRUD execute() pipeline.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

WJT_LIST_ENDPOINT = "/api/controller/v2/workflow_job_templates/"
WORKFLOW_JOBS_ENDPOINT = "/api/controller/v2/workflow_jobs/"


@dataclass
class APIWorkflowLaunch_v2(BaseTransformMixin):
    """API v2 representation of a workflow launch request."""

    name: Optional[str] = None
    organization: Optional[int] = None
    inventory: Optional[int] = None
    limit: Optional[str] = None
    job_tags: Optional[str] = None
    skip_tags: Optional[str] = None
    scm_branch: Optional[str] = None
    extra_vars: Optional[Dict] = None
    id: Optional[int] = None


class WorkflowLaunchTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for WorkflowLaunch API v2.

    This is a minimal mixin -- launch operations bypass the standard
    CRUD endpoint operations and use launch_resource() directly.
    """

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIWorkflowLaunch_v2":
        """Create API instance from Ansible dataclass."""
        return APIWorkflowLaunch_v2(
            name=getattr(ansible_instance, "name", None),
            id=getattr(ansible_instance, "id", None),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for workflow launch operations.

        Launch uses POST to /launch/ sub-endpoint rather than standard CRUD.
        The list endpoint is used only for finding/validating the WJT exists.
        """
        return {
            "list": EndpointOperation(
                path="/api/controller/v2/workflow_job_templates/",
                method="GET",
                fields=[],
                required_for="find",
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
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]):
        """Transform from API format to Ansible format."""
        from ....ansible_models.workflow_launch import AnsibleWorkflowLaunch

        return AnsibleWorkflowLaunch(
            name=api_data.get("name", ""),
            id=api_data.get("id"),
        )
