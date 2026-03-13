"""
API v2 Organization dataclass and transform mixin.

Mirrors v1 for Gateway v2 endpoint paths (when available).
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIOrganization_v2(BaseTransformMixin):
    """API v2 representation of an organization."""

    name: str
    description: Optional[str] = None
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class OrganizationTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for Organization API v2. Mirrors v1 with v2 paths."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> 'APIOrganization_v2':
        op = getattr(context, 'operation', None) if isinstance(context, TransformContext) else context.get('operation')
        include_nulls = getattr(context, 'include_nulls_for_update', False) if isinstance(context, TransformContext) else context.get('include_nulls_for_update', False)
        api_data = {}
        name = getattr(ansible_instance, 'name', None)
        new_name = getattr(ansible_instance, 'new_name', None)
        description = getattr(ansible_instance, 'description', None)

        if op == 'create':
            api_data['name'] = name or new_name
        elif op == 'update':
            api_data['name'] = new_name if new_name is not None else (name or '')
        if description is not None:
            api_data['description'] = description
        elif op == 'update' and include_nulls:
            api_data['description'] = ''
        for field in ('id', 'created', 'modified', 'url'):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
        return APIOrganization_v2(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            'create': EndpointOperation(path='/api/gateway/v2/organizations/', method='POST', fields=['name', 'description'], required_for='create', order=1),
            'update': EndpointOperation(path='/api/gateway/v2/organizations/{id}/', method='PATCH', fields=['name', 'description'], path_params=['id'], required_for='update', order=1),
            'delete': EndpointOperation(path='/api/gateway/v2/organizations/{id}/', method='DELETE', fields=[], path_params=['id'], required_for='delete', order=1),
            'get': EndpointOperation(path='/api/gateway/v2/organizations/{id}/', method='GET', fields=[], path_params=['id'], required_for='find', order=1),
            'list': EndpointOperation(path='/api/gateway/v2/organizations/', method='GET', fields=[], required_for='find', order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return 'name'

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> 'AnsibleOrganization':
        from ...ansible_models.organization import AnsibleOrganization
        return AnsibleOrganization(
            name=api_data.get('name', ''),
            description=api_data.get('description'),
            id=api_data.get('id'),
            created=api_data.get('created'),
            modified=api_data.get('modified'),
            url=api_data.get('url'),
        )
