"""
API v2 JobLaunch dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 launch format.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

CONTROLLER_JOB_TEMPLATES_ENDPOINT = "/api/controller/v2/job_templates/"
CONTROLLER_JOB_TEMPLATE_LAUNCH_ENDPOINT = "/api/controller/v2/job_templates/{id}/launch/"
CONTROLLER_JOB_ENDPOINT = "/api/controller/v2/jobs/{id}/"


@dataclass
class APIJobLaunch_v2(BaseTransformMixin):
    """API v2 representation of a Controller job launch payload."""

    job_type: Optional[str] = None
    limit: Optional[str] = None
    scm_branch: Optional[str] = None
    verbosity: Optional[int] = None
    diff_mode: Optional[bool] = None
    forks: Optional[int] = None
    job_slice_count: Optional[int] = None
    extra_vars: Optional[str] = None
    job_tags: Optional[str] = None
    skip_tags: Optional[str] = None
    timeout: Optional[int] = None
    credential_passwords: Optional[Dict[str, Any]] = None
    inventory: Optional[int] = None
    execution_environment: Optional[int] = None
    credentials: Optional[List[int]] = None
    instance_groups: Optional[List[int]] = None
    labels: Optional[List[int]] = None

    # Identity (resolved from name)
    job_template_id: Optional[int] = None


class JobLaunchTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for JobLaunch API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APIJobLaunch_v2":
        api_data: Dict[str, Any] = {}
        manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")

        # Resolve job template name → ID (also returns org for scoping downstream lookups)
        name = getattr(ansible_instance, "name", None)
        organization = getattr(ansible_instance, "organization", None)
        jt_id, resolved_org_id = cls._resolve_job_template(manager, name, organization)
        api_data["job_template_id"] = jt_id
        org_scope = {"organization": resolved_org_id} if resolved_org_id is not None else None

        for field in ("job_type", "limit", "scm_branch", "verbosity", "diff_mode", "forks", "job_slice_count"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        extra_vars = getattr(ansible_instance, "extra_vars", None)
        if extra_vars is not None:
            api_data["extra_vars"] = json.dumps(extra_vars) if isinstance(extra_vars, dict) else extra_vars

        tags = getattr(ansible_instance, "tags", None)
        if tags is not None:
            api_data["job_tags"] = ",".join(tags)

        skip_tags = getattr(ansible_instance, "skip_tags", None)
        if skip_tags is not None:
            api_data["skip_tags"] = ",".join(skip_tags)

        job_timeout = getattr(ansible_instance, "job_timeout", None)
        if job_timeout is not None:
            api_data["timeout"] = job_timeout

        credential_passwords = getattr(ansible_instance, "credential_passwords", None)
        if credential_passwords is not None:
            api_data["credential_passwords"] = credential_passwords

        # FK resolution: inventory name → ID (scoped to JT's org to avoid cross-org ambiguity)
        inventory = getattr(ansible_instance, "inventory", None)
        if inventory is not None:
            if str(inventory).isdigit():
                api_data["inventory"] = int(inventory)
            elif manager is not None:
                api_data["inventory"] = manager.lookup_resource_id(
                    "inventories",
                    "name",
                    inventory,
                    service="controller",
                    extra_query_params=org_scope,
                    require_unique=True,
                )

        # FK resolution: execution_environment name → ID
        execution_environment = getattr(ansible_instance, "execution_environment", None)
        if execution_environment is not None:
            if str(execution_environment).isdigit():
                api_data["execution_environment"] = int(execution_environment)
            elif manager is not None:
                api_data["execution_environment"] = manager.lookup_resource_id(
                    "execution_environments",
                    "name",
                    execution_environment,
                    service="controller",
                    require_unique=True,
                )

        # FK resolution: credentials list (names → IDs, scoped to JT's org)
        credentials = getattr(ansible_instance, "credentials", None)
        if credentials is not None and manager is not None:
            api_data["credentials"] = [
                int(c)
                if str(c).isdigit()
                else manager.lookup_resource_id(
                    "credentials",
                    "name",
                    c,
                    service="controller",
                    extra_query_params=org_scope,
                    require_unique=True,
                )
                for c in credentials
            ]

        # FK resolution: instance_groups list (names → IDs)
        instance_groups = getattr(ansible_instance, "instance_groups", None)
        if instance_groups is not None and manager is not None:
            api_data["instance_groups"] = [
                int(ig)
                if str(ig).isdigit()
                else manager.lookup_resource_id(
                    "instance_groups",
                    "name",
                    ig,
                    service="controller",
                    require_unique=True,
                )
                for ig in instance_groups
            ]

        # FK resolution: labels list (names → IDs, scoped to JT's org)
        labels = getattr(ansible_instance, "labels", None)
        if labels is not None and manager is not None:
            api_data["labels"] = [
                int(lb)
                if str(lb).isdigit()
                else manager.lookup_resource_id(
                    "labels",
                    "name",
                    lb,
                    service="controller",
                    extra_query_params=org_scope,
                    require_unique=True,
                )
                for lb in labels
            ]

        return APIJobLaunch_v2(**api_data)

    @staticmethod
    def _resolve_job_template(manager, name, organization):
        """Resolve a job template name (and optional organization) to its numeric ID and organization.

        Returns:
            Tuple of (job_template_id, organization_id) where organization_id may be None.
        """
        from ansible.errors import AnsibleError

        if str(name).isdigit():
            return int(name), None
        if organization:
            org_id = manager.lookup_resource_id("organizations", "name", organization)
            data = manager.search_api(
                CONTROLLER_JOB_TEMPLATES_ENDPOINT,
                query_params={"name": name, "organization": org_id},
            )
            results = data.get("results", [])
            if not results:
                raise AnsibleError(f"Job template '{name}' not found in organization '{organization}'")
            return results[0]["id"], org_id
        data = manager.search_api(
            CONTROLLER_JOB_TEMPLATES_ENDPOINT,
            query_params={"name": name},
        )
        results = data.get("results", [])
        if not results:
            raise AnsibleError(f"Job template '{name}' not found")
        if len(results) > 1:
            orgs = [r.get("organization") for r in results]
            raise AnsibleError(f"Multiple job templates named '{name}' found (organizations: {orgs}). Specify 'organization' to disambiguate.")
        return results[0]["id"], results[0].get("organization")

    @classmethod
    def to_launch_payload(cls, api_data: "APIJobLaunch_v2") -> Dict[str, Any]:
        """Build the POST payload from the API dataclass, excluding None values and the resolved template ID."""
        payload = {}
        for field_name in (
            "job_type",
            "limit",
            "scm_branch",
            "verbosity",
            "diff_mode",
            "forks",
            "job_slice_count",
            "extra_vars",
            "job_tags",
            "skip_tags",
            "timeout",
            "credential_passwords",
            "inventory",
            "execution_environment",
            "credentials",
            "instance_groups",
            "labels",
        ):
            val = getattr(api_data, field_name, None)
            if val is not None:
                payload[field_name] = val
        return payload

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "launch": EndpointOperation(
                path=CONTROLLER_JOB_TEMPLATE_LAUNCH_ENDPOINT,
                method="POST",
                fields=[
                    "job_type",
                    "limit",
                    "scm_branch",
                    "verbosity",
                    "diff_mode",
                    "forks",
                    "job_slice_count",
                    "extra_vars",
                    "job_tags",
                    "skip_tags",
                    "timeout",
                    "credential_passwords",
                    "inventory",
                    "execution_environment",
                    "credentials",
                    "instance_groups",
                    "labels",
                ],
                path_params=["id"],
                required_for="launch",
                order=1,
            ),
            "get": EndpointOperation(
                path=CONTROLLER_JOB_ENDPOINT,
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

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.job_launch import AnsibleJobLaunch

        return AnsibleJobLaunch(
            name=str(api_data.get("id", "")),
            id=api_data.get("id"),
            status=api_data.get("status"),
        )
