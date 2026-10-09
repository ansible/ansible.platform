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


@dataclass
class APISchedule_v2(BaseTransformMixin):
    """API v2 representation of a Controller schedule."""

    name: Optional[str] = None
    description: Optional[str] = None
    rrule: Optional[str] = None
    unified_job_template: Optional[int] = None
    enabled: Optional[bool] = None
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

        for field in ("description", "rrule", "enabled"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
            elif op == "update" and include_nulls and field == "description":
                api_data[field] = ""

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
                fields=["name", "description", "rrule", "unified_job_template", "enabled"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/schedules/{id}/",
                method="PATCH",
                fields=["name", "description", "rrule", "unified_job_template", "enabled"],
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

        return AnsibleSchedule(
            name=api_data.get("name", ""),
            description=api_data.get("description"),
            rrule=api_data.get("rrule"),
            unified_job_template=ujt_str,
            enabled=api_data.get("enabled"),
            id=api_data.get("id"),
        )
