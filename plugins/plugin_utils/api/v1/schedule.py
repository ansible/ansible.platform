"""
API v1 Schedule dataclass and transform mixin.

Handles transformations between Ansible format and the Controller API format
for schedule resources.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...ansible_models.schedule import AnsibleSchedule
from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

_NAME_LOOKUP_FIELDS = (
    ("inventory", "/api/controller/v2/inventories/"),
    ("execution_environment", "/api/controller/v2/execution_environments/"),
    ("unified_job_template", "/api/controller/v2/unified_job_templates/"),
)

_DIRECT_FIELDS = (
    "description",
    "rrule",
    "forks",
    "job_slice_count",
    "timeout",
    "scm_branch",
    "job_type",
    "job_tags",
    "skip_tags",
    "limit",
    "diff_mode",
    "verbosity",
    "enabled",
)


@dataclass
class APISchedule_v1:
    """Wire format for Controller schedules."""

    name: str
    rrule: Optional[str] = None
    description: Optional[str] = None
    unified_job_template: Optional[int] = None
    execution_environment: Optional[int] = None
    extra_data: Optional[dict] = None
    forks: Optional[int] = None
    inventory: Optional[int] = None
    job_slice_count: Optional[int] = None
    timeout: Optional[int] = None
    scm_branch: Optional[str] = None
    job_type: Optional[str] = None
    job_tags: Optional[str] = None
    skip_tags: Optional[str] = None
    limit: Optional[str] = None
    diff_mode: Optional[bool] = None
    verbosity: Optional[int] = None
    enabled: Optional[bool] = None
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class ScheduleTransformMixin_v1(BaseTransformMixin):
    """Transforms between AnsibleSchedule and APISchedule_v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance: AnsibleSchedule, context: TransformContext) -> APISchedule_v1:
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

        if ansible_instance.extra_data is not None:
            params["extra_data"] = ansible_instance.extra_data

        # Read-only from API (for building the {id} URL path param in execute)
        for field in ("id", "created", "modified", "url"):
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = value

        return APISchedule_v1(**params)

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: TransformContext) -> AnsibleSchedule:
        """Reverse: API response -> Ansible model."""

        def _str_or_none(val: Any) -> Optional[str]:
            return str(val) if val is not None else None

        return AnsibleSchedule(
            id=api_data.get("id"),
            name=api_data.get("name", ""),
            rrule=api_data.get("rrule"),
            description=api_data.get("description"),
            unified_job_template=_str_or_none(api_data.get("unified_job_template")),
            execution_environment=_str_or_none(api_data.get("execution_environment")),
            extra_data=api_data.get("extra_data"),
            forks=api_data.get("forks"),
            inventory=_str_or_none(api_data.get("inventory")),
            job_slice_count=api_data.get("job_slice_count"),
            timeout=api_data.get("timeout"),
            scm_branch=api_data.get("scm_branch"),
            job_type=api_data.get("job_type"),
            job_tags=api_data.get("job_tags"),
            skip_tags=api_data.get("skip_tags"),
            limit=api_data.get("limit"),
            diff_mode=api_data.get("diff_mode"),
            verbosity=api_data.get("verbosity"),
            enabled=api_data.get("enabled"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        fields = [
            "name",
            "description",
            "rrule",
            "unified_job_template",
            "execution_environment",
            "extra_data",
            "forks",
            "inventory",
            "job_slice_count",
            "timeout",
            "scm_branch",
            "job_type",
            "job_tags",
            "skip_tags",
            "limit",
            "diff_mode",
            "verbosity",
            "enabled",
        ]

        return {
            "create": EndpointOperation(
                path="/api/controller/v2/schedules/",
                method="POST",
                fields=fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/schedules/{id}/",
                method="PATCH",
                fields=fields,
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
    def get_find_list_query_params(cls, ansible_data: APISchedule_v1) -> Dict[str, Any]:
        """Scope name lookups by unified_job_template — schedule names are only unique per-template."""
        ujt_id = getattr(ansible_data, "unified_job_template", None)
        if ujt_id is not None:
            return {"unified_job_template": ujt_id}
        return {}
