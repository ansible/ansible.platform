"""
API v1 JobWait dataclass and transform mixin.

Handles transformations between Ansible format and the Controller API format
for waiting on an existing job/update to finish.

job_type selects which Controller resource collection to poll — 'jobs',
'inventory_updates', 'project_updates', or 'workflow_jobs' — so the GET path
is templated with {job_type} as well as {id}. Both the "create" operation
(the initial check) and "get" operation (subsequent polls, driven by
_wait_for_resource_completion) point at the same GET path; there is nothing
to actually create, this module only ever reads.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...ansible_models.job_wait import AnsibleJobWait
from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIJobWait_v1:
    """Wire format for polling a Controller job/update by id."""

    job_type: str
    id: Optional[int] = None
    status: Optional[str] = None
    started: Optional[str] = None
    finished: Optional[str] = None
    elapsed: Optional[float] = None


class JobWaitTransformMixin_v1(BaseTransformMixin):
    """Transforms between AnsibleJobWait and APIJobWait_v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance: AnsibleJobWait, context: TransformContext) -> APIJobWait_v1:
        """Forward: Ansible model -> API wire format.

        ``ansible_instance.id`` is set by _wait_for_resource_completion's
        replace() on the second and subsequent polls; on the very first call
        it is None and job_id (the user-supplied id to wait on) is used instead.
        """
        resolved_id = ansible_instance.id if ansible_instance.id is not None else ansible_instance.job_id
        return APIJobWait_v1(job_type=ansible_instance.job_type, id=resolved_id)

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: TransformContext) -> AnsibleJobWait:
        """Reverse: API response -> Ansible model."""
        return AnsibleJobWait(
            job_id=api_data.get("id"),
            id=api_data.get("id"),
            status=api_data.get("status"),
            started=api_data.get("started"),
            finished=api_data.get("finished"),
            elapsed=api_data.get("elapsed"),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        path = "/api/controller/v2/{job_type}/{id}/"
        return {
            "create": EndpointOperation(
                path=path,
                method="GET",
                fields=[],
                path_params=["job_type", "id"],
                required_for="create",
                order=1,
            ),
            "get": EndpointOperation(
                path=path,
                method="GET",
                fields=[],
                path_params=["job_type", "id"],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "id"
