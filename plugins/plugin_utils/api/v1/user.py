"""
API v1 User dataclass and transform mixin.

Handles transformations between Ansible format and Gateway API v1 format.
"""

import logging
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIUser_v1(BaseTransformMixin):
    """
    API v1 representation of a user.

    This dataclass knows how to transform to/from the Gateway API v1 format.
    """

    # API fields (snake_case as per API)
    username: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    is_superuser: Optional[bool] = None

    # Read-only fields from API
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None

    associated_authenticators: Optional[Dict[str, Any]] = None


class UserTransformMixin_v1(BaseTransformMixin):
    """
    Transform mixin for User API v1.

    Defines how to transform between Ansible format and API v1 format.
    """

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIUser_v1":
        """
        Create API instance from Ansible dataclass.

        Args:
            ansible_instance: AnsibleUser instance
            context: TransformContext or dict with manager

        Returns:
            APIUser_v1 instance
        """
        logger.info("Transforming AnsibleUser to APIUser_v1: username=%s", getattr(ansible_instance, "username", None))
        api_data = {}

        # Simple field mappings
        simple_fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "is_superuser",
            "id",
            "created",
            "modified",
            "url",
            "associated_authenticators",
        ]
        read_only = {"id", "created", "modified", "url"}
        # Only send null for these on enforced update; many APIs reject null for password/booleans
        clearable_string_fields = {"email", "first_name", "last_name"}
        op = getattr(context, "operation", None) if isinstance(context, TransformContext) else context.get("operation")
        include_nulls = (
            getattr(context, "include_nulls_for_update", False) if isinstance(context, TransformContext) else context.get("include_nulls_for_update", False)
        )

        for field in simple_fields:
            value = getattr(ansible_instance, field, None)
            if field == "password" and op == "update":
                # Never send password on update unless user set a new one (API rejects placeholder/read-only)
                if value and str(value).strip() and str(value) != "Password Disabled":
                    api_data[field] = value
                    logger.debug("Mapped field %s: (new password)", field)
                continue
            if value is not None:
                api_data[field] = value
                logger.debug("Mapped field %s: %s", field, value)
            elif op == "update" and include_nulls and field not in read_only and field in clearable_string_fields:
                # Enforced update only: send empty string to clear (Gateway API expects "" not null, per UI payload)
                api_data[field] = ""
                logger.debug("Mapped field %s: '' (enforced clear)", field)

        logger.debug("APIUser_v1 data prepared with %s fields", len(api_data))
        return APIUser_v1(**api_data)

    # Field mapping: ansible_field -> api_field or complex mapping
    _field_mapping: ClassVar[Dict[str, Any]] = {
        "username": "username",
        "email": "email",
        "first_name": "first_name",
        "last_name": "last_name",
        "password": "password",
        "is_superuser": "is_superuser",
        "associated_authenticators": "associated_authenticators",
        "id": "id",
        "created": "created",
        "modified": "modified",
        "url": "url",
    }

    # Transform functions registry
    _transform_registry: ClassVar[Dict[str, Any]] = {}

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """
        Define API endpoints for different operations.

        Returns:
            Dictionary mapping operation names to endpoint configurations
        """
        return {
            "create": EndpointOperation(
                path="/api/gateway/v1/users/",
                method="POST",
                fields=["username", "email", "first_name", "last_name", "password", "is_superuser"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/gateway/v1/users/{id}/",
                method="PATCH",
                # Omit username from body; resource is identified by URL (many APIs reject username in PATCH)
                fields=["email", "first_name", "last_name", "password", "is_superuser", "associated_authenticators"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(path="/api/gateway/v1/users/{id}/", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1),
            "get": EndpointOperation(path="/api/gateway/v1/users/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path="/api/gateway/v1/users/", method="GET", fields=[], required_for="find", order=1),
            # NOTE: Organization membership is managed from the organization side.
            # The spec exposes POST /organizations/{id}/users/associate/ and
            # /disassociate/ but NOT POST /users/{id}/organizations/.
            # The associate_organizations operation has been removed because
            # /users/{id}/organizations/ only supports GET in the spec.
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        """
        Return the field name used to look up existing resources.

        Returns:
            Field name for lookups (e.g., 'username', 'name')
        """
        return "username"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleUser":
        """
        Transform from API format to Ansible format.

        Args:
            api_data: Data from API response (dict from API)
            context: TransformContext or dict with manager and other runtime info

        Returns:
            AnsibleUser dataclass instance (not dict - use asdict() if dict needed)
        """
        from ...ansible_models.user import AnsibleUser

        username = api_data.get("username", "unknown")
        logger.info("Transforming APIUser_v1 to Ansible format: username=%s", username)
        logger.debug("API data keys: %s", list(api_data.keys()))

        ansible_data = {}

        # Reverse mapping
        for ansible_field, mapping in cls._field_mapping.items():
            # Simple 1:1 mapping
            if isinstance(mapping, str):
                if mapping in api_data:
                    ansible_data[ansible_field] = api_data[mapping]
                    logger.debug("Mapped %s -> %s: %s", mapping, ansible_field, api_data[mapping])

            # Complex mapping with reverse transformation
            elif isinstance(mapping, dict):
                api_field = mapping["api_field"]
                transform_name = mapping.get("reverse_transform")

                if api_field in api_data:
                    value = api_data[api_field]

                    if transform_name and transform_name in cls._transform_registry:
                        logger.debug("Applying reverse transform '%s' for %s -> %s", transform_name, api_field, ansible_field)
                        transform_func = cls._transform_registry[transform_name]
                        # Normalize context for transform function (base_transform normalizes, but we handle both for safety)
                        if isinstance(context, dict):
                            # Convert dict to TransformContext for type safety
                            normalized_ctx = TransformContext(
                                manager=context["manager"],
                                session=context["session"],
                                cache=context.get("cache", {}),
                                api_version=context.get("api_version", "1"),
                            )
                        else:
                            normalized_ctx = context
                        transformed_value = transform_func(value, normalized_ctx)
                        ansible_data[ansible_field] = transformed_value
                        logger.debug("Transform completed: %s -> %s", value, transformed_value)
                    else:
                        ansible_data[ansible_field] = value
                        logger.debug("Direct mapping %s -> %s: %s", api_field, ansible_field, value)

        logger.info("Ansible format transformation completed with %s fields", len(ansible_data))
        # Return AnsibleUser dataclass instance, not dict
        return AnsibleUser(**ansible_data)
