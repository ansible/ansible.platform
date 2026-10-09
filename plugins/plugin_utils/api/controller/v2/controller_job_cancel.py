"""
API v2 ControllerJobCancel dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format.
This is a minimal mixin for the cancel operation (Shape 4) -- the actual
cancel logic lives in the SDK's cancel_resource() method, not in the
standard CRUD execute() pipeline.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIControllerJobCancel_v2(BaseTransformMixin):
    """
    API v2 representation of a controller job cancel request.
    """

    job_id: Optional[int] = None
    fail_if_not_running: bool = False
    id: Optional[int] = None


class ControllerJobCancelTransformMixin_v2(BaseTransformMixin):
    """
    Transform mixin for ControllerJobCancel API v2.

    This is a minimal mixin -- cancel operations bypass the standard
    CRUD endpoint operations and use cancel_resource() directly.
    """

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIControllerJobCancel_v2":
        """Create API instance from Ansible dataclass."""
        return APIControllerJobCancel_v2(
            job_id=getattr(ansible_instance, "job_id", None),
            fail_if_not_running=getattr(ansible_instance, "fail_if_not_running", False),
            id=getattr(ansible_instance, "id", None),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for controller job cancel operations.

        Cancel uses a POST to /cancel/ sub-endpoint rather than standard CRUD.
        The list endpoint is used only for finding/validating the job exists.
        """
        return {
            "list": EndpointOperation(
                path="/api/controller/v2/jobs/",
                method="GET",
                fields=[],
                required_for="find",
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
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "job_id"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleControllerJobCancel":
        """Transform from API format to Ansible format."""
        from ....ansible_models.controller_job_cancel import AnsibleControllerJobCancel

        return AnsibleControllerJobCancel(
            job_id=api_data.get("id", 0),
            id=api_data.get("id"),
        )
