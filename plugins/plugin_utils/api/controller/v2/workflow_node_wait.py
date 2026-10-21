# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Transform mixin and endpoint constants for workflow_node_wait."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from dataclasses import dataclass
from typing import Any, Dict, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

WORKFLOW_NODES_LIST_ENDPOINT = "/api/controller/v2/workflow_jobs/{workflow_job_id}/workflow_nodes/"


@dataclass
class APIWorkflowNodeWait_v2(BaseTransformMixin):
    """API v2 representation of a workflow node wait request."""

    workflow_job_id: int = 0
    name: str = ""


class WorkflowNodeWaitTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for WorkflowNodeWait API v2."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIWorkflowNodeWait_v2":
        """Create API instance from Ansible dataclass."""
        return APIWorkflowNodeWait_v2(
            workflow_job_id=getattr(ansible_instance, "workflow_job_id", 0),
            name=getattr(ansible_instance, "name", ""),
        )

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleWorkflowNodeWait":
        """Transform from API format to Ansible format."""
        from ....ansible_models.workflow_node_wait import AnsibleWorkflowNodeWait

        return AnsibleWorkflowNodeWait(
            workflow_job_id=api_data.get("workflow_job_id", 0),
            name=api_data.get("name", ""),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoint for workflow node wait."""
        return {
            "find": EndpointOperation(
                path=WORKFLOW_NODES_LIST_ENDPOINT,
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "workflow_job_id"
