"""Controller API v2 representation of organization configuration fields."""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

BASE_PATH = "/api/controller/v2/organizations"


@dataclass
class APIControllerOrganization_v2(BaseTransformMixin):
    """API v2 fields used to update an existing Controller organization."""

    name: Optional[str] = None
    default_environment: Optional[Any] = None
    max_hosts: Optional[int] = None
    id: Optional[int] = None


class ControllerOrganizationTransformMixin_v2(BaseTransformMixin):
    """Transform Controller organization configuration fields."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIControllerOrganization_v2:
        """Build a sparse Controller update payload from supplied settings.

        Resolve a named default execution environment to its Controller ID
        when a manager is available. Unspecified values are omitted so the
        update leaves the current Controller settings unchanged.

        Args:
            ansible_instance: Ansible organization model with requested fields.
            context: Transform context or mapping containing the API manager.

        Returns:
            APIControllerOrganization_v2: Controller update data.

        Raises:
            ValueError: If a named default execution environment cannot be found.
        """
        api_data: Dict[str, Any] = {}
        name = getattr(ansible_instance, "name", None)
        if name is not None:
            api_data["name"] = name

        default_environment = getattr(ansible_instance, "default_environment", None)
        if default_environment is not None:
            value = str(default_environment).strip()
            if value.isdigit():
                api_data["default_environment"] = int(value)
            elif value and not value.startswith("/"):
                manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
                if manager is not None:
                    environment_id = manager.lookup_resource_id("execution_environments", "name", default_environment, service="controller")
                    if environment_id is None:
                        raise ValueError("Could not resolve Controller execution environment %r" % default_environment)
                    api_data["default_environment"] = environment_id
                else:
                    api_data["default_environment"] = default_environment
            else:
                # Preserve URL-like or empty values for the Controller API to validate.
                api_data["default_environment"] = default_environment

        max_hosts = getattr(ansible_instance, "max_hosts", None)
        if max_hosts is not None:
            api_data["max_hosts"] = max_hosts

        resource_id = getattr(ansible_instance, "id", None)
        if resource_id is not None:
            api_data["id"] = resource_id

        return APIControllerOrganization_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Expose read and update operations only; Gateway owns lifecycle."""
        return {
            "update": EndpointOperation(
                path=BASE_PATH + "/{id}/",
                method="PATCH",
                fields=["default_environment", "max_hosts"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "get": EndpointOperation(path=BASE_PATH + "/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path=BASE_PATH + "/", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        """Return the field used to look up Controller organizations."""
        return "name"

    @classmethod
    def get_find_list_query_params(cls, api_data: APIControllerOrganization_v2) -> Dict[str, Any]:
        """Scope a name lookup to Controller's organization endpoint."""
        return {"name": api_data.name} if api_data.name is not None else {}

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "AnsibleControllerOrganization":
        """Return Controller organization fields without mixing Gateway IDs."""
        from ....ansible_models.controller_organization import AnsibleControllerOrganization

        default_environment = api_data.get("default_environment")
        if isinstance(default_environment, dict):
            default_environment = default_environment.get("id")
        return AnsibleControllerOrganization(
            name=api_data.get("name"),
            default_environment=str(default_environment) if default_environment is not None else None,
            max_hosts=api_data.get("max_hosts"),
            id=api_data.get("id"),
        )
