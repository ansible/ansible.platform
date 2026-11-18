"""Shared type definitions for the platform collection.

This module contains dataclasses and type definitions used throughout
the framework.
"""

from dataclasses import asdict, dataclass, is_dataclass
from dataclasses import field as dataclass_field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

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
        required_fields: Update fields that must be included even when not explicitly set

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
    required_fields: Set[str] = dataclass_field(default_factory=set)


@dataclass
class SingletonMutationPlan:
    """Ordered endpoint-operation names and the predicted public result.

    Resource mixins decide which steps are needed. The shared client executes
    the declared steps, or returns only the prediction in check mode.
    """

    operations: List[str]
    result: Dict[str, Any]
    api_data: Optional[Any] = None


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
        force_update: When True, skip idempotency short-circuiting for an intentional update such as
            resetting a write-only secret that the API represents with an encrypted placeholder.
        check_mode: Predict a supported singleton mutation without sending writes.
        current_api_data: Raw API resource currently being transformed, used by idempotency checks
            that need server-side foreign-key IDs after public fields are converted to names.
    """

    manager: "PlatformService"
    session: "Session"
    cache: Dict[str, Any]
    api_version: str
    service: str = "gateway"
    operation: Optional[str] = None
    include_nulls_for_update: bool = False
    force_update: bool = False
    current_api_data: Optional[Dict[str, Any]] = None
    check_mode: bool = False


def build_endpoint_request(
    operation: EndpointOperation,
    api_data: Any,
    context: Optional[TransformContext] = None,
    *,
    path_values: Optional[Dict[str, Any]] = None,
    fields_to_null: Optional[Set[str]] = None,
    omit_empty_strings: bool = False,
) -> tuple[str, Any]:
    """Build an endpoint path and body from API data and operation metadata.

    Both CRUD execution and action-oriented operations use this function so
    endpoint field declarations remain the source of request bodies.

    Args:
        operation: Endpoint declaration providing path parameters, fields, and
            optional flattened-body behavior.
        api_data: API dataclass or mapping produced by the transform.
        context: Request context used for update null semantics.
        path_values: Optional values from prior operations. These override
            values on ``api_data`` when resolving path parameters.
        fields_to_null: Fields that must be sent as explicit nulls.
        omit_empty_strings: Omit empty strings outside updates. Explicit update
            values, including empty strings, are retained.

    Returns:
        A tuple of the resolved endpoint path and request body.
    """
    if is_dataclass(api_data):
        data = asdict(api_data)
    elif isinstance(api_data, dict):
        data = api_data
    else:
        raise TypeError("API request data must be a dataclass or dict")

    resolved_values = dict(data)
    if path_values:
        resolved_values.update(path_values)

    path = operation.path
    for parameter in operation.path_params or []:
        value = resolved_values.get(parameter)
        if value is not None:
            path = path.replace("{%s}" % parameter, str(value))

    request_data = {}
    null_fields = fields_to_null or set()
    operation_name = context.operation if context is not None else None
    include_nulls_for_update = context.include_nulls_for_update if context is not None else False
    for field in operation.fields or []:
        if field not in data:
            continue
        value = data[field]
        if value is None:
            if field in null_fields or (operation_name == "update" and include_nulls_for_update and field in {"organization", "credential"}):
                request_data[field] = None
            continue
        if omit_empty_strings and value == "" and operation_name != "update":
            continue
        request_data[field] = value

    if operation.flatten_body and len(request_data) == 1:
        request_data = next(iter(request_data.values()))

    return path, request_data
