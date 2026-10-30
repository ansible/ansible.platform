"""API v2 WorkflowLaunch dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format.
The launch action uses the transform to resolve foreign keys and normalize
launch fields before calling the SDK launch endpoint.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Union
from urllib.parse import quote

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

WJT_LIST_ENDPOINT = "/api/controller/v2/workflow_job_templates/"
WORKFLOW_JOBS_ENDPOINT = "/api/controller/v2/workflow_jobs/"
_ORGANIZATION_LIST_ENDPOINT = "/api/gateway/v1/organizations/"
_INVENTORY_LIST_ENDPOINT = "/api/controller/v2/inventories/"
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
    named_url_endpoint: str,
    reject_ambiguous: bool = False,
) -> Optional[int]:
    """Resolve an Ansible resource reference to an API ID.

    In addition to numeric IDs and names, the legacy modules accept named URL
    references such as ``Production++``.  The Controller API exposes those as
    detail paths, so resolve them before falling back to a name-filtered list
    lookup.
    """
    if value is None:
        return None

    value_string = str(value).strip()
    if not value_string:
        return None
    if value_string.isdigit():
        return int(value_string)

    if "++" in value_string:
        named_url = f"{named_url_endpoint}{quote(value_string, safe='+')}/"
        try:
            named_result = manager.search_api(named_url)
            if named_result.get("id") is not None:
                return int(named_result["id"])
        except Exception:
            # Preserve the legacy fallback: if the named URL is not found,
            # try the value as a literal resource name.
            pass

    if reject_ambiguous:
        response = manager.search_api(named_url_endpoint, query_params={"name": value_string}, return_all=True)
        results = response.get("results", [])
        result_count = response.get("count")
        if not results:
            raise ValueError("Resource '%s' with name=%s not found" % (endpoint, value_string))
        if len(results) > 1 or (isinstance(result_count, int) and result_count > 1):
            resource_label = endpoint[:-3] + "y" if endpoint.endswith("ies") else endpoint.rstrip("s")
            raise ValueError("More than one %s matched name '%s'" % (resource_label, value_string))
        resource_id = results[0].get("id")
        if resource_id is None:
            raise ValueError("Resource '%s' with name=%s has no ID" % (endpoint, value_string))
        return int(resource_id)

    if service == "gateway":
        return manager.lookup_resource_id(endpoint, "name", value_string)
    return manager.lookup_resource_id(endpoint, "name", value_string, service=service)


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

        return APIWorkflowLaunch_v2(
            name=getattr(ansible_instance, "name", None),
            organization=_lookup_resource_id(manager, organization, "organizations", "gateway", _ORGANIZATION_LIST_ENDPOINT),
            inventory=_lookup_resource_id(
                manager,
                inventory,
                "inventories",
                "controller",
                _INVENTORY_LIST_ENDPOINT,
                reject_ambiguous=True,
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
