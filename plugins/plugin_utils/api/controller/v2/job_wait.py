"""
API v2 JobWait dataclass and transform mixin.

job_wait is a non-CRUD module. It polls a job endpoint until
the job finishes. The transform mixin is minimal and exists
primarily so the registry auto-discovers it as a controller module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext


@dataclass
class APIJobWait_v2(BaseTransformMixin):
    """API v2 representation of a job wait operation."""

    job_id: Optional[int] = None
    job_type: str = "jobs"
    interval: Optional[float] = 2
    timeout: Optional[int] = None

    # Read-only
    id: Optional[int] = None
    status: Optional[str] = None
    elapsed: Optional[float] = None
    started: Optional[str] = None
    finished: Optional[str] = None


class JobWaitTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for JobWait API v2.

    This is a non-CRUD module so the transform mixin is minimal.
    The action plugin handles all logic via search_api() directly.
    """

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIJobWait_v2:
        return APIJobWait_v2(
            job_id=getattr(ansible_instance, "job_id", None),
            job_type=getattr(ansible_instance, "job_type", "jobs"),
            interval=getattr(ansible_instance, "interval", 2),
            timeout=getattr(ansible_instance, "timeout", None),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Endpoint operations (minimal for non-CRUD module)."""
        return {
            "get": EndpointOperation(
                path="/api/controller/v2/jobs/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "job_id"

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.job_wait import AnsibleJobWait

        return AnsibleJobWait(
            job_id=api_data.get("id"),
            id=api_data.get("id"),
            status=api_data.get("status"),
            elapsed=api_data.get("elapsed"),
            started=api_data.get("started"),
            finished=api_data.get("finished"),
        )
