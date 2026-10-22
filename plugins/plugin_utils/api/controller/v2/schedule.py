"""
API v2 Schedule dataclass and transform mixin.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

BASE_PATH = "/api/controller/v2/schedules"


@dataclass
class APISchedule_v2(BaseTransformMixin):
    """API v2 representation of a Controller schedule."""

    name: Optional[str] = None
    description: Optional[str] = None
    rrule: Optional[str] = None
    unified_job_template: Optional[int] = None
    enabled: Optional[bool] = None
    extra_data: Optional[str] = None
    inventory: Optional[int] = None
    scm_branch: Optional[str] = None
    job_type: Optional[str] = None
    job_tags: Optional[str] = None
    skip_tags: Optional[str] = None
    limit: Optional[str] = None
    diff_mode: Optional[bool] = None
    verbosity: Optional[int] = None
    forks: Optional[int] = None
    job_slice_count: Optional[int] = None
    timeout: Optional[int] = None
    execution_environment: Optional[int] = None
    id: Optional[int] = None


class ScheduleTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for Schedule API v2."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APISchedule_v2":
        api_data: Dict[str, Any] = {}
        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
        op = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")
        include_nulls = (
            getattr(context, "include_nulls_for_update", False) if isinstance(context, TransformContext) else context.get("include_nulls_for_update", False)
        )

        if op == "create":
            api_data["name"] = name or new_name
        elif op == "update":
            if new_name is not None:
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                api_data["name"] = name

        ujt = getattr(ansible_instance, "unified_job_template", None)
        if ujt is not None:
            manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
            if manager is not None and not str(ujt).strip().isdigit():
                api_data["unified_job_template"] = manager.lookup_resource_id("unified_job_templates", "name", ujt, service="controller")
            else:
                api_data["unified_job_template"] = int(ujt) if ujt is not None else None

        _SCALAR_FIELDS = (
            "description",
            "rrule",
            "enabled",
            "scm_branch",
            "job_type",
            "job_tags",
            "skip_tags",
            "limit",
            "diff_mode",
            "verbosity",
            "forks",
            "job_slice_count",
            "timeout",
        )
        for field in _SCALAR_FIELDS:
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
            elif op == "update" and include_nulls and field == "description":
                api_data[field] = ""

        extra_data = getattr(ansible_instance, "extra_data", None)
        if extra_data is not None:
            import json

            api_data["extra_data"] = json.dumps(extra_data) if isinstance(extra_data, dict) else extra_data

        manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")

        inventory = getattr(ansible_instance, "inventory", None)
        if inventory is not None:
            if manager is not None and not str(inventory).strip().isdigit():
                api_data["inventory"] = manager.lookup_resource_id("inventories", "name", inventory, service="controller")
            else:
                api_data["inventory"] = int(inventory)

        execution_environment = getattr(ansible_instance, "execution_environment", None)
        if execution_environment is not None:
            if manager is not None and not str(execution_environment).strip().isdigit():
                api_data["execution_environment"] = manager.lookup_resource_id("execution_environments", "name", execution_environment, service="controller")
            else:
                api_data["execution_environment"] = int(execution_environment)

        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APISchedule_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/schedules/",
                method="POST",
                fields=[
                    "name",
                    "description",
                    "rrule",
                    "unified_job_template",
                    "enabled",
                    "extra_data",
                    "inventory",
                    "scm_branch",
                    "job_type",
                    "job_tags",
                    "skip_tags",
                    "limit",
                    "diff_mode",
                    "verbosity",
                    "forks",
                    "job_slice_count",
                    "timeout",
                    "execution_environment",
                ],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/schedules/{id}/",
                method="PATCH",
                fields=[
                    "name",
                    "description",
                    "rrule",
                    "unified_job_template",
                    "enabled",
                    "extra_data",
                    "inventory",
                    "scm_branch",
                    "job_type",
                    "job_tags",
                    "skip_tags",
                    "limit",
                    "diff_mode",
                    "verbosity",
                    "forks",
                    "job_slice_count",
                    "timeout",
                    "execution_environment",
                ],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/schedules/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/schedules/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/schedules/",
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
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]):
        from ....ansible_models.schedule import AnsibleSchedule

        ujt_val = api_data.get("unified_job_template")
        ujt_str = str(ujt_val) if ujt_val is not None else ""

        extra_data = api_data.get("extra_data")
        if isinstance(extra_data, str) and extra_data.strip():
            import json as _json

            try:
                extra_data = _json.loads(extra_data)
            except ValueError:
                extra_data = None
        elif not isinstance(extra_data, dict):
            extra_data = None

        inv_val = api_data.get("inventory")
        ee_val = api_data.get("execution_environment")

        return AnsibleSchedule(
            name=api_data.get("name", ""),
            description=api_data.get("description"),
            rrule=api_data.get("rrule"),
            unified_job_template=ujt_str,
            enabled=api_data.get("enabled"),
            extra_data=extra_data if extra_data else None,
            inventory=str(inv_val) if inv_val is not None else None,
            scm_branch=api_data.get("scm_branch") or None,
            job_type=api_data.get("job_type") or None,
            job_tags=api_data.get("job_tags") or None,
            skip_tags=api_data.get("skip_tags") or None,
            limit=api_data.get("limit") or None,
            diff_mode=api_data.get("diff_mode"),
            verbosity=api_data.get("verbosity"),
            forks=api_data.get("forks"),
            job_slice_count=api_data.get("job_slice_count"),
            timeout=api_data.get("timeout"),
            execution_environment=str(ee_val) if ee_val is not None else None,
            id=api_data.get("id"),
        )
