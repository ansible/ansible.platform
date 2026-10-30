"""API v1 EDA Project dataclass and transform mixin."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

# EDA project API endpoints
EDA_PROJECTS_LIST_ENDPOINT = "/api/eda/v1/projects/"
EDA_PROJECTS_DETAIL_ENDPOINT = "/api/eda/v1/projects/{id}/"
EDA_PROJECTS_SYNC_ENDPOINT = "/api/eda/v1/projects/{id}/sync/"


def _resolve_fk(manager, endpoint: str, lookup_field: str, value, service: str = "gateway") -> Optional[int]:
    """Resolve a name or id to an integer id.

    Returns the integer ID, or None if resolution fails.
    Exceptions are logged but not re-raised so callers can decide how to handle.
    """
    if value is None:
        return None
    if str(value).isdigit():
        return int(value)
    try:
        result = manager.lookup_resource_id(endpoint, lookup_field, str(value), service=service)
        if result is None:
            logger.debug("_resolve_fk: lookup_resource_id returned None for %s=%s in endpoint '%s'", lookup_field, value, endpoint)
        return result
    except Exception as exc:
        logger.debug("_resolve_fk: Failed to resolve %s=%s in endpoint '%s': %s: %s", lookup_field, value, endpoint, type(exc).__name__, exc)
        return None


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
        - organization_name (name) -> organization_id (int) via gateway organizations endpoint
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
        if credential is not None and manager:
            resolved = _resolve_fk(manager, "eda-credentials", "name", credential, service="eda")
            if resolved is not None:
                api_data["eda_credential_id"] = resolved
            else:
                raise ValueError("Could not resolve EDA credential '%s' to an ID" % credential)
        elif credential is not None and str(credential).isdigit():
            api_data["eda_credential_id"] = int(credential)

        # Resolve organization_name -> organization_id
        organization_name = getattr(ansible_instance, "organization_name", None)
        if organization_name is not None and manager:
            resolved = _resolve_fk(manager, "organizations", "name", organization_name, service="gateway")
            if resolved is not None:
                api_data["organization_id"] = resolved
            else:
                raise ValueError("Could not resolve organization '%s' to an ID" % organization_name)
        elif organization_name is not None and str(organization_name).isdigit():
            api_data["organization_id"] = int(organization_name)

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
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        """Return the field used for existence checks."""
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleEdaProject":
        """Transform from API format to Ansible format."""
        from ....ansible_models.eda_project import AnsibleEdaProject

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

        # Reverse-map eda_credential_id -> credential (as string ID for now)
        eda_credential_id = api_data.get("eda_credential_id")
        if eda_credential_id is not None:
            ansible_data["credential"] = str(eda_credential_id)

        # Reverse-map organization_id -> organization_name (as string ID for now)
        organization_id = api_data.get("organization_id")
        if organization_id is not None:
            ansible_data["organization_name"] = str(organization_id)

        return AnsibleEdaProject(**ansible_data)
