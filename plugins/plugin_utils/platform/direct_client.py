"""Direct HTTP Client - Standard connection mode.

This module provides a direct HTTP client for standard mode (default).
It uses direct requests.Session without a persistent manager process,
but shares all the same layers (version detection, error handling,
credential management, CRUD operations).
"""

import base64
import logging
import threading
import time
from typing import Any, Dict, Optional
import requests

from .base_client import BaseAPIClient
from .config import GatewayConfig
from .credential_manager import get_credential_manager, CredentialStore
from .exceptions import (
    PlatformError,
    AuthenticationError,
    NetworkError,
    APIError,
    TimeoutError,
    classify_exception
)
from .retry import retry_http_request, RetryConfig
from .types import TransformContext

logger = logging.getLogger(__name__)

class DirectHTTPClient(BaseAPIClient):
    """
    Direct HTTP client for standard connection mode.

    This is the default connection mode. It uses direct HTTP requests
    without a persistent manager process. Each task creates its own
    session, authenticates, and makes requests directly.

    All shared layers are used:
    - Version detection (APIVersionRegistry, DynamicClassLoader)
    - Error taxonomy (exceptions.py, retry.py)
    - Credential management (credential_manager.py)
    - CRUD operations (transform mixins, endpoint operations)
    - Optimizations (caching, lookup helpers)
    """

    def __init__(self, config: GatewayConfig):
        """
        Initialize direct HTTP client.

        Args:
            config: Gateway configuration
        """
        super().__init__(config)

        # Initialize credential manager and store credentials securely
        self.credential_manager = get_credential_manager()
        self.credential_store = self.credential_manager.get_or_create_store(
            gateway_url=self.base_url,
            username=config.username,
            password=config.password,
            oauth_token=config.oauth_token,
            process_id=str(id(self))  # Use object ID as process identifier
        )

        # Store namespace ID for credential operations
        self.namespace_id = self.credential_store.namespace.namespace_id

        # Get credentials from store (they're stored securely there)
        self.username, self.password, self.oauth_token = self.credential_store.get_auth_credentials()

        # Initialize session (new session for each client instance)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Ansible Platform Collection',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })

        # Track authentication state
        self._auth_lock = threading.Lock()
        self._last_auth_error = None

        # Performance counters
        self._http_request_count = 0
        self._tls_handshake_count = 1  # 1 handshake when session is created (HTTPS)
        self._lock = threading.Lock()

        # Retry configuration
        self.retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=True
        )

        # Authenticate (with error handling)
        try:
            self._authenticate()
            logger.info("DirectHTTPClient: Authentication successful")
        except Exception as e:
            logger.error(f"DirectHTTPClient: Authentication failed: {e}")
            self._last_auth_error = e
            raise

        # Detect API version
        try:
            self.api_version = self._detect_api_version()
            logger.info(f"DirectHTTPClient: Initialized with API v{self.api_version}")
        except Exception as e:
            logger.warning(f"DirectHTTPClient: Version detection failed: {e}, defaulting to v1")
            self.api_version = '1'

    def _detect_api_version(self) -> str:
        """
        Detect API version from platform.

        Returns:
            API version string (e.g., '1', '2')
        """
        try:
            # Try to get version from API
            response = self.session.get(
                f'{self.base_url}/api/gateway/v1/ping/',
                timeout=self.request_timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()

            # Try to extract version from response or default to v1
            version_str = '1'  # Default to v1 for AAP Gateway

            # If API provides version info, extract it
            if response.headers.get('X-API-Version'):
                version_str = response.headers.get('X-API-Version', '1')
            elif response.json().get('version'):
                version_str = str(response.json().get('version', '1'))

            # Normalize version string
            if version_str.startswith('v'):
                version_str = version_str[1:]

            return version_str

        except Exception as e:
            logger.warning(f"Version detection failed: {e}, defaulting to v1")
            return '1'

    def _authenticate(self) -> None:
        """
        Authenticate with the platform API.

        Raises:
            AuthenticationError: If authentication fails
        """
        with self._auth_lock:
            # Get fresh credentials from store
            username, password, oauth_token = self.credential_store.get_auth_credentials()

            # Use simple URL for auth - we don't know the API version yet
            url = self.base_url

            if oauth_token:
                # OAuth token authentication
                header = {"Authorization": f"Bearer {oauth_token}"}
                self.session.headers.update(header)
                try:
                    response = self.session.get(url, timeout=self.request_timeout, verify=self.verify_ssl)
                    response.raise_for_status()
                    self._last_auth_error = None
                except requests.RequestException as e:
                    self._last_auth_error = e
                    raise AuthenticationError(
                        message=f"Authentication error with token: {str(e)}",
                        operation='authenticate',
                        resource='auth',
                        details={'url': url, 'original_exception': str(e)},
                        original_exception=e
                    ) from e
            elif username and password:
                # Basic authentication
                basic_str = base64.b64encode(
                    f"{username}:{password}".encode("ascii")
                )
                header = {"Authorization": f"Basic {basic_str.decode('ascii')}"}
                self.session.headers.update(header)
                try:
                    response = self.session.get(url, timeout=self.request_timeout, verify=self.verify_ssl)
                    response.raise_for_status()
                    self._last_auth_error = None
                except requests.RequestException as e:
                    self._last_auth_error = e
                    raise AuthenticationError(
                        message=f"Authentication error with username/password: {str(e)}",
                        operation='authenticate',
                        resource='auth',
                        details={'url': url, 'original_exception': str(e)},
                        original_exception=e
                    ) from e
            else:
                raise AuthenticationError(
                    message="No authentication credentials provided",
                    operation='authenticate',
                    resource='auth',
                    details={'url': url}
                )

    def _make_request(
        self,
        method: str,
        url: str,
        operation: str = 'http_request',
        resource: str = 'unknown',
        **kwargs
    ) -> requests.Response:
        """
        Make HTTP request with retry logic (using decorator pattern).

        This method uses the retry decorator to handle retries automatically.

        Args:
            method: HTTP method ('get', 'post', 'put', 'patch', 'delete')
            url: Request URL
            operation: Operation name for error context
            resource: Resource type for error context
            **kwargs: Additional arguments for requests method

        Returns:
            Response object

        Raises:
            PlatformError: Classified platform error
        """
        # Create a retried version of the request function
        @retry_http_request(config=self.retry_config)
        def _execute_with_retry():
            # Set default timeout and verify_ssl if not provided
            request_kwargs = kwargs.copy()
            if 'timeout' not in request_kwargs:
                request_kwargs['timeout'] = self.request_timeout
            if 'verify' not in request_kwargs:
                request_kwargs['verify'] = self.verify_ssl

            # Get the appropriate session method
            session_method = getattr(self.session, method.lower())

            # Track request count
            with self._lock:
                self._http_request_count += 1

            # Make the actual HTTP request
            response = session_method(url, **request_kwargs)

            # Check for HTTP error status codes
            if response.status_code >= 400:
                # Handle 401 separately (authentication recovery)
                if response.status_code == 401:
                    # Try to recover authentication
                    if self._handle_auth_error(response):
                        # Retry the request after re-authentication
                        response = session_method(url, **request_kwargs)
                        if response.status_code == 401:
                            # Still 401 after recovery attempt
                            raise AuthenticationError(
                                message=f"Authentication failed: HTTP {response.status_code}",
                                operation=operation,
                                resource=resource,
                                details={
                                    'status_code': response.status_code,
                                    'url': url,
                                    'response_body': response.text[:500]
                                },
                                status_code=response.status_code
                            )
                    else:
                        # Authentication recovery failed
                        raise AuthenticationError(
                            message=f"Authentication failed: HTTP {response.status_code}",
                            operation=operation,
                            resource=resource,
                            details={
                                'status_code': response.status_code,
                                'url': url,
                                'response_body': response.text[:500]
                            },
                            status_code=response.status_code
                        )

                # For other HTTP errors, raise APIError
                response.raise_for_status()  # Will raise requests.HTTPError

            return response

        # Execute with retry logic
        return _execute_with_retry()

    def _handle_auth_error(self, response: requests.Response) -> bool:
        """
        Handle authentication error (401) and attempt recovery.

        Args:
            response: HTTP response with 401 status

        Returns:
            True if authentication was recovered, False otherwise
        """
        if response.status_code != 401:
            return False

        logger.warning("Received 401 Unauthorized, attempting to recover authentication")

        # Try token refresh first (if using OAuth)
        _, _, oauth_token = self.credential_store.get_auth_credentials()
        if oauth_token:
            if self._refresh_token():
                return True

        # Fall back to re-authentication
        if self._re_authenticate():
            return True

        logger.error("Failed to recover authentication")
        return False

    def _refresh_token(self) -> bool:
        """
        Refresh OAuth token if expired.

        Returns:
            True if token was refreshed, False otherwise
        """
        # TODO: Implement token refresh logic
        # This would check if token is expired and refresh it
        return False

    def _re_authenticate(self) -> bool:
        """
        Re-authenticate with stored credentials.

        Returns:
            True if re-authentication succeeded, False otherwise
        """
        try:
            self._authenticate()
            return True
        except Exception as e:
            logger.error(f"Re-authentication failed: {e}")
            return False

    def _build_url(self, endpoint: str, query_params: Optional[Dict] = None) -> str:
        """
        Build full URL from endpoint.

        Args:
            endpoint: API endpoint (e.g., '/api/gateway/v1/users/')
            query_params: Optional query parameters

        Returns:
            Full URL
        """
        # Ensure endpoint starts with /
        if not endpoint.startswith('/'):
            endpoint = f'/{endpoint}'

        # Build base URL
        url = f"{self.base_url}{endpoint}"

        # Add query parameters if provided
        if query_params:
            from urllib.parse import urlencode
            url = f"{url}?{urlencode(query_params)}"

        return url

    def execute(
        self,
        operation: str,
        module_name: str,
        ansible_data: Any
    ) -> dict:
        """
        Execute a generic operation on any resource.

        This is the main entry point called by action plugins.
        Uses the same shared CRUD logic as PlatformService.

        Args:
            operation: Operation type ('create', 'update', 'delete', 'find')
            module_name: Module name (e.g., 'user', 'organization')
            ansible_data: Ansible dataclass instance or dict

        Returns:
            Result as dict (Ansible format) with timing information

        Raises:
            ValueError: If operation is unknown or execution fails
        """
        from dataclasses import asdict, is_dataclass

        # Convert to dict if dataclass (for consistency with ManagerRPCClient)
        if is_dataclass(ansible_data):
            ansible_data_dict = asdict(ansible_data)
        else:
            ansible_data_dict = ansible_data
        # Performance timing: Processing start
        processing_start = time.perf_counter()

        logger.info(f"Executing {operation} on {module_name}")

        # Load version-appropriate classes (shared layer)
        AnsibleClass, APIClass, MixinClass = self.loader.load_classes_for_module(
            module_name,
            self.api_version
        )

        # Reconstruct Ansible dataclass
        ansible_instance = AnsibleClass(**ansible_data_dict)

        # Build transformation context (using dataclass for type safety)
        context = TransformContext(
            manager=self,
            session=self.session,
            cache=self.cache,
            api_version=self.api_version
        )

        # Execute operation (shared CRUD logic)
        try:
            if operation == 'create':
                result = self._create_resource(
                    ansible_instance, MixinClass, context
                )
            elif operation == 'update':
                result = self._update_resource(
                    ansible_instance, MixinClass, context
                )
            elif operation == 'delete':
                result = self._delete_resource(
                    ansible_instance, MixinClass, context
                )
            elif operation == 'find':
                result = self._find_resource(
                    ansible_instance, MixinClass, context
                )
            else:
                raise ValueError(f"Unknown operation: {operation}")

            # Performance timing: Processing end
            processing_end = time.perf_counter()
            processing_elapsed = processing_end - processing_start

            # Extract API call time from context if available
            api_time = 0
            if isinstance(context, dict) and 'timing' in context:
                api_time = context['timing'].get('api_call_time', 0)
            elif hasattr(context, 'timing'):
                api_time = getattr(context.timing, 'api_call_time', 0)

            # Calculate our code time (excluding API call which is AAP's time)
            our_code_time = processing_elapsed - api_time

            # Add timing info to result
            if isinstance(result, dict):
                result.setdefault('_timing', {})['processing_time'] = processing_elapsed
                result['_timing']['processing_start'] = processing_start
                result['_timing']['processing_end'] = processing_end
                result['_timing']['api_call_time'] = api_time
                result['_timing']['our_code_time'] = our_code_time

                # Add HTTP and TLS metrics (thread-safe read)
                with self._lock:
                    result['_timing']['http_request_count'] = self._http_request_count
                    result['_timing']['tls_handshake_count'] = self._tls_handshake_count

            return result

        except Exception as e:
            logger.error(f"Operation {operation} on {module_name} failed: {e}")
            raise

    # CRUD operation methods (shared logic - same as PlatformService)
    # These will be extracted to a shared module later, but for now
    # we'll duplicate them here to get standard mode working

    def _create_resource(
        self,
        ansible_data: Any,
        mixin_class: type,
        context: TransformContext
    ) -> dict:
        """Create resource with transformation."""
        # FORWARD TRANSFORM: Ansible → API
        api_data = ansible_data.to_api(context)

        # Get endpoint operations from mixin
        operations = mixin_class.get_endpoint_operations()

        # Execute operations (potentially multi-endpoint)
        api_result = self._execute_operations(
            operations, api_data, context, required_for='create'
        )

        # REVERSE TRANSFORM: API → Ansible
        if api_result:
            # from_api returns AnsibleUser dataclass
            ansible_instance = mixin_class.from_api(api_result, context)
            from dataclasses import asdict
            ansible_result = asdict(ansible_instance)
            ansible_result['changed'] = True
            return ansible_result

        return {'changed': True}

    def _update_resource(
        self,
        ansible_data: Any,
        mixin_class: type,
        context: TransformContext
    ) -> dict:
        """Update resource with transformation."""
        # Get the resource ID
        resource_id = getattr(ansible_data, 'id', None)
        if not resource_id:
            raise ValueError("Resource ID required for update operation")

        # Fetch current state for comparison
        try:
            current_data = self._find_resource(ansible_data, mixin_class, context)
        except Exception:
            current_data = {}

        # FORWARD TRANSFORM: Ansible → API
        api_data = ansible_data.to_api(context)

        # Get endpoint operations from mixin
        operations = mixin_class.get_endpoint_operations()

        # Execute update operation
        api_result = self._execute_operations(
            operations, api_data, context, required_for='update'
        )

        # REVERSE TRANSFORM: API → Ansible
        if api_result:
            # from_api returns AnsibleUser dataclass
            ansible_instance = mixin_class.from_api(api_result, context)
            from dataclasses import asdict
            ansible_result = asdict(ansible_instance)
            # Compare with current state to determine if changed
            changed = ansible_result != current_data
            ansible_result['changed'] = changed
            return ansible_result

        return {'changed': False}

    def _delete_resource(
        self,
        ansible_data: Any,
        mixin_class: type,
        context: TransformContext
    ) -> dict:
        """Delete resource."""
        # Get the resource ID
        resource_id = getattr(ansible_data, 'id', None)
        if not resource_id:
            raise ValueError("Resource ID required for delete operation")

        # Get endpoint operations from mixin
        operations = mixin_class.get_endpoint_operations()
        delete_op = operations.get('delete')

        if not delete_op:
            raise ValueError(f"Delete operation not defined for {mixin_class.__name__}")

        # Build URL
        url = self._build_url(delete_op.path.format(id=resource_id))

        # Execute delete
        response = self._make_request(
            delete_op.method,
            url,
            operation='delete',
            resource=mixin_class.__name__
        )

        return {'changed': True, 'deleted': True}

    def _find_resource(
        self,
        ansible_data: Any,
        mixin_class: type,
        context: TransformContext
    ) -> dict:
        """Find resource by lookup field."""
        # Get lookup field from mixin
        lookup_field = mixin_class.get_lookup_field()
        lookup_value = getattr(ansible_data, lookup_field, None)

        if not lookup_value:
            raise ValueError(f"Lookup field '{lookup_field}' not found in data")

        # Get endpoint operations from mixin
        operations = mixin_class.get_endpoint_operations()
        list_op = operations.get('list')

        if not list_op:
            raise ValueError(f"List operation not defined for {mixin_class.__name__}")

        # Build URL with query parameter
        url = self._build_url(list_op.path, {lookup_field: lookup_value})

        # Execute list request
        response = self._make_request(
            list_op.method,
            url,
            operation='find',
            resource=mixin_class.__name__
        )

        # Parse response
        results = response.json().get('results', [])
        if results:
            # Return first match
            api_data = results[0]
            # from_api returns AnsibleUser dataclass, convert to dict for return
            ansible_instance = mixin_class.from_api(api_data, context)
            from dataclasses import asdict
            return asdict(ansible_instance)

        # Not found
        raise ValueError(f"Resource not found: {lookup_field}={lookup_value}")

    def _execute_operations(
        self,
        operations: Dict,
        api_data: Any,
        context: TransformContext,
        required_for: str = None
    ) -> dict:
        """
        Execute endpoint operations (potentially multi-endpoint).

        This handles operations that may require multiple API calls
        (e.g., create user, then associate organizations).
        """
        results = {}

        # Filter operations by required_for
        relevant_ops = {
            name: op for name, op in operations.items()
            if op.required_for == required_for or required_for is None
        }

        # Sort by order
        sorted_ops = sorted(relevant_ops.items(), key=lambda x: x[1].order)

        for op_name, endpoint_op in sorted_ops:
            # Check dependencies
            if endpoint_op.depends_on and endpoint_op.depends_on not in results:
                continue

            # Build URL
            url = endpoint_op.path
            if endpoint_op.path_params:
                # Replace path parameters
                for param in endpoint_op.path_params:
                    param_value = results.get('id') or getattr(api_data, 'id', None)
                    if param_value:
                        url = url.replace(f'{{{param}}}', str(param_value))

            url = self._build_url(url)

            # Prepare request data
            request_data = {}
            if endpoint_op.fields:
                for field in endpoint_op.fields:
                    value = getattr(api_data, field, None)
                    if value is not None:
                        request_data[field] = value

            # Performance timing: API call start
            api_start = time.perf_counter()

            try:
                # Increment HTTP request counter (thread-safe)
                with self._lock:
                    self._http_request_count += 1

                response = self._make_request(
                    endpoint_op.method,
                    url,
                    json=request_data,
                    operation=op_name,
                    resource=endpoint_op.path.split('/')[-2] if '/' in endpoint_op.path else 'unknown'
                )

                # Performance timing: API call end
                api_end = time.perf_counter()
                api_elapsed = api_end - api_start

                # Store timing in context
                if hasattr(context, 'timing'):
                    context.timing['api_call_time'] = api_elapsed
                    context.timing['api_call_start'] = api_start
                    context.timing['api_call_end'] = api_end
                elif isinstance(context, dict):
                    context.setdefault('timing', {})['api_call_time'] = api_elapsed
                    context['timing']['api_call_start'] = api_start
                    context['timing']['api_call_end'] = api_end

            except Exception as e:
                logger.error(f"DirectHTTPClient: API call failed: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Response status: {e.response.status_code}")
                    logger.error(f"Response body: {e.response.text}")
                raise

            # Store result
            result_data = response.json() if response.content else {}
            results[op_name] = result_data

            # Store ID for dependent operations
            if 'id' in result_data and 'id' not in results:
                results['id'] = result_data['id']

        # Return main result
        return results.get('create') or results.get('update') or results.get('get') or results

    def lookup_organization_ids(self, names: list) -> list:
        """Lookup organization IDs from names (shared helper)."""
        # TODO: Implement lookup using cache
        # This should use the cache to avoid repeated lookups
        pass

    def lookup_organization_names(self, ids: list) -> list:
        """Lookup organization names from IDs (shared helper)."""
        # TODO: Implement lookup using cache
        # This should use the cache to avoid repeated lookups
        pass
