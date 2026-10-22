"""API v2 AdHocCommandCancel dataclass and transform mixin."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIAdHocCommandCancel_v2(BaseTransformMixin):
    """API v2 representation of an ad hoc command cancel request."""

    command_id: Optional[int] = None
    fail_if_not_running: bool = False
    id: Optional[int] = None


class AdHocCommandCancelTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for AdHocCommandCancel API v2.

    Minimal mixin -- cancel operations bypass standard CRUD
    and use cancel_resource() directly.
    """

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIAdHocCommandCancel_v2":
        """Create API instance from Ansible dataclass."""
        return APIAdHocCommandCancel_v2(
            command_id=getattr(ansible_instance, "command_id", None),
            fail_if_not_running=getattr(ansible_instance, "fail_if_not_running", False),
            id=getattr(ansible_instance, "id", None),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for ad hoc command cancel operations."""
        return {
            "list": EndpointOperation(
                path="/api/controller/v2/ad_hoc_commands/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/ad_hoc_commands/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        """Return the lookup field."""
        return "command_id"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleAdHocCommandCancel":
        """Transform from API format to Ansible format."""
        from ....ansible_models.ad_hoc_command_cancel import AnsibleAdHocCommandCancel

        return AnsibleAdHocCommandCancel(
            command_id=api_data.get("id", 0),
            id=api_data.get("id"),
        )
