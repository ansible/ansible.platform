"""Shared type definitions for the platform collection.

This module contains dataclasses and type definitions used throughout
the framework.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from requests import Session

    from ..manager.platform_manager import PlatformService


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
    flatten_body: bool = False  # If True, send dict field value as the body directly (for singletons)


@dataclass
class TransformContext:
    """
    Context for data transformations between Ansible and API formats.

    This dataclass provides type-safe access to transformation context
    instead of using Dict[str, Any], which improves mypy type checking.

    Attributes:
        manager: PlatformService instance for lookups and API operations
        session: HTTP session for making requests
        cache: Lookup cache (e.g., org names ↔ IDs)
        api_version: Current API version string
        operation: Optional operation name ('create', 'update', etc.).
        include_nulls_for_update: When True and operation is 'update', transforms include null
            for optional fields so the API can clear them (enforced state only; present must not send nulls).
    """

    manager: "PlatformService"
    session: "Session"
    cache: Dict[str, Any]
    api_version: str
    operation: Optional[str] = None
    include_nulls_for_update: bool = False
