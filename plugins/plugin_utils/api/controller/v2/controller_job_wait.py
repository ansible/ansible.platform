"""
API v2 ControllerJobWait transform mixin.

Shape 3 (wait-only) resource — no CRUD operations. The actual wait logic
lives in the SDK layer (wait_for_resource). This mixin exists for registry
discovery and provides endpoint paths used by the action plugin.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIControllerJobWait_v2(BaseTransformMixin):
    """API v2 representation — read-only polling result."""

    id: Optional[int] = None
    status: Optional[str] = None
    elapsed: Optional[float] = None
    started: Optional[str] = None
    finished: Optional[str] = None


class ControllerJobWaitTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for ControllerJobWait API v2."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIControllerJobWait_v2":
        return APIControllerJobWait_v2(
            id=getattr(ansible_instance, "id", None),
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
        return "job_id"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleControllerJobWait":
        from ....ansible_models.controller_job_wait import AnsibleControllerJobWait

        return AnsibleControllerJobWait(
            id=api_data.get("id"),
            status=api_data.get("status"),
            elapsed=api_data.get("elapsed"),
            started=api_data.get("started"),
            finished=api_data.get("finished"),
        )
