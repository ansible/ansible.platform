"""
API v2 ExecutionEnvironment dataclass and transform mixin.

Handles transformations between Ansible format and Controller API v2 format.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


def lookup_execution_environment_id(manager, name, organization_id=None, service="controller"):
    """Resolve an execution environment name, preferring the requested organization.

    Controller allows global execution environments with a null organization.
    When an organization is supplied, search matching names once, select a
    unique organization match first, then fall back to a unique global match.
    """
    if str(name).strip().isdigit():
        return int(name)

    lookup_kwargs = {"service": service, "require_unique": True}
    if organization_id is None or "++" in str(name):
        if organization_id is not None:
            lookup_kwargs["extra_query_params"] = {"organization": organization_id}
        return manager.lookup_resource_id("execution_environments", "name", name, **lookup_kwargs)

    response = manager.search_api("execution_environments", query_params={"name": name}, return_all=True, service=service)
    results = [item for item in response.get("results", []) if item.get("name") == name]

    def relationship_id(value):
        if isinstance(value, dict):
            value = value.get("id")
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return value

    requested_organization = relationship_id(organization_id)
    organization_matches = [item for item in results if relationship_id(item.get("organization")) == requested_organization]
    global_matches = [item for item in results if item.get("organization") is None]
    matches = organization_matches or global_matches

    if not matches:
        raise ValueError("Resource 'execution_environments' with name=%s not found" % name)
    if len(matches) > 1:
        scope = "organization %s" % organization_id if organization_matches else "global scope"
        raise ValueError("Execution environment %r matched multiple resources in %s" % (name, scope))

    resource_id = matches[0].get("id")
    if resource_id is None:
        raise ValueError("Execution environment %r lookup did not return an ID" % name)
    return resource_id


@dataclass
class APIExecutionEnvironment_v2(BaseTransformMixin):
    """API v2 representation of a Controller execution environment."""

    name: Optional[str] = None
    image: Optional[str] = None
    description: Optional[str] = None
    organization: Optional[int] = None
    credential: Optional[int] = None
    pull: Optional[str] = None

    # Read-only fields from API
    id: Optional[int] = None


class ExecutionEnvironmentTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for ExecutionEnvironment API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APIExecutionEnvironment_v2":
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

        manager = getattr(context, "manager", None) if isinstance(context, TransformContext) else context.get("manager")

        # Resolve the organization in Controller's ID space for this Controller FK.
        organization = getattr(ansible_instance, "organization", None)
        organization_id = None
        if organization is not None:
            if manager is not None and not str(organization).strip().isdigit():
                organization_id = manager.lookup_resource_id("organizations", "name", organization, service="controller")
            else:
                organization_id = int(organization) if organization is not None else None
            if organization_id is None:
                raise ValueError("Could not resolve organization %r to an ID" % organization)
            api_data["organization"] = organization_id
        organization_scope = {"organization": organization_id} if organization_id is not None else None
        lookup_kwargs: Dict[str, Any] = {"service": "controller"}
        if organization_scope:
            lookup_kwargs["extra_query_params"] = organization_scope

        # FK resolution: credential (Controller-owned)
        credential = getattr(ansible_instance, "credential", None)
        if credential is not None:
            if manager is not None and not str(credential).strip().isdigit():
                api_data["credential"] = manager.lookup_resource_id("credentials", "name", credential, **lookup_kwargs)
            else:
                api_data["credential"] = int(credential) if credential is not None else None

        for field in ("image", "description", "pull"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
            elif op == "update" and include_nulls and field == "description":
                api_data[field] = ""

        # Read-only from API (for building URL in execute)
        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIExecutionEnvironment_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/execution_environments/",
                method="POST",
                fields=["name", "image", "description", "organization", "credential", "pull"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/controller/v2/execution_environments/{id}/",
                method="PATCH",
                fields=["name", "image", "description", "organization", "credential", "pull"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/controller/v2/execution_environments/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/execution_environments/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/controller/v2/execution_environments/",
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
        from ....ansible_models.execution_environment import AnsibleExecutionEnvironment

        organization_val = api_data.get("organization")
        organization_str = str(organization_val) if organization_val is not None else None

        credential_val = api_data.get("credential")
        credential_str = str(credential_val) if credential_val is not None else None

        return AnsibleExecutionEnvironment(
            name=api_data.get("name", ""),
            image=api_data.get("image"),
            description=api_data.get("description"),
            organization=organization_str,
            credential=credential_str,
            pull=api_data.get("pull"),
            id=api_data.get("id"),
        )
