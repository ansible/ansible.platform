"""
API v2 Controller Bulk Host Create dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format
for the bulk host create endpoint.

This is a Shape 5 (bulk) module: array-in/array-out with partial-failure
semantics. It does NOT use the standard CRUD endpoint operations; instead,
the action plugin calls the SDK bulk_host_create() method directly.
The mixin is provided for consistency and potential future use.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIControllerBulkHostCreate_v2(BaseTransformMixin):
    """
    API v2 representation of a bulk host create request.
    """

    hosts: List[dict] = field(default_factory=list)
    inventory: Optional[str] = None


class ControllerBulkHostCreateTransformMixin_v2(BaseTransformMixin):
    """
    Transform mixin for Controller Bulk Host Create API v2.

    This is a minimal mixin for a bulk (Shape 5) module.
    The actual API call is handled by the SDK bulk_host_create() method
    rather than the standard CRUD endpoint operations pipeline.
    """

    @classmethod
    def from_ansible_data(
        cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]
    ) -> "APIControllerBulkHostCreate_v2":
        """Create API instance from Ansible dataclass."""
        return APIControllerBulkHostCreate_v2(
            hosts=getattr(ansible_instance, "hosts", []),
            inventory=getattr(ansible_instance, "inventory", None),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for bulk host create operations.

        Note: This module uses the SDK bulk_host_create() method directly
        rather than the standard CRUD pipeline, so these operations are
        provided for documentation and introspection purposes only.
        """
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/bulk/host_create/",
                method="POST",
                fields=["inventory", "hosts"],
                required_for="create",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "inventory"

    @classmethod
    def from_api(
        cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]
    ) -> "AnsibleControllerBulkHostCreate":
        """Transform from API format to Ansible format."""
        from ....ansible_models.controller_bulk_host_create import (
            AnsibleControllerBulkHostCreate,
        )

        return AnsibleControllerBulkHostCreate(
            hosts=api_data.get("hosts", []),
            inventory=api_data.get("inventory"),
        )
