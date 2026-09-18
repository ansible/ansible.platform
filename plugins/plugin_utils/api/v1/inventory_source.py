"""
API v1 InventorySource dataclass and transform mixin.

Handles transformations between Ansible format and the Controller API format
for inventory source resources.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...ansible_models.inventory_source import AnsibleInventorySource
from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

_NAME_LOOKUP_FIELDS = (
    ("inventory", "/api/controller/v2/inventories/"),
    ("credential", "/api/controller/v2/credentials/"),
    ("execution_environment", "/api/controller/v2/execution_environments/"),
    ("source_project", "/api/controller/v2/projects/"),
)

_DIRECT_FIELDS = (
    "description",
    "source",
    "source_path",
    "scm_branch",
    "enabled_var",
    "enabled_value",
    "host_filter",
    "overwrite",
    "overwrite_vars",
    "timeout",
    "verbosity",
    "limit",
    "update_on_launch",
    "update_cache_timeout",
)


@dataclass
class APIInventorySource_v1:
    """Wire format for Controller inventory sources."""

    name: str
    inventory: Optional[int] = None
    description: Optional[str] = None
    source: Optional[str] = None
    source_path: Optional[str] = None
    source_vars: Optional[str] = None
    scm_branch: Optional[str] = None
    credential: Optional[int] = None
    enabled_var: Optional[str] = None
    enabled_value: Optional[str] = None
    host_filter: Optional[str] = None
    overwrite: Optional[bool] = None
    overwrite_vars: Optional[bool] = None
    timeout: Optional[int] = None
    verbosity: Optional[int] = None
    limit: Optional[str] = None
    execution_environment: Optional[int] = None
    update_on_launch: Optional[bool] = None
    update_cache_timeout: Optional[int] = None
    source_project: Optional[int] = None
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class InventorySourceTransformMixin_v1(BaseTransformMixin):
    """Transforms between AnsibleInventorySource and APIInventorySource_v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance: AnsibleInventorySource, context: TransformContext) -> APIInventorySource_v1:
        """Forward: Ansible model -> API wire format."""
        params: Dict[str, Any] = {
            "name": ansible_instance.new_name or ansible_instance.name,
        }

        for field, endpoint in _NAME_LOOKUP_FIELDS:
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = context.manager.lookup_resource_id(endpoint, "name", value)

        for field in _DIRECT_FIELDS:
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = value

        # Convert source_vars dict to JSON string for the API
        if ansible_instance.source_vars is not None:
            if isinstance(ansible_instance.source_vars, dict):
                params["source_vars"] = json.dumps(ansible_instance.source_vars)
            else:
                params["source_vars"] = str(ansible_instance.source_vars)

        # Read-only from API (for building the {id} URL path param in execute)
        for field in ("id", "created", "modified", "url"):
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = value

        return APIInventorySource_v1(**params)

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: TransformContext) -> AnsibleInventorySource:
        """Reverse: API response -> Ansible model."""
        raw_vars = api_data.get("source_vars")
        source_vars: Optional[dict] = None
        if isinstance(raw_vars, dict):
            source_vars = raw_vars
        elif isinstance(raw_vars, str) and raw_vars.strip():
            try:
                source_vars = json.loads(raw_vars)
            except ValueError:
                source_vars = None

        def _str_or_none(val: Any) -> Optional[str]:
            return str(val) if val is not None else None

        return AnsibleInventorySource(
            id=api_data.get("id"),
            name=api_data.get("name", ""),
            inventory=_str_or_none(api_data.get("inventory")),
            description=api_data.get("description"),
            source=api_data.get("source"),
            source_path=api_data.get("source_path"),
            source_vars=source_vars,
            scm_branch=api_data.get("scm_branch"),
            credential=_str_or_none(api_data.get("credential")),
            enabled_var=api_data.get("enabled_var"),
            enabled_value=api_data.get("enabled_value"),
            host_filter=api_data.get("host_filter"),
            overwrite=api_data.get("overwrite"),
            overwrite_vars=api_data.get("overwrite_vars"),
            timeout=api_data.get("timeout"),
            verbosity=api_data.get("verbosity"),
            limit=api_data.get("limit"),
            execution_environment=_str_or_none(api_data.get("execution_environment")),
            update_on_launch=api_data.get("update_on_launch"),
            update_cache_timeout=api_data.get("update_cache_timeout"),
            source_project=_str_or_none(api_data.get("source_project")),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = [
            "name",
            "description",
            "inventory",
            "source",
            "source_path",
            "source_vars",
            "scm_branch",
            "credential",
            "enabled_var",
            "enabled_value",
            "host_filter",
            "overwrite",
            "overwrite_vars",
            "timeout",
            "verbosity",
            "limit",
            "execution_environment",
            "update_on_launch",
            "update_cache_timeout",
            "source_project",
        ]

        return {
            "create": EndpointOperation(
                path="/api/controller/v2/inventory_sources/",
                method="POST",
                fields=fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/inventory_sources/{id}/",
                method="PATCH",
                fields=fields,
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/inventory_sources/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/inventory_sources/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/inventory_sources/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def get_find_list_query_params(cls, ansible_data: APIInventorySource_v1) -> Dict[str, Any]:
        """Scope name lookups by inventory — source names are only unique per-inventory."""
        inventory_id = getattr(ansible_data, "inventory", None)
        if inventory_id is not None:
            return {"inventory": inventory_id}
        return {}
