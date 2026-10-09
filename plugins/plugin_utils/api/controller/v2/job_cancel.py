"""API v2 JobCancel dataclass and transform mixin.

job_cancel is a non-CRUD action module. It POSTs to the controller
jobs/{id}/cancel/ sub-endpoint to cancel a running job.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext


@dataclass
class APIJobCancel_v2:
    """API v2 representation of a job cancel request."""

    id: Optional[int] = None


class JobCancelTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for JobCancel API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIJobCancel_v2:
        return APIJobCancel_v2(id=getattr(ansible_instance, "job_id", None))

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/jobs/{id}/cancel/",
                method="POST",
                fields=["id"],
                path_params=["id"],
                required_for="create",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/jobs/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/jobs/",
                method="GET",
                fields=[],
                required_for="find",
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
        from ....ansible_models.job_cancel import AnsibleJobCancel

        return AnsibleJobCancel(
            job_id=api_data.get("id"),
            id=api_data.get("id"),
        )
