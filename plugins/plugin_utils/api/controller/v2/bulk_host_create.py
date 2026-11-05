"""Transform and endpoint definition for Controller bulk host creation."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ....ansible_models.bulk_host_create import AnsibleBulkHostCreate
from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

BULK_HOST_CREATE_ENDPOINT = "/api/controller/v2/bulk/host_create/"


@dataclass
class APIBulkHostCreate_v2(BaseTransformMixin):
    """API representation of a Controller bulk host creation request."""

    inventory: Optional[int] = None
    hosts: List[Dict[str, Any]] = field(default_factory=list)


class BulkHostCreateTransformMixin_v2(BaseTransformMixin):
    """Resolve bulk host references and serialize the Controller request body."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance: AnsibleBulkHostCreate,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIBulkHostCreate_v2:
        """Resolve inventory references and encode host variables for Controller."""
        manager = cls._normalize_context(context).manager
        organization = getattr(ansible_instance, "organization", None)
        if organization is not None:
            if str(organization).strip().isdigit():
                organization_id = int(str(organization).strip())
            else:
                organization_id = manager.lookup_resource_id("organizations", "name", str(organization), service="controller", require_unique=True)
                if organization_id is None:
                    raise ValueError("Organization '%s' not found" % organization)
        else:
            organization_id = None

        inventory = getattr(ansible_instance, "inventory", None)
        if inventory is None:
            raise ValueError("inventory is required")
        lookup_kwargs = {"service": "controller", "require_unique": True}
        if organization_id is not None:
            lookup_kwargs["extra_query_params"] = {"organization": organization_id}
        inventory_id = manager.lookup_resource_id("inventories", "name", str(inventory), **lookup_kwargs)
        if inventory_id is None:
            raise ValueError("Inventory '%s' not found" % inventory)

        hosts = []
        for host in getattr(ansible_instance, "hosts", []):
            host_data = dict(host)
            variables = host_data.get("variables")
            if isinstance(variables, dict):
                host_data["variables"] = json.dumps(variables)
            hosts.append(host_data)

        return APIBulkHostCreate_v2(inventory=inventory_id, hosts=hosts)

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> AnsibleBulkHostCreate:
        """Convert the response to the stable Ansible model."""
        return AnsibleBulkHostCreate(hosts=api_data.get("hosts", []), inventory=api_data.get("inventory"))

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Declare the bulk create endpoint and its request fields."""
        return {
            "create": EndpointOperation(
                path=BULK_HOST_CREATE_ENDPOINT,
                method="POST",
                fields=["inventory", "hosts"],
                required_for="create",
                order=1,
            )
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        """Return the inventory lookup field for loader compatibility."""
        return "inventory"
