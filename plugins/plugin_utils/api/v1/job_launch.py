"""
API v1 JobLaunch dataclass and transform mixin.

Handles transformations between Ansible format and the Controller API format
for launching a job template.

Launching a job is a POST to an existing job_template's /launch/ sub-action
endpoint, not a generic resource create — so the "create" and "get" operations
target two different Controller resource types:
  - create: POST /api/controller/v2/job_templates/{job_template_id}/launch/
  - get (poll for completion): GET /api/controller/v2/jobs/{id}/

The job_template itself is resolved directly via /api/controller/v2/job_templates/
by name (not unified_job_templates, which also returns other unified job template
types sharing the same name — see from_ansible_data's docstring). This collection
does not (yet) ship a job_template CRUD module to depend on, but the underlying
Controller list endpoint exists regardless of whether this collection has a
module wrapping it.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ...ansible_models.job_launch import AnsibleJobLaunch
from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

_NAME_LOOKUP_FIELDS = (
    ("inventory", "/api/controller/v2/inventories/"),
    ("execution_environment", "/api/controller/v2/execution_environments/"),
)

_NAME_LOOKUP_LIST_FIELDS = (
    ("credentials", "/api/controller/v2/credentials/"),
    ("labels", "/api/controller/v2/labels/"),
    ("instance_groups", "/api/controller/v2/instance_groups/"),
)

_DIRECT_FIELDS = (
    "job_type",
    "limit",
    "scm_branch",
    "verbosity",
    "diff_mode",
    "extra_vars",
    "credential_passwords",
    "forks",
    "job_slice_count",
)


@dataclass
class APIJobLaunch_v1:
    """Wire format for launching/polling a Controller job."""

    job_template_id: Optional[int] = None
    job_type: Optional[str] = None
    inventory: Optional[int] = None
    credentials: Optional[List[int]] = None
    extra_vars: Optional[dict] = None
    limit: Optional[str] = None
    job_tags: Optional[str] = None
    scm_branch: Optional[str] = None
    skip_tags: Optional[str] = None
    verbosity: Optional[int] = None
    diff_mode: Optional[bool] = None
    credential_passwords: Optional[dict] = None
    execution_environment: Optional[int] = None
    forks: Optional[int] = None
    instance_groups: Optional[List[int]] = None
    job_slice_count: Optional[int] = None
    labels: Optional[List[int]] = None
    timeout: Optional[int] = None
    id: Optional[int] = None
    status: Optional[str] = None
    finished: Optional[str] = None


class JobLaunchTransformMixin_v1(BaseTransformMixin):
    """Transforms between AnsibleJobLaunch and APIJobLaunch_v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance: AnsibleJobLaunch, context: TransformContext) -> APIJobLaunch_v1:
        """Forward: Ansible model -> API wire format.

        If ``ansible_instance.id`` is already set (a poll of an in-flight job,
        via _wait_for_resource_completion's replace()), reuse it directly for
        the "get" operation's {id} path param. Otherwise this is the initial
        launch: resolve the target job_template's id directly via the
        job_templates endpoint (not unified_job_templates, which also returns
        workflow_job_templates/inventory_sources/projects sharing the same
        name — lookup_resource_id takes the first match regardless of type,
        so a same-named workflow job template would resolve to the wrong id
        and 404 against the job_template-specific /launch/ endpoint) for the
        "create" operation's {job_template_id} path param.
        """
        if ansible_instance.id is not None:
            return APIJobLaunch_v1(id=ansible_instance.id)

        job_template_id = context.manager.lookup_resource_id("/api/controller/v2/job_templates/", "name", ansible_instance.name)
        if job_template_id is None:
            raise ValueError("Unable to find job template by name '%s'" % ansible_instance.name)

        params: Dict[str, Any] = {"job_template_id": job_template_id}

        for field, endpoint in _NAME_LOOKUP_FIELDS:
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = context.manager.lookup_resource_id(endpoint, "name", value)

        for field, endpoint in _NAME_LOOKUP_LIST_FIELDS:
            values = getattr(ansible_instance, field, None)
            if values is not None:
                params[field] = [context.manager.lookup_resource_id(endpoint, "name", v) for v in values]

        for field in _DIRECT_FIELDS:
            value = getattr(ansible_instance, field, None)
            if value is not None:
                params[field] = value

        # Comma-separated on the wire, list on the Ansible side.
        if ansible_instance.tags is not None:
            params["job_tags"] = ",".join(ansible_instance.tags)
        if ansible_instance.skip_tags is not None:
            params["skip_tags"] = ",".join(ansible_instance.skip_tags)

        # job_timeout is renamed to the wire field "timeout" (not to be confused
        # with the wait-poll "timeout" control flag, which never reaches here).
        if ansible_instance.job_timeout is not None:
            params["timeout"] = ansible_instance.job_timeout

        return APIJobLaunch_v1(**params)

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: TransformContext) -> AnsibleJobLaunch:
        """Reverse: API response (the launched/polled job) -> Ansible model."""
        inventory = api_data.get("inventory")

        return AnsibleJobLaunch(
            id=api_data.get("id"),
            name=api_data.get("name", ""),
            inventory=str(inventory) if inventory is not None else None,
            status=api_data.get("status"),
            finished=api_data.get("finished"),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        launch_fields = [
            "job_type",
            "inventory",
            "credentials",
            "extra_vars",
            "limit",
            "job_tags",
            "scm_branch",
            "skip_tags",
            "verbosity",
            "diff_mode",
            "credential_passwords",
            "execution_environment",
            "forks",
            "instance_groups",
            "job_slice_count",
            "labels",
            "timeout",
        ]

        return {
            "create": EndpointOperation(
                path="/api/controller/v2/job_templates/{job_template_id}/launch/",
                method="POST",
                fields=launch_fields,
                path_params=["job_template_id"],
                required_for="create",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/jobs/{id}/",
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
