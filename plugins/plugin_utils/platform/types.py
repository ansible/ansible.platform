"""Shared type definitions for the platform collection.

This module contains dataclasses and type definitions used throughout
the framework.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, List, Optional

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
        path_param_aliases: Optional mapping of path param → list of aliases
        required_for: Optional operation type this is required for
            ('create', 'update', 'delete', or None for always)
        depends_on: Optional name of operation this depends on
        order: Execution order (lower runs first)
        flatten_body: If True, send dict field value as the body directly (for singletons)
    """

    path: str
    method: str
    fields: List[str]
    path_params: Optional[List[str]] = None
    path_param_aliases: Optional[Dict[str, List[str]]] = None
    required_for: Optional[str] = None
    depends_on: Optional[str] = None
    order: int = 0
    flatten_body: bool = False


@dataclass
class ResourceModuleStates:
    """Declares which resource module states a resource supports.

    Used by the base action plugin to validate the ``state`` parameter
    and by DOCUMENTATION generation.

    Attributes:
        merged: Additive create/update (C' = C ∪ D)
        replaced: Item-level replacement (C' = (C \\ K(D)) ∪ D)
        overridden: Set equality (C' = D), deletes extras
        deleted: Set difference (C' = C \\ D)
        gathered: Read-only state gathering
    """

    merged: bool = True
    replaced: bool = True
    overridden: bool = True
    deleted: bool = True
    gathered: bool = True

    @property
    def as_frozenset(self) -> FrozenSet[str]:
        """Return the enabled states as a frozenset of strings."""
        states = set()
        for attr in ("merged", "replaced", "overridden", "deleted", "gathered"):
            if getattr(self, attr):
                states.add(attr)
        return frozenset(states)


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
            for optional fields so the API can clear them (replaced/overridden states).
    """

    manager: "PlatformService"
    session: "Session"
    cache: Dict[str, Any]
    api_version: str
    operation: Optional[str] = None
    include_nulls_for_update: bool = False
