"""API v1 EDA Project dataclass and transform mixin."""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....ansible_models.eda_project import AnsibleEdaProject
from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

# EDA project API endpoints
EDA_PROJECTS_LIST_ENDPOINT = "/api/eda/v1/projects/"
EDA_PROJECTS_DETAIL_ENDPOINT = "/api/eda/v1/projects/{id}/"
EDA_PROJECTS_SYNC_ENDPOINT = "/api/eda/v1/projects/{id}/sync/"
_PROJECT_ORGANIZATION_SUPPORT_CACHE_KEY = "capability:eda:project_organization"


def supports_project_organization(manager: Any) -> bool:
    """Return whether this EDA API supports project organizations.

    EDA 2.4 lacks the ``config`` and ``organizations`` endpoints. The legacy
    ``ansible.eda.project`` module uses the config endpoint as its capability
    check and omits organization fields when that endpoint returns 404.
    """
    if manager is None:
        return False

    cache = getattr(manager, "cache", None)
    if isinstance(cache, dict) and _PROJECT_ORGANIZATION_SUPPORT_CACHE_KEY in cache:
        return cache[_PROJECT_ORGANIZATION_SUPPORT_CACHE_KEY]

    supported = True
    try:
        manager.search_api("config", service="eda")
    except Exception as exc:
        details = getattr(exc, "details", None)
        status_code = details.get("status_code") if isinstance(details, dict) else None
        status_code = status_code or getattr(exc, "status_code", None)
        status_code = status_code or getattr(getattr(exc, "response", None), "status_code", None)
        if str(status_code) == "404" or (isinstance(exc, ValueError) and "404" in str(exc)):
            supported = False
        else:
            raise

    if isinstance(cache, dict):
        cache[_PROJECT_ORGANIZATION_SUPPORT_CACHE_KEY] = supported
    return supported


def resolve_project_organization_id(manager: Any, value: Any) -> Optional[int]:
    """Resolve an organization only when this EDA version supports projects organizations."""
    if value is None or not supports_project_organization(manager):
        return None
    return resolve_foreign_key_id(manager, "organizations", "name", value, service="eda")


def resolve_foreign_key_id(manager, endpoint: str, lookup_field: str, value, service: str = "eda") -> Optional[int]:
    """Resolve a supplied foreign-key name or ID to its canonical integer ID."""
    if value is None:
        return None
    value = str(value).strip()
    if value.isdigit():
        return int(value)
    if manager is None:
        raise ValueError("Cannot resolve %s '%s' without an API manager" % (lookup_field, value))
    resolved_id = manager.lookup_resource_id(endpoint, lookup_field, value, service=service, require_unique=True)
    if resolved_id is None:
        raise ValueError("Could not resolve %s '%s' to an ID" % (lookup_field, value))
    return int(resolved_id)


def _related_resource_name(manager, api_data: Dict[str, Any], id_field: str, relationship_field: str, endpoint: str, service: str) -> Optional[str]:
    """Return a related resource name, falling back to its stable ID string."""
    related = api_data.get(relationship_field)
    if isinstance(related, dict):
        related_name = related.get("name")
        if related_name is not None:
            return str(related_name)
        resource_id = related.get("id")
    elif isinstance(related, str) and not related.isdigit():
        return related
    else:
        resource_id = related

    resource_id = resource_id if resource_id is not None else api_data.get(id_field)
    if resource_id is None:
        return None
    if manager is not None:
        try:
            if endpoint == "organizations":
                names = manager.lookup_organization_names([int(resource_id)], service=service)
                if names and names[0] is not None:
                    return str(names[0])
            response = manager.search_api(
                "/api/%s/v1/%s/" % (service, endpoint),
                query_params={"id": int(resource_id)},
                service=service,
            )
            matches = [item for item in response.get("results", []) if str(item.get("id")) == str(resource_id)]
            if len(matches) == 1 and matches[0].get("name") is not None:
                return str(matches[0]["name"])
        except Exception:
            # Name hydration is output enrichment; the ID remains a stable value
            # for comparison and can still be returned when the lookup is unavailable.
            pass
    return str(resource_id)


