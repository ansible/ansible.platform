"""
Retry Logic for Platform Operations.

This module provides retry decorators and utilities for handling
transient failures with exponential backoff.
"""

import logging
import time
import functools
from typing import Callable, TypeVar, Optional, Dict, Any
from .exceptions import PlatformError, NetworkError, APIError

logger = logging.getLogger(__name__)

T = TypeVar('T')

class RetryConfig:
    """
    Configuration for retry behavior.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        """
        Initialize retry configuration.

        Args:
            max_attempts: Maximum number of retry attempts (default: 3)
            initial_delay: Initial delay in seconds (default: 1.0)
            max_delay: Maximum delay in seconds (default: 60.0)
            exponential_base: Base for exponential backoff (default: 2.0)
            jitter: Whether to add random jitter to delays (default: True)
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for retry attempt.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: delay = initial_delay * (base ^ attempt)
        delay = self.initial_delay * (self.exponential_base ** attempt)

        # Cap at max_delay
        delay = min(delay, self.max_delay)

        # Add jitter to prevent thundering herd
        if self.jitter:
            import random
            jitter_amount = delay * 0.1  # 10% jitter
            delay = delay + random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay)  # Ensure non-negative

        return delay

# Default retry configuration
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True
)

def retry_on_failure(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: Optional[tuple] = None
) -> Callable:
    """
    Decorator for retrying operations on transient failures.

    Args:
        config: Retry configuration (uses default if not provided)
        retryable_exceptions: Tuple of exception types to retry (default: PlatformError)

    Returns:
        Decorated function with retry logic
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG

    if retryable_exceptions is None:
        retryable_exceptions = (PlatformError,)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            operation = kwargs.get('operation') or getattr(args[0] if args else None, 'operation', 'unknown')
            resource = kwargs.get('resource') or getattr(args[0] if args else None, 'resource', 'unknown')

            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Check if exception is retryable
                    is_retryable = False
                    if isinstance(e, PlatformError):
                        is_retryable = getattr(e, 'retryable', False)
                    elif isinstance(e, retryable_exceptions):
                        is_retryable = True

                    # Don't retry if not retryable or last attempt
                    if not is_retryable or attempt == config.max_attempts - 1:
                        logger.debug(
                            f"Not retrying {func.__name__} (attempt {attempt + 1}/{config.max_attempts}): "
                            f"retryable={is_retryable}, exception={type(e).__name__}"
                        )
                        raise

                    # Calculate delay for next retry
                    delay = config.calculate_delay(attempt)

                    logger.warning(
                        f"Retrying {func.__name__} (attempt {attempt + 1}/{config.max_attempts}) "
                        f"after {delay:.2f}s: {type(e).__name__}: {str(e)}"
                    )

                    # Wait before retry
                    time.sleep(delay)

            # If we get here, all retries failed
            if last_exception:
                raise last_exception

            # Should never reach here, but just in case
            raise RuntimeError(f"Retry logic failed for {func.__name__}")

        return wrapper
    return decorator

def retry_http_request(
    config: Optional[RetryConfig] = None
) -> Callable:
    """
    Decorator specifically for HTTP requests with retry logic.

    This decorator handles:
    - Network errors (retryable)
    - Timeout errors (retryable)
    - 5xx server errors (retryable)
    - 429 rate limit errors (retryable)
    - 4xx client errors (not retryable, except 408, 429)

    Args:
        config: Retry configuration (uses default if not provided)

    Returns:
        Decorated function with HTTP retry logic
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            import requests
            from .exceptions import (
                NetworkError, TimeoutError, APIError, classify_exception
            )

            last_exception = None
            operation = kwargs.get('operation', 'http_request')
            resource = kwargs.get('resource', 'unknown')

            for attempt in range(config.max_attempts):
                try:
                    response = func(*args, **kwargs)

                    # Check for HTTP error status codes
                    if hasattr(response, 'status_code'):
                        status_code = response.status_code

                        # Retry on 5xx errors or specific 4xx errors
                        if status_code >= 500 or status_code in [408, 429]:
                            # Create APIError for retryable status codes
                            error = APIError(
                                message=f"HTTP {status_code} error",
                                operation=operation,
                                resource=resource,
                                details={'status_code': status_code},
                                status_code=status_code
                            )

                            # Check if we should retry
                            if error.retryable and attempt < config.max_attempts - 1:
                                delay = config.calculate_delay(attempt)
                                logger.warning(
                                    f"Retrying HTTP request (attempt {attempt + 1}/{config.max_attempts}) "
                                    f"after {delay:.2f}s: HTTP {status_code}"
                                )
                                time.sleep(delay)
                                continue
                            else:
                                raise error

                    return response

                except (requests.exceptions.Timeout, TimeoutError) as e:
                    last_exception = e
                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"Retrying HTTP request (attempt {attempt + 1}/{config.max_attempts}) "
                            f"after {delay:.2f}s: Timeout error"
                        )
                        time.sleep(delay)
                        continue
                    else:
                        raise TimeoutError(
                            message=f"Request timed out after {config.max_attempts} attempts: {str(e)}",
                            operation=operation,
                            resource=resource,
                            details={'original_exception': str(e)},
                            timeout_seconds=getattr(e, 'timeout', None)
                        )

                except (requests.exceptions.ConnectionError, requests.exceptions.SSLError, NetworkError) as e:
                    last_exception = e
                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"Retrying HTTP request (attempt {attempt + 1}/{config.max_attempts}) "
                            f"after {delay:.2f}s: Network error"
                        )
                        time.sleep(delay)
                        continue
                    else:
                        if isinstance(e, NetworkError):
                            raise
                        else:
                            raise NetworkError(
                                message=f"Network error after {config.max_attempts} attempts: {str(e)}",
                                operation=operation,
                                resource=resource,
                                details={'original_exception': str(e)},
                                original_exception=e
                            )

                except Exception as e:
                    # Classify exception and check if retryable
                    platform_error = classify_exception(e, operation, resource)

                    if platform_error.retryable and attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"Retrying HTTP request (attempt {attempt + 1}/{config.max_attempts}) "
                            f"after {delay:.2f}s: {type(e).__name__}"
                        )
                        time.sleep(delay)
                        continue
                    else:
                        raise platform_error

            # If we get here, all retries failed
            if last_exception:
                raise last_exception

            raise RuntimeError(f"Retry logic failed for {func.__name__}")

        return wrapper
    return decorator

def retry_with_backoff(max_retries=3, delay=1, backoff=2):
    """
    Decorator to retry function on NetworkError or APIError.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            while True:
                try:
                    return func(*args, **kwargs)
                except (NetworkError, APIError) as e:
                    if retries >= max_retries:
                        logger.error(f"Max retries ({max_retries}) reached for {func.__name__}. Error: {e}")
                        raise e
                    retries += 1
                    logger.warning(
                        f"Transient error in {func.__name__}: {e}. "
                        f"Retrying in {current_delay} seconds - ({retries}/{max_retries})"
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator