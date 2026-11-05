"""API v2 WorkflowLaunch dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format.
The launch action uses the transform to resolve foreign keys and normalize
launch fields before calling the SDK launch endpoint.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

WORKFLOW_JOBS_ENDPOINT = "/api/controller/v2/workflow_jobs/"
WJT_LIST_ENDPOINT = "/api/controller/v2/workflow_job_templates/"
_LAUNCH_PAYLOAD_FIELDS = frozenset({"inventory", "limit", "job_tags", "skip_tags", "scm_branch", "extra_vars"})


@dataclass
class APIWorkflowLaunch_v2(BaseTransformMixin):
    """API v2 representation of a workflow launch request."""

    name: Optional[str] = None
    organization: Optional[int] = None
    inventory: Optional[int] = None
    limit: Optional[str] = None
    job_tags: Optional[str] = None
    skip_tags: Optional[str] = None
    scm_branch: Optional[str] = None
    extra_vars: Optional[Dict] = None
    id: Optional[int] = None


def _context_manager(context: Union[TransformContext, Dict[str, Any]]):
    if isinstance(context, TransformContext):
        return context.manager
    return context.get("manager")


def _lookup_resource_id(
    manager: Any,
    value: Optional[str],
    endpoint: str,
    service: str,
    extra_query_params: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """Resolve a resource reference through the shared client lookup path."""
    if value is None:
        return None

    value_string = str(value).strip()
    if not value_string:
        return None
    if value_string.isdigit():
        return int(value_string)

    return manager.lookup_resource_id(
        endpoint,
        "name",
        value_string,
        service=service,
        extra_query_params=extra_query_params,
        require_unique=True,
    )


class WorkflowLaunchTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for WorkflowLaunch API v2."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIWorkflowLaunch_v2":
        """Create an API launch request from an Ansible dataclass."""
        manager = _context_manager(context)
        if manager is None:
            raise ValueError("A manager is required to transform workflow launch data")

        organization = getattr(ansible_instance, "organization", None)
        inventory = getattr(ansible_instance, "inventory", None)
        tags = getattr(ansible_instance, "tags", None)
        skip_tags = getattr(ansible_instance, "skip_tags", None)
        extra_vars = getattr(ansible_instance, "extra_vars", None)

        organization_id = _lookup_resource_id(manager, organization, "organizations", "controller")
        organization_scope = {"organization": organization_id} if organization_id is not None else None

        return APIWorkflowLaunch_v2(
            name=getattr(ansible_instance, "name", None),
            organization=organization_id,
            inventory=_lookup_resource_id(
                manager,
                inventory,
                "inventories",
                "controller",
                extra_query_params=organization_scope,
            ),
            limit=getattr(ansible_instance, "limit", None) or None,
            job_tags=",".join(tags) if tags else None,
            skip_tags=",".join(skip_tags) if skip_tags else None,
            scm_branch=getattr(ansible_instance, "scm_branch", None) or None,
            extra_vars=extra_vars or None,
            id=getattr(ansible_instance, "id", None),
        )

    @classmethod
    def to_launch_payload(cls, api_instance: "APIWorkflowLaunch_v2") -> Dict[str, Any]:
        """Build the Controller launch payload from a transformed request."""
        api_data = asdict(api_instance)
        return {field: api_data[field] for field in _LAUNCH_PAYLOAD_FIELDS if api_data.get(field) is not None}

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define the read operations used to validate the workflow template."""
        return {
            "list": EndpointOperation(
                path=WJT_LIST_ENDPOINT,
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/workflow_job_templates/{id}/",
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
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]):
        """Transform from API format to Ansible format."""
        from ....ansible_models.workflow_launch import AnsibleWorkflowLaunch

        return AnsibleWorkflowLaunch(
            name=api_data.get("name", ""),
            id=api_data.get("id"),
        )
