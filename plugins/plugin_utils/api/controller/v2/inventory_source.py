"""
API v2 InventorySource dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

import yaml

        elif op == "update":
            if new_name is not None:
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                api_data["name"] = name

        manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")

        # FK resolution: inventory name → ID (Controller-owned)
        inventory = getattr(ansible_instance, "inventory", None)
        if inventory is not None:
            if manager is not None and not str(inventory).strip().isdigit():
                api_data["inventory"] = manager.lookup_resource_id("inventories", "name", inventory, service="controller")
            else:
                api_data["inventory"] = int(inventory) if inventory is not None else None

        # FK resolution: credential name → ID (Controller-owned)
        credential = getattr(ansible_instance, "credential", None)
        if credential is not None:
            if manager is not None and not str(credential).strip().isdigit():
                api_data["credential"] = manager.lookup_resource_id("credentials", "name", credential, service="controller")
            else:
                api_data["credential"] = int(credential)

        # FK resolution: execution_environment name → ID (Controller-owned)
        ee = getattr(ansible_instance, "execution_environment", None)
        if ee is not None:
            if manager is not None and not str(ee).strip().isdigit():
                api_data["execution_environment"] = manager.lookup_resource_id("execution_environments", "name", ee, service="controller")
            else:
                api_data["execution_environment"] = int(ee)

        # FK resolution: source_project name → ID (Controller-owned)
        source_project = getattr(ansible_instance, "source_project", None)
        if source_project is not None:
            if manager is not None and not str(source_project).strip().isdigit():
                api_data["source_project"] = manager.lookup_resource_id("projects", "name", source_project, service="controller")
            else:
                api_data["source_project"] = int(source_project)

        # Simple pass-through fields
        for field in (
            "description",
            "source",
            "source_path",
            "enabled_var",
            "enabled_value",
            "host_filter",
            "limit",
            "overwrite",
            "overwrite_vars",
            "timeout",
            "verbosity",
            "update_on_launch",
            "update_cache_timeout",
            "scm_branch",
        ):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
            elif op == "update" and include_nulls and field == "description":
                api_data[field] = ""

        # source_vars: already normalized to JSON string by __post_init__
        source_vars = getattr(ansible_instance, "source_vars", None)
        if source_vars is not None:
            api_data["source_vars"] = json.dumps(source_vars, sort_keys=True) if isinstance(source_vars, dict) else source_vars

        # Read-only from API (for building URL in execute)
        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIInventorySource_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        _fields = [
            "name",
            "description",
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
            "inventory",
            "update_on_launch",
            "update_cache_timeout",
            "source_project",
        ]
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/inventory_sources/",
                method="POST",
                fields=_fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/inventory_sources/{id}/",
                method="PATCH",
                fields=_fields,
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
    def get_find_list_query_params(cls, api_data) -> Dict[str, Any]:
        inventory_id = getattr(api_data, "inventory", None)
        if inventory_id is not None:
            try:
                return {"inventory": int(str(inventory_id).strip())}
            except Exception:
                pass
        return {}

    @staticmethod
    def _normalize_vars(val):
        if val is None:
            return None
        if isinstance(val, dict):
            return json.dumps(val, sort_keys=True)
        if isinstance(val, str) and val.strip():
            try:
                parsed = yaml.safe_load(val)
                if isinstance(parsed, dict):
                    return json.dumps(parsed, sort_keys=True)
            except Exception:
                pass
        return val

    @classmethod
            enabled_var=api_data.get("enabled_var"),
            enabled_value=api_data.get("enabled_value"),
            host_filter=api_data.get("host_filter"),
            limit=api_data.get("limit"),
            credential=_str_or_none(api_data.get("credential")),
            execution_environment=_str_or_none(api_data.get("execution_environment")),
            overwrite=api_data.get("overwrite"),
            overwrite_vars=api_data.get("overwrite_vars"),
            timeout=api_data.get("timeout"),
            verbosity=api_data.get("verbosity"),
            update_on_launch=api_data.get("update_on_launch"),
            update_cache_timeout=api_data.get("update_cache_timeout"),
            source_project=_str_or_none(api_data.get("source_project")),
            scm_branch=api_data.get("scm_branch"),
            id=api_data.get("id"),
        )
