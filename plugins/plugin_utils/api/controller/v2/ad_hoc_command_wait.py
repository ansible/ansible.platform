"""API v2 AdHocCommandWait dataclass and transform mixin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

AD_HOC_COMMANDS_ENDPOINT = "/api/controller/v2/ad_hoc_commands/"
AD_HOC_COMMANDS_DETAIL_ENDPOINT = "/api/controller/v2/ad_hoc_commands/{id}/"


@dataclass
class APIAdHocCommandWait_v2(BaseTransformMixin):
    """API v2 representation of an ad hoc command wait request."""

    command_id: Optional[int] = None
    interval: float = 2.0
    timeout: Optional[int] = None
    id: Optional[int] = None


class AdHocCommandWaitTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for AdHocCommandWait API v2.

    Minimal mixin -- wait operations bypass standard CRUD
    and use wait_for_completion() directly.
    """

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIAdHocCommandWait_v2":
        """Create API instance from Ansible dataclass."""
        return APIAdHocCommandWait_v2(
            command_id=getattr(ansible_instance, "command_id", None),
            interval=getattr(ansible_instance, "interval", 2.0),
            timeout=getattr(ansible_instance, "timeout", None),
            id=getattr(ansible_instance, "id", None),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for ad hoc command wait operations."""
        return {
            "list": EndpointOperation(
                path=AD_HOC_COMMANDS_ENDPOINT,
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
            "get": EndpointOperation(
                path=AD_HOC_COMMANDS_DETAIL_ENDPOINT,
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
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleAdHocCommandWait":
        """Transform from API format to Ansible format."""
        from ....ansible_models.ad_hoc_command_wait import AnsibleAdHocCommandWait

        return AnsibleAdHocCommandWait(
            command_id=api_data.get("id", 0),
            id=api_data.get("id"),
        )