@dataclass
class APIEdaProject_v1(BaseTransformMixin):
    """API v1 representation of an EDA project."""

    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    proxy: Optional[str] = None
    scm_branch: Optional[str] = None
    eda_credential_id: Optional[int] = None
    organization_id: Optional[int] = None
    update_revision_on_launch: Optional[bool] = None
    scm_update_cache_timeout: Optional[int] = None

    # Read-only fields from API
    id: Optional[int] = None
    import_state: Optional[str] = None
    import_error: Optional[str] = None


class EdaProjectTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for EDA Project API v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIEdaProject_v1":
        """Create API instance from Ansible dataclass.

        Resolves foreign key fields:
        - credential (name) -> eda_credential_id (int) via EDA credentials endpoint
        - organization_name (name) -> organization_id (int) when supported by this EDA version
        """
        api_data: Dict[str, Any] = {}
        manager = context.manager if isinstance(context, TransformContext) else context.get("manager")

        # Direct field mappings
        for field in ("name", "description", "url", "proxy", "scm_branch", "update_revision_on_launch", "scm_update_cache_timeout"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        # Handle new_name -> name rename
        new_name = getattr(ansible_instance, "new_name", None)
        if new_name is not None:
            api_data["name"] = new_name

        # Resolve credential name -> eda_credential_id
        credential = getattr(ansible_instance, "credential", None)
        if credential is not None:
            api_data["eda_credential_id"] = resolve_foreign_key_id(manager, "eda-credentials", "name", credential, service="eda")

        # Resolve organization_name -> organization_id
        organization_name = getattr(ansible_instance, "organization_name", None)
        if organization_name is not None:
            organization_id = resolve_project_organization_id(manager, organization_name)
            if organization_id is not None:
                api_data["organization_id"] = organization_id

        # Read-only fields
        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIEdaProject_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for EDA project operations."""
        return {
            "create": EndpointOperation(
                path=EDA_PROJECTS_LIST_ENDPOINT,
                method="POST",
                fields=[
                    "name",
                    "description",
                    "url",
                    "proxy",
                    "scm_branch",
                    "eda_credential_id",
                    "organization_id",
                    "update_revision_on_launch",
                    "scm_update_cache_timeout",
                ],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path=EDA_PROJECTS_DETAIL_ENDPOINT,
                method="PATCH",
                fields=[
                    "name",
                    "description",
                    "url",
                    "proxy",
                    "scm_branch",
                    "eda_credential_id",
                    "organization_id",
                    "update_revision_on_launch",
                    "scm_update_cache_timeout",
                ],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path=EDA_PROJECTS_DETAIL_ENDPOINT,
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path=EDA_PROJECTS_DETAIL_ENDPOINT,
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path=EDA_PROJECTS_LIST_ENDPOINT,
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
            "sync": EndpointOperation(
                path=EDA_PROJECTS_SYNC_ENDPOINT,
                method="POST",
                fields=[],
                path_params=["id"],
                required_for="sync",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        """Return the field used for existence checks."""
        return "name"

    @classmethod
    def get_find_list_query_params(cls, api_data) -> Dict[str, Any]:
        """Use the EDA project list contract, which looks projects up by name."""
        return {}

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleEdaProject":
        """Transform from API format to Ansible format."""
        ansible_data = {
            "name": api_data.get("name", ""),
            "description": api_data.get("description"),
            "url": api_data.get("url"),
            "proxy": api_data.get("proxy"),
            "scm_branch": api_data.get("scm_branch"),
            "update_revision_on_launch": api_data.get("update_revision_on_launch"),
            "scm_update_cache_timeout": api_data.get("scm_update_cache_timeout"),
            "id": api_data.get("id"),
        }

        manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
        credential = _related_resource_name(manager, api_data, "eda_credential_id", "eda_credential", "eda-credentials", "eda")
        organization = _related_resource_name(manager, api_data, "organization_id", "organization", "organizations", "eda")
        if credential is not None:
            ansible_data["credential"] = credential
        if organization is not None:
            ansible_data["organization_name"] = organization

        return AnsibleEdaProject(**ansible_data)
