"""
API v1 InventorySourceUpdate dataclass and transform mixin.

Handles transformations between Ansible format and the Controller API format
for launching an inventory source update (sync).

Launching an update is a POST to an existing inventory_source's /update/
sub-action endpoint, not a generic resource create — so the "create" and
"get" operations target two different Controller resource types:
  - create: POST /api/controller/v2/inventory_sources/{inventory_source_id}/update/
  - get (poll for completion): GET /api/controller/v2/inventory_updates/{id}/
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...ansible_models.inventory_source_update import AnsibleInventorySourceUpdate
from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIInventorySourceUpdate_v1:
    """Wire format for launching/polling a Controller inventory source update."""

    inventory_source_id: Optional[int] = None
    id: Optional[int] = None
    status: Optional[str] = None
    finished: Optional[str] = None


class InventorySourceUpdateTransformMixin_v1(BaseTransformMixin):
    """Transforms between AnsibleInventorySourceUpdate and APIInventorySourceUpdate_v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance: AnsibleInventorySourceUpdate, context: TransformContext) -> APIInventorySourceUpdate_v1:
        """Forward: Ansible model -> API wire format.

        If ``ansible_instance.id`` is already set (a poll of an in-flight
        inventory_update, via _wait_for_resource_completion's replace()), reuse
        it directly for the "get" operation's {id} path param. Otherwise this is
        the initial launch: resolve the target inventory_source's id — scoped by
        inventory, since inventory_source names are only unique per-inventory —
        by reusing InventorySourceTransformMixin_v1's own find logic rather than
        reimplementing composite name+inventory lookup here.
        """
        if ansible_instance.id is not None:
            return APIInventorySourceUpdate_v1(id=ansible_instance.id)

        find_data: Dict[str, Any] = {"name": ansible_instance.name}
        if ansible_instance.inventory is not None:
            inventory_id = context.manager.lookup_resource_id("/api/controller/v2/inventories/", "name", ansible_instance.inventory)
            if inventory_id is not None:
                find_data["inventory"] = str(inventory_id)

        found = context.manager.execute(operation="find", module_name="inventory_source", ansible_data_dict=find_data)
        if not found or not found.get("id"):
            raise ValueError("Could not find inventory_source '%s' in inventory '%s'" % (ansible_instance.name, ansible_instance.inventory))

        return APIInventorySourceUpdate_v1(inventory_source_id=found["id"])

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: TransformContext) -> AnsibleInventorySourceUpdate:
        """Reverse: API response (the launched/polled inventory_update) -> Ansible model."""
        inventory = api_data.get("inventory")

        return AnsibleInventorySourceUpdate(
            id=api_data.get("id"),
            name=api_data.get("name", ""),
            inventory=str(inventory) if inventory is not None else None,
            status=api_data.get("status"),
            finished=api_data.get("finished"),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/inventory_sources/{inventory_source_id}/update/",
                method="POST",
                fields=[],
                path_params=["inventory_source_id"],
                required_for="create",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/inventory_updates/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"
