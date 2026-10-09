"""
API v2 BulkHostCreate dataclass and transform mixin.

BulkHostCreate POSTs a list of hosts to /bulk/host_create/ to add them
to an inventory in a single request. There is no standard CRUD lifecycle.
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
    hosts: List = field(default_factory=list)


class BulkHostCreateTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for BulkHostCreate API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIBulkHostCreate_v2:
        return APIBulkHostCreate_v2(
            hosts=getattr(ansible_instance, "hosts", []),
            inventory=None,
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
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
        return ""

    @classmethod
    def resolve(cls, ansible_instance, context: TransformContext) -> dict:
        """Bulk create hosts in an inventory via the controller API."""
        hosts = list(getattr(ansible_instance, "hosts", []))
        inventory_name = getattr(ansible_instance, "inventory", None)

        if not inventory_name:
            raise ValueError("inventory is required")
        if not hosts:
            raise ValueError("hosts list is required and cannot be empty")

        if str(inventory_name).isdigit():
            inv_id = int(inventory_name)
        else:
            inv_id = context.manager.lookup_resource_id(
                "inventories", "name", inventory_name, service="controller"
            )
            if inv_id is None:
                raise ValueError(f"Inventory '{inventory_name}' not found")

        for h in hosts:
            if "variables" in h and isinstance(h["variables"], dict):
                h["variables"] = json.dumps(h["variables"])

        url = context.manager._build_url(
            "/api/controller/v2/bulk/host_create/",
            service="controller",
            api_version=context.api_version,
        )

        response = context.manager.session.post(
            url,
            json={"inventory": inv_id, "hosts": hosts},
            timeout=context.manager.request_timeout,
            verify=context.manager.requests_verify,
        )

        if response.status_code != 201:
            body = response.text[:500]
            raise ValueError(
                f"Failed to create hosts (status {response.status_code}): {body}"
            )

        return {"changed": True}

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.bulk_host_create import AnsibleBulkHostCreate

        return AnsibleBulkHostCreate()
