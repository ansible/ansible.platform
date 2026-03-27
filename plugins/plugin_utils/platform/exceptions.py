"""
Error Taxonomy for Platform Collection.

This module defines a hierarchy of exceptions for platform operations,
enabling proper error classification and retry logic.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PlatformError(Exception):
    """
    Base exception for all platform-related errors.

    All platform exceptions inherit from this class, allowing
    catch-all error handling when needed.
    """

    def __init__(self, message: str, operation: Optional[str] = None, resource: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize platform error.

        Args:
            message: Human-readable error message
            operation: Operation that failed (e.g., 'create', 'update', 'find')
            resource: Resource type (e.g., 'user', 'organization')
            details: Additional error details (e.g., HTTP status, response body)
        """
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.resource = resource
        self.details = details or {}

    def __str__(self) -> str:
        """Return formatted error message."""
        parts = [self.message]
        if self.operation:
            parts.append(f"Operation: {self.operation}")
        if self.resource:
            parts.append(f"Resource: {self.resource}")
        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert error to dictionary for serialization.

        Returns:
            Dictionary representation of error
        """
        return {"error_type": self.__class__.__name__, "message": self.message, "operation": self.operation, "resource": self.resource, "details": self.details}


class AuthenticationError(PlatformError):
    """
    Authentication failures.

    Raised when:
    - Invalid credentials provided
    - Token expired and refresh failed
    - Authentication endpoint returns 401/403
    """

    def __init__(self, message: str, operation: Optional[str] = None, resource: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, operation, resource, details)
        self.retryable = False  # Authentication errors are not retryable

    def get_suggestion(self) -> str:
        """Get suggestion for fixing authentication error."""
        if "token" in self.message.lower() or "expired" in self.message.lower():
            return "Check if token has expired. Provide a valid token or refresh token."
        elif "password" in self.message.lower() or "username" in self.message.lower():
            return "Verify username and password are correct."
        else:
            return "Check gateway credentials (username/password or token) are valid and have proper permissions."


class NetworkError(PlatformError):
    """
    Network/connection failures (retryable).

    Raised when:
    - Connection timeout
    - DNS resolution failure
    - Connection refused
    - Network unreachable
    - SSL/TLS errors (connection-level)
    """

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(message, operation, resource, details)
        self.retryable = True  # Network errors are retryable
        self.original_exception = original_exception

    def get_suggestion(self) -> str:
        """Get suggestion for fixing network error."""
        if "timeout" in self.message.lower():
            return "Check network connectivity and gateway availability. Consider increasing timeout."
        elif "connection" in self.message.lower() or "refused" in self.message.lower():
            return "Verify gateway URL is correct and gateway service is running."
        elif "dns" in self.message.lower() or "resolve" in self.message.lower():
            return "Check DNS resolution for gateway hostname."
        elif "ssl" in self.message.lower() or "tls" in self.message.lower():
            return "Verify SSL certificate is valid. Use gateway_validate_certs=false for testing only."
        else:
            return "Check network connectivity and gateway availability."


class ValidationError(PlatformError):
    """
    Input validation errors (not retryable).

    Raised when:
    - Invalid input parameters
    - Missing required fields
    - Invalid data format
    - Constraint violations
    """

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        invalid_fields: Optional[list] = None,
    ):
        super().__init__(message, operation, resource, details)
        self.retryable = False  # Validation errors are not retryable
        self.invalid_fields = invalid_fields or []

    def get_suggestion(self) -> str:
        """Get suggestion for fixing validation error."""
        if self.invalid_fields:
            fields_str = ", ".join(self.invalid_fields)
            return f"Check the following fields are valid: {fields_str}"
        else:
            return "Review input parameters and ensure all required fields are provided with valid values."


class APIError(PlatformError):
    """
    API-level errors (may be retryable).

    Raised when:
    - HTTP 4xx errors (client errors, may be retryable for some)
    - HTTP 5xx errors (server errors, usually retryable)
    - API returns error response
    - Rate limiting (429)
    """

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
        response_body: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, operation, resource, details)
        self.status_code = status_code
        self.response_body = response_body or {}

        # Determine if retryable based on status code
        if status_code:
            # 5xx errors are retryable (server errors)
            # 429 (rate limit) is retryable
            # 408 (timeout) is retryable
            # 4xx errors (except above) are generally not retryable
            self.retryable = status_code >= 500 or status_code in [408, 429]
        else:
            self.retryable = False

    def get_suggestion(self) -> str:
        """Get suggestion for fixing API error."""
        if self.status_code == 401:
            return "Authentication failed. Check credentials are valid and have proper permissions."
        elif self.status_code == 403:
            return "Access forbidden. Check user has required permissions for this operation."
        elif self.status_code == 404:
            return "Resource not found. Verify the resource exists or check the resource identifier."
        elif self.status_code == 409:
            return "Conflict. Resource may already exist or be in use. Check for duplicate resources."
        elif self.status_code == 422:
            return "Validation error. Check input parameters and required fields."
        elif self.status_code == 429:
            return "Rate limit exceeded. Wait before retrying or reduce request frequency."
        elif self.status_code >= 500:
            return "Server error. This may be temporary. Retry the operation."
        else:
            return "Check API response for details and verify input parameters."


class TimeoutError(PlatformError):
    """
    Operation timeout errors (retryable).

    Raised when:
    - Request timeout exceeded
    - Operation takes too long
    """

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        timeout_seconds: Optional[float] = None,
    ):
        super().__init__(message, operation, resource, details)
        self.retryable = True  # Timeout errors are retryable
        self.timeout_seconds = timeout_seconds

    def get_suggestion(self) -> str:
        """Get suggestion for fixing timeout error."""
        if self.timeout_seconds:
            return f"Operation timed out after {self.timeout_seconds}s. Consider increasing gateway_request_timeout or check network/gateway performance."
        else:
            return "Operation timed out. Consider increasing gateway_request_timeout or check network/gateway performance."


def classify_exception(exception: Exception, operation: Optional[str] = None, resource: Optional[str] = None) -> PlatformError:
    """
    Classify a generic exception into platform error taxonomy.

    Args:
        exception: Exception to classify
        operation: Operation that failed
        resource: Resource type

    Returns:
        Classified PlatformError
    """
    import requests

    # If already a PlatformError, return as-is
    if isinstance(exception, PlatformError):
        return exception

    # Classify based on exception type
    if isinstance(exception, requests.exceptions.Timeout):
        return TimeoutError(
            message=f"Request timed out: {str(exception)}",
            operation=operation,
            resource=resource,
            details={"original_exception": str(exception)},
            timeout_seconds=getattr(exception, "timeout", None),
        )

    elif isinstance(exception, requests.exceptions.ConnectionError):
        return NetworkError(
            message=f"Connection error: {str(exception)}",
            operation=operation,
            resource=resource,
            details={"original_exception": str(exception)},
            original_exception=exception,
        )

    elif isinstance(exception, requests.exceptions.SSLError):
        return NetworkError(
            message=f"SSL error: {str(exception)}",
            operation=operation,
            resource=resource,
            details={"original_exception": str(exception), "error_type": "ssl"},
            original_exception=exception,
        )

    elif isinstance(exception, ValueError) and ("auth" in str(exception).lower() or "credential" in str(exception).lower()):
        return AuthenticationError(
            message=f"Authentication error: {str(exception)}", operation=operation, resource=resource, details={"original_exception": str(exception)}
        )

    elif isinstance(exception, ValueError):
        return ValidationError(
            message=f"Validation error: {str(exception)}", operation=operation, resource=resource, details={"original_exception": str(exception)}
        )

    else:
        # Generic platform error for unclassified exceptions
        return PlatformError(
            message=f"Unexpected error: {str(exception)}",
            operation=operation,
            resource=resource,
            details={"original_exception": str(exception), "exception_type": type(exception).__name__},
        )
