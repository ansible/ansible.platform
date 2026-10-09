"""
API v2 JobWait dataclass and transform mixin.

JobWait polls a controller job until it reaches a terminal state.
There is no standard CRUD lifecycle.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = frozenset({"successful", "failed", "error", "canceled"})


@dataclass
class APIJobWait_v2(BaseTransformMixin):
    """API v2 representation of a job wait query."""

    job_id: Optional[int] = None
    job_type: Optional[str] = None


class JobWaitTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for JobWait API v2.

    Polls a job endpoint until it reaches a terminal status.
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
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
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
        return ""

    @classmethod
    def resolve(cls, ansible_instance, context: TransformContext) -> dict:
        """Poll a job until it reaches a terminal state."""
        job_id = getattr(ansible_instance, "job_id", None)
        job_type = getattr(ansible_instance, "job_type", "jobs")
        interval = getattr(ansible_instance, "interval", 2)
        timeout = getattr(ansible_instance, "timeout", None)

        if not job_id:
            raise ValueError("job_id is required")

        url = context.manager._build_url(
            f"/api/controller/v2/{job_type}/{job_id}/",
            service="controller",
            api_version=context.api_version,
        )

        start_time = time.monotonic()

        while True:
            response = context.manager.session.get(
                url,
                timeout=context.manager.request_timeout,
                verify=context.manager.requests_verify,
            )
            if response.status_code == 404:
                raise ValueError(
                    f"Unable to wait on {job_type.rstrip('s')} {job_id}; that ID does not exist."
                )
            response.raise_for_status()
            job_data = response.json()

            status = job_data.get("status", "")
            if status in TERMINAL_STATUSES:
                result = {
                    "id": job_data.get("id", job_id),
                    "status": status,
                    "elapsed": job_data.get("elapsed"),
                    "started": job_data.get("started"),
                    "finished": job_data.get("finished"),
                    "changed": False,
                    "failed": status in ("failed", "error"),
                }
                if result["failed"]:
                    result["msg"] = f"Job {job_id} finished with status: {status}"
                return result

            elapsed = time.monotonic() - start_time
            if timeout and elapsed >= timeout:
                raise ValueError(
                    f"Timed out waiting for job {job_id} after {timeout}s (current status: {status})"
                )

            time.sleep(interval)

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.job_wait import AnsibleJobWait

        return AnsibleJobWait()
