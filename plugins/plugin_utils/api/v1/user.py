"""
API v1 User dataclass and transform mixin.

Handles transformations between Ansible format and Gateway API v1 format.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, ClassVar
from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation


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
    def from_ansible_data(cls, ansible_instance, context: Dict[str, Any]) -> 'APIUser_v1':
        """
        Create API instance from Ansible dataclass.
        
        Args:
            ansible_instance: AnsibleUser instance
            context: Context dict with manager
        
        Returns:
            APIUser_v1 instance
        """
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
        
        # Complex transformation: organizations (names -> IDs)
        if ansible_instance.organizations:
            api_data['organization_ids'] = cls._names_to_ids(
                ansible_instance.organizations,
                context
            )
        
        return APIUser_v1(**api_data)
    
    @staticmethod
    def _names_to_ids(names: List[str], context: Dict[str, Any]) -> List[int]:
        """Convert organization names to IDs."""
        if not names:
            return []
        
        # Use manager to lookup IDs
        manager = context.get('manager')
        if manager:
            return manager.lookup_organization_ids(names)
        
        return []
    
    @staticmethod
    def _ids_to_names(ids: List[int], context: Dict[str, Any]) -> List[str]:
        """Convert organization IDs to names."""
        if not ids:
            return []
        
        # Use manager to lookup names
        manager = context.get('manager')
        if manager:
            return manager.lookup_organization_names(ids)
        
        return []
    
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
    _transform_registry: ClassVar[Dict[str, Any]] = {
        'names_to_ids': lambda names, ctx: ctx['manager'].lookup_organization_ids(names) if names else [],
        'ids_to_names': lambda ids, ctx: ctx['manager'].lookup_organization_names(ids) if ids else [],
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
    
    def to_api(self, context: Dict[str, Any]) -> 'APIUser_v1':
        """
        Transform from Ansible format to API format.
        
        Args:
            context: Context dict with manager and other runtime info
            
        Returns:
            APIUser_v1 instance ready for API submission
        """
        api_data = {}
        
        # Apply field mappings
        for ansible_field, mapping in self._field_mapping.items():
            if not hasattr(self, ansible_field):
                continue
                
            value = getattr(self, ansible_field)
            if value is None:
                continue
            
            # Simple 1:1 mapping
            if isinstance(mapping, str):
                api_data[mapping] = value
            
            # Complex mapping with transformation
            elif isinstance(mapping, dict):
                api_field = mapping['api_field']
                transform_name = mapping.get('forward_transform')
                
                if transform_name and transform_name in self._transform_registry:
                    transform_func = self._transform_registry[transform_name]
                    api_data[api_field] = transform_func(value, context)
                else:
                    api_data[api_field] = value
        
        return APIUser_v1(**api_data)
    
    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform from API format to Ansible format.
        
        Args:
            api_data: Data from API response
            context: Context dict with manager and other runtime info
            
        Returns:
            Dictionary in Ansible format
        """
        ansible_data = {}
        
        # Reverse mapping
        for ansible_field, mapping in cls._field_mapping.items():
            # Simple 1:1 mapping
            if isinstance(mapping, str):
                if mapping in api_data:
                    ansible_data[ansible_field] = api_data[mapping]
            
            # Complex mapping with reverse transformation
            elif isinstance(mapping, dict):
                api_field = mapping['api_field']
                transform_name = mapping.get('reverse_transform')
                
                if api_field in api_data:
                    value = api_data[api_field]
                    
                    if transform_name and transform_name in cls._transform_registry:
                        transform_func = cls._transform_registry[transform_name]
                        ansible_data[ansible_field] = transform_func(value, context)
                    else:
                        ansible_data[ansible_field] = value
        
        return ansible_data

