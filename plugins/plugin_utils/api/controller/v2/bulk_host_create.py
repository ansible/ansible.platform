"""
API v2 BulkHostCreate dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format
for the bulk host create endpoint.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIBulkHostCreate_v2(BaseTransformMixin):
    """API v2 representation of a bulk host create request."""

    inventory: Optional[int] = None
    hosts: Optional[List[dict]] = field(default_factory=list)


class BulkHostCreateTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for BulkHostCreate API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIBulkHostCreate_v2:
        """Transform from Ansible format to API format.

        Resolves inventory name to ID and serializes host variables dicts
        to JSON strings as required by the controller API.
        """
        manager = context.manager if isinstance(context, TransformContext) else context.get("manager")

        # Resolve inventory name/ID to integer ID
        inventory_value = getattr(ansible_instance, "inventory", None)
        inventory_id = None
        if inventory_value is not None:
            if str(inventory_value).isdigit():
                inventory_id = int(inventory_value)
            elif manager:
                inventory_id = manager.lookup_resource_id(
                    "inventories", "name", str(inventory_value), service="controller"
                )

        # Process hosts: serialize variables dicts to JSON strings
        hosts = getattr(ansible_instance, "hosts", None) or []
        api_hosts = []
        for host in hosts:
            h = dict(host)
            if "variables" in h and h["variables"] is not None:
                if isinstance(h["variables"], dict):
                    h["variables"] = json.dumps(h["variables"])
            api_hosts.append(h)

        return APIBulkHostCreate_v2(
            inventory=inventory_id,
            hosts=api_hosts,
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for bulk host create operations."""
        return {
            "create": EndpointOperation(
                path="/bulk/host_create/",
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
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        """Transform from API response to Ansible format."""
        from ....ansible_models.bulk_host_create import AnsibleBulkHostCreate

        return AnsibleBulkHostCreate(
            hosts=api_data.get("hosts", []),
            inventory=str(api_data.get("inventory", "")),
        )
