"""
API v2 ControllerJobTemplate dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format.
Association fields (credentials, labels, notification templates, instance
groups), copy_from, and survey_spec are not part of core CRUD and are added
in a follow-up PR.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

_SCALAR_FIELDS = (
    "description",
    "job_type",
    "playbook",
    "scm_branch",
    "forks",
    "limit",
    "verbosity",
    "job_tags",
    "force_handlers",
    "skip_tags",
    "start_at_task",
    "timeout",
    "use_fact_cache",
    "host_config_key",
    "ask_scm_branch_on_launch",
    "ask_diff_mode_on_launch",
    "ask_variables_on_launch",
    "ask_limit_on_launch",
    "ask_tags_on_launch",
    "ask_skip_tags_on_launch",
    "ask_job_type_on_launch",
    "ask_verbosity_on_launch",
    "ask_inventory_on_launch",
    "ask_credential_on_launch",
    "ask_execution_environment_on_launch",
    "ask_labels_on_launch",
    "ask_forks_on_launch",
    "ask_job_slice_count_on_launch",
    "ask_timeout_on_launch",
    "ask_instance_groups_on_launch",
    "survey_enabled",
    "become_enabled",
    "diff_mode",
    "allow_simultaneous",
    "job_slice_count",
    "webhook_service",
    "prevent_instance_group_fallback",
    "opa_query_path",
)

_WRITABLE_FIELDS = ("name",) + _SCALAR_FIELDS + ("inventory", "project", "execution_environment", "webhook_credential", "extra_vars")


@dataclass
class APIControllerJobTemplate_v2(BaseTransformMixin):
    """API v2 representation of a controller job template."""

    name: Optional[str] = None
    description: Optional[str] = None
    job_type: Optional[str] = None
    inventory: Optional[int] = None
    project: Optional[int] = None
    playbook: Optional[str] = None
    scm_branch: Optional[str] = None
    forks: Optional[int] = None
    limit: Optional[str] = None
    verbosity: Optional[int] = None
    extra_vars: Optional[str] = None
    job_tags: Optional[str] = None
    force_handlers: Optional[bool] = None
    skip_tags: Optional[str] = None
    start_at_task: Optional[str] = None
    timeout: Optional[int] = None
    use_fact_cache: Optional[bool] = None
    execution_environment: Optional[int] = None
    host_config_key: Optional[str] = None
    ask_scm_branch_on_launch: Optional[bool] = None
    ask_diff_mode_on_launch: Optional[bool] = None
    ask_variables_on_launch: Optional[bool] = None
    ask_limit_on_launch: Optional[bool] = None
    ask_tags_on_launch: Optional[bool] = None
    ask_skip_tags_on_launch: Optional[bool] = None
    ask_job_type_on_launch: Optional[bool] = None
    ask_verbosity_on_launch: Optional[bool] = None
    ask_inventory_on_launch: Optional[bool] = None
    ask_credential_on_launch: Optional[bool] = None
    ask_execution_environment_on_launch: Optional[bool] = None
    ask_labels_on_launch: Optional[bool] = None
    ask_forks_on_launch: Optional[bool] = None
    ask_job_slice_count_on_launch: Optional[bool] = None
    ask_timeout_on_launch: Optional[bool] = None
    ask_instance_groups_on_launch: Optional[bool] = None
    survey_enabled: Optional[bool] = None
    become_enabled: Optional[bool] = None
    diff_mode: Optional[bool] = None
    allow_simultaneous: Optional[bool] = None
    job_slice_count: Optional[int] = None
    webhook_service: Optional[str] = None
    webhook_credential: Optional[int] = None
    prevent_instance_group_fallback: Optional[bool] = None
    opa_query_path: Optional[str] = None

    # Read-only fields from API
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class ControllerJobTemplateTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for ControllerJobTemplate API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APIControllerJobTemplate_v2":
        api_data: Dict[str, Any] = {}

        op = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")
        manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
        service = getattr(context, "service", "controller") if isinstance(context, TransformContext) else context.get("service", "controller")
        api_version = getattr(context, "api_version", None) if isinstance(context, TransformContext) else context.get("api_version")

        # Create: use name; Update: use new_name if set, else echo back current name.
        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
        if op == "create":
            api_data["name"] = name or new_name
        elif op == "update":
            if new_name is not None:
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                api_data["name"] = name

        for field in _SCALAR_FIELDS:
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        # extra_vars: dict on the Ansible side, JSON string on the wire.
        extra_vars = getattr(ansible_instance, "extra_vars", None)
        if extra_vars is not None:
            api_data["extra_vars"] = json.dumps(extra_vars) if isinstance(extra_vars, dict) else str(extra_vars)

        inventory = getattr(ansible_instance, "inventory", None)
        if inventory is not None:
            api_data["inventory"] = manager.lookup_resource_id("inventories", "name", inventory, service=service)

        execution_environment = getattr(ansible_instance, "execution_environment", None)
        if execution_environment is not None:
            api_data["execution_environment"] = manager.lookup_resource_id("execution_environments", "name", execution_environment, service=service)

        webhook_credential = getattr(ansible_instance, "webhook_credential", None)
        if webhook_credential is not None:
            api_data["webhook_credential"] = manager.lookup_resource_id("credentials", "name", webhook_credential, service=service)

        # project: organization (Gateway-owned, see docs/12-api-landscape.md) disambiguates
        # between same-named projects in different orgs, matching the legacy awx_collection
        # job_template module's get_one(..., data={"organization": organization_id}) lookup.
        project = getattr(ansible_instance, "project", None)
        organization = getattr(ansible_instance, "organization", None)
        if project is not None:
            if str(project).isdigit():
                api_data["project"] = int(project)
            elif organization is not None:
                org_id = manager.lookup_resource_id("organizations", "name", organization)
                projects_path = f"/api/{service}/v{api_version}/projects/"
                response = manager.search_api(projects_path, query_params={"name": project, "organization": org_id})
                results = response.get("results", [])
                if not results:
                    raise ValueError(f"The project {project} in organization {organization} was not found on the controller instance")
                api_data["project"] = results[0]["id"]
            else:
                api_data["project"] = manager.lookup_resource_id("projects", "name", project, service=service)

        return APIControllerJobTemplate_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        writable_fields = list(_WRITABLE_FIELDS)
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/job_templates/",
                method="POST",
                fields=writable_fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/job_templates/{id}/",
                method="PATCH",
                fields=writable_fields,
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/job_templates/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/job_templates/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/job_templates/",
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
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.job_template import AnsibleControllerJobTemplate

        extra_vars = None
        raw_extra = api_data.get("extra_vars")
        if isinstance(raw_extra, dict):
            extra_vars = raw_extra
        elif isinstance(raw_extra, str) and raw_extra.strip():
            try:
                extra_vars = json.loads(raw_extra)
            except ValueError:
                extra_vars = None

        manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")
        cache = getattr(context, "cache", None) if isinstance(context, TransformContext) else context.get("cache")
        service = getattr(context, "service", "controller") if isinstance(context, TransformContext) else context.get("service", "controller")
        api_version = getattr(context, "api_version", None) if isinstance(context, TransformContext) else context.get("api_version")

        def _resolve_fk_name(endpoint: str, resource_id: Optional[int]) -> Optional[str]:
            # FK fields are Optional[str] (names) on AnsibleControllerJobTemplate, so the
            # raw int id from the API must be resolved back to a name here. Returning the
            # raw id instead would break _should_update()'s comparison (it diffs this
            # from_api() output against the user-supplied name, a str-vs-int mismatch that
            # always reports "changed") as well as round-trip output.
            if resource_id is None or manager is None:
                return None
            cache_key = f"id:{service}:{endpoint}:{resource_id}"
            if cache is not None and cache_key in cache:
                return cache[cache_key]
            try:
                result = manager.search_api(f"/api/{service}/v{api_version}/{endpoint}/{resource_id}/")
                name = result.get("name")
            except Exception:
                name = None
            if name is not None and cache is not None:
                cache[cache_key] = name
            return name

        kwargs = {field: api_data.get(field) for field in _SCALAR_FIELDS}
        return AnsibleControllerJobTemplate(
            name=api_data.get("name"),
            inventory=_resolve_fk_name("inventories", api_data.get("inventory")),
            project=_resolve_fk_name("projects", api_data.get("project")),
            execution_environment=_resolve_fk_name("execution_environments", api_data.get("execution_environment")),
            webhook_credential=_resolve_fk_name("credentials", api_data.get("webhook_credential")),
            extra_vars=extra_vars,
            id=api_data.get("id"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
            **kwargs,
        )
