"""Shared type definitions for the platform collection.

This module contains dataclasses and type definitions used throughout
the framework.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class EndpointOperation:
    """
    Configuration for a single API endpoint operation.
    
    Defines how to call a specific API endpoint, what data to send,
    and how it relates to other operations.
    
    Attributes:
        path: API endpoint path (e.g., '/api/gateway/v1/users/')
        method: HTTP method ('GET', 'POST', 'PATCH', 'DELETE')
        fields: List of dataclass field names to include in request
        path_params: Optional list of path parameter names (e.g., ['id'])
        required_for: Optional operation type this is required for
            ('create', 'update', 'delete', or None for always)
        depends_on: Optional name of operation this depends on
        order: Execution order (lower runs first)
    
    Examples:
        >>> # Main create operation
        >>> EndpointOperation(
        ...     path='/api/gateway/v1/users/',
        ...     method='POST',
        ...     fields=['username', 'email'],
        ...     order=1
        ... )
        
        >>> # Dependent operation (runs after create)
        >>> EndpointOperation(
        ...     path='/api/gateway/v1/users/{id}/organizations/',
        ...     method='POST',
        ...     fields=['organizations'],
        ...     path_params=['id'],
        ...     depends_on='create',
        ...     order=2
        ... )
    """
    
    path: str
    method: str
    fields: List[str]
    path_params: Optional[List[str]] = None
    required_for: Optional[str] = None
    depends_on: Optional[str] = None
    order: int = 0


