"""
API v1 User dataclass and transform mixin.

Handles transformations between Ansible format and Gateway API v1 format.
"""

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, ClassVar, Union
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
    is_platform_auditor: Optional[bool] = None

    # Read-only fields from API
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None

    # For organizations - handled separately via associations
    organization_ids: Optional[List[int]] = None

class UserTransformMixin_v1(BaseTransformMixin):
    """
    Transform mixin for User API v1.

    Defines how to transform between Ansible format and API v1 format.
    """

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> 'APIUser_v1':
        """
        Create API instance from Ansible dataclass.

        Args:
            ansible_instance: AnsibleUser instance
            context: TransformContext or dict with manager

        Returns:
            APIUser_v1 instance
        """
        logger.info(f"Transforming AnsibleUser to APIUser_v1: username={getattr(ansible_instance, 'username', None)}")
        api_data = {}

        # Simple field mappings
        simple_fields = [
            'username', 'email', 'first_name', 'last_name',
            'password', 'is_superuser', 'is_platform_auditor',
            'id', 'created', 'modified', 'url'
        ]

        for field in simple_fields:
            value = getattr(ansible_instance, field, None)
            if value is not None:
                api_data[field] = value
                logger.debug(f"Mapped field {field}: {value}")

        # Complex transformation: organizations (names -> IDs)
        if ansible_instance.organizations:
            logger.debug(f"Transforming organizations from names to IDs: {ansible_instance.organizations}")
            org_ids = cls._names_to_ids(
                ansible_instance.organizations,
                context
            )
            api_data['organization_ids'] = org_ids
            logger.info(f"Organizations transformed: {ansible_instance.organizations} -> {org_ids}")

        logger.debug(f"APIUser_v1 data prepared with {len(api_data)} fields")
        return APIUser_v1(**api_data)

    @staticmethod
    def _names_to_ids(names: List[str], context: Union[TransformContext, Dict[str, Any]]) -> List[int]:
        """Convert organization names to IDs."""
        if not names:
            return []

        # Use manager to lookup IDs
        if isinstance(context, TransformContext):
            return context.manager.lookup_organization_ids(names)
        else:
            manager = context.get('manager')
            if manager:
                return manager.lookup_organization_ids(names)

        return []

    @staticmethod
    def _ids_to_names(ids: List[int], context: Union[TransformContext, Dict[str, Any]]) -> List[str]:
        """Convert organization IDs to names."""
        if not ids:
            logger.debug("No organization IDs to convert")
            return []

        logger.debug(f"Looking up organization names for IDs: {ids}")

        # Use manager to lookup names
        if isinstance(context, TransformContext):
            result = context.manager.lookup_organization_names(ids)
        else:
            manager = context.get('manager')
            if manager:
                result = manager.lookup_organization_names(ids)
            else:
                logger.warning("No manager in context for organization lookup")
                return []

        logger.info(f"Organization lookup completed: {ids} -> {result}")
        return result

    # Field mapping: ansible_field -> api_field or complex mapping
    _field_mapping: ClassVar[Dict[str, Any]] = {
        'username': 'username',
        'email': 'email',
        'first_name': 'first_name',
        'last_name': 'last_name',
        'password': 'password',
        'is_superuser': 'is_superuser',
        'is_platform_auditor': 'is_platform_auditor',
        'id': 'id',
        'created': 'created',
        'modified': 'modified',
        'url': 'url',

        # Complex mapping for organizations (names <-> IDs)
        'organizations': {
            'api_field': 'organization_ids',
            'forward_transform': 'names_to_ids',
            'reverse_transform': 'ids_to_names',
        },
    }

    # Transform functions registry
    # Note: context is normalized to TransformContext in base_transform._apply_transform
    _transform_registry: ClassVar[Dict[str, Any]] = {
        'names_to_ids': lambda names, ctx: ctx.manager.lookup_organization_ids(names) if names else [],
        'ids_to_names': lambda ids, ctx: ctx.manager.lookup_organization_names(ids) if ids else [],
    }

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """
        Define API endpoints for different operations.

        Returns:
            Dictionary mapping operation names to endpoint configurations
        """
        return {
            'create': EndpointOperation(
                path='/api/gateway/v1/users/',
                method='POST',
                fields=['username', 'email', 'first_name', 'last_name', 'password', 'is_superuser', 'is_platform_auditor'],
                required_for='create',
                order=1
            ),
            'update': EndpointOperation(
                path='/api/gateway/v1/users/{id}/',
                method='PATCH',
                fields=['username', 'email', 'first_name', 'last_name', 'password', 'is_superuser', 'is_platform_auditor'],
                path_params=['id'],
                required_for='update',
                order=1
            ),
            'delete': EndpointOperation(
                path='/api/gateway/v1/users/{id}/',
                method='DELETE',
                fields=[],
                path_params=['id'],
                required_for='delete',
                order=1
            ),
            'get': EndpointOperation(
                path='/api/gateway/v1/users/{id}/',
                method='GET',
                fields=[],
                path_params=['id'],
                required_for='find',
                order=1
            ),
            'list': EndpointOperation(
                path='/api/gateway/v1/users/',
                method='GET',
                fields=[],
                required_for='find',
                order=1
            ),
            # Secondary operation for organization associations
            'associate_organizations': EndpointOperation(
                path='/api/gateway/v1/users/{id}/organizations/',
                method='POST',
                fields=['organizations'],
                path_params=['id'],
                depends_on='create',
                required_for='create',
                order=2
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        """
        Return the field name used to look up existing resources.

        Returns:
            Field name for lookups (e.g., 'username', 'name')
        """
        return 'username'

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> 'AnsibleUser':
        """
        Transform from API format to Ansible format.

        Args:
            api_data: Data from API response (dict from API)
            context: TransformContext or dict with manager and other runtime info

        Returns:
            AnsibleUser dataclass instance (not dict - use asdict() if dict needed)
        """
        from ...ansible_models.user import AnsibleUser

        username = api_data.get('username', 'unknown')
        logger.info(f"Transforming APIUser_v1 to Ansible format: username={username}")
        logger.debug(f"API data keys: {list(api_data.keys())}")

        ansible_data = {}

        # Reverse mapping
        for ansible_field, mapping in cls._field_mapping.items():
            # Simple 1:1 mapping
            if isinstance(mapping, str):
                if mapping in api_data:
                    ansible_data[ansible_field] = api_data[mapping]
                    logger.debug(f"Mapped {mapping} -> {ansible_field}: {api_data[mapping]}")

            # Complex mapping with reverse transformation
            elif isinstance(mapping, dict):
                api_field = mapping['api_field']
                transform_name = mapping.get('reverse_transform')

                if api_field in api_data:
                    value = api_data[api_field]

                    if transform_name and transform_name in cls._transform_registry:
                        logger.debug(f"Applying reverse transform '{transform_name}' for {api_field} -> {ansible_field}")
                        transform_func = cls._transform_registry[transform_name]
                        # Normalize context for transform function (base_transform normalizes, but we handle both for safety)
                        if isinstance(context, dict):
                            # Convert dict to TransformContext for type safety
                            normalized_ctx = TransformContext(
                                manager=context['manager'],
                                session=context['session'],
                                cache=context.get('cache', {}),
                                api_version=context.get('api_version', '1')
                            )
                        else:
                            normalized_ctx = context
                        transformed_value = transform_func(value, normalized_ctx)
                        ansible_data[ansible_field] = transformed_value
                        logger.debug(f"Transform completed: {value} -> {transformed_value}")
                    else:
                        ansible_data[ansible_field] = value
                        logger.debug(f"Direct mapping {api_field} -> {ansible_field}: {value}")

        logger.info(f"Ansible format transformation completed with {len(ansible_data)} fields")
        # Return AnsibleUser dataclass instance, not dict
        return AnsibleUser(**ansible_data)
