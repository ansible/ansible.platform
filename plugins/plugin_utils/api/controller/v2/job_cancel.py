"""
API v2 JobCancel dataclass and transform mixin.

JobCancel checks whether a job can be canceled and then POSTs to its
cancel endpoint. There is no standard CRUD lifecycle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIJobCancel_v2(BaseTransformMixin):
    """API v2 representation of a job cancel request."""

    job_id: Optional[int] = None
    fail_if_not_running: bool = False


class JobCancelTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for JobCancel API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIJobCancel_v2:
        return APIJobCancel_v2(
            job_id=getattr(ansible_instance, "job_id", None),
            fail_if_not_running=getattr(ansible_instance, "fail_if_not_running", False),
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
        """Cancel a running job via the controller API."""
        job_id = getattr(ansible_instance, "job_id", None)
        fail_if_not_running = getattr(ansible_instance, "fail_if_not_running", False)

        if not job_id:
            raise ValueError("job_id is required")

        job_url = context.manager._build_url(
            f"/api/controller/v2/jobs/{job_id}/",
            service="controller",
            api_version=context.api_version,
        )
        response = context.manager.session.get(
            job_url,
            timeout=context.manager.request_timeout,
            verify=context.manager.requests_verify,
        )
        if response.status_code == 404:
            raise ValueError(f"Unable to find job with id {job_id}")
        response.raise_for_status()

        cancel_url = context.manager._build_url(
            f"/api/controller/v2/jobs/{job_id}/cancel/",
            service="controller",
            api_version=context.api_version,
        )
        cancel_check = context.manager.session.get(
            cancel_url,
            timeout=context.manager.request_timeout,
            verify=context.manager.requests_verify,
        )
        cancel_check.raise_for_status()
        cancel_data = cancel_check.json()

        if not cancel_data.get("can_cancel", False):
            if fail_if_not_running:
                raise ValueError("Job is not running")
            return {"id": job_id, "changed": False}

        result = context.manager.session.post(
            cancel_url,
            json={},
            timeout=context.manager.request_timeout,
            verify=context.manager.requests_verify,
        )
        if result.status_code != 202:
            raise ValueError(
                f"Failed to cancel job {job_id}, got status {result.status_code}"
            )

        return {"id": job_id, "changed": True}

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.job_cancel import AnsibleJobCancel

        return AnsibleJobCancel()
