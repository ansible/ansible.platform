"""Platform Manager - Persistent service for API communication.

This module provides the server-side manager that maintains persistent
connections to the platform API and handles all data transformations.
"""

import base64
import logging
import threading
from multiprocessing.managers import BaseManager
from socketserver import ThreadingMixIn
from typing import Any, Dict, Optional, Tuple
from dataclasses import asdict, is_dataclass
from urllib.parse import urlparse, urlencode
import requests

from ..platform.registry import APIVersionRegistry
from ..platform.loader import DynamicClassLoader
from ..platform.types import EndpointOperation, TransformContext
from ..platform.credential_manager import (
    get_credential_manager,
    CredentialStore,
    TokenInfo
)
from ..platform.exceptions import (
    PlatformError,
    AuthenticationError,
    NetworkError,
    ValidationError,
    APIError,
    TimeoutError,
    classify_exception
)
from ..platform.retry import retry_http_request, RetryConfig

logger = logging.getLogger(__name__)


class PlatformService:
    """
    Generic platform service - resource agnostic.
    
    This service maintains a persistent connection and handles all resource operations
    generically. It performs all transformations and API calls.
    
    Attributes:
        base_url: Platform base URL
        session: Persistent HTTP session
        api_version: Detected/cached API version
        registry: Version registry
        loader: Class loader
        cache: Lookup cache (org names ↔ IDs, etc.)
        username: Authentication username
        password: Authentication password
        oauth_token: OAuth token for authentication
        verify_ssl: SSL verification flag
    """
    
    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        oauth_token: Optional[str] = None,
        verify_ssl: bool = True,
        request_timeout: float = 10.0
    ):
        """
        Initialize platform service.
        
        Args:
            base_url: Platform base URL (e.g., https://platform.example.com)
            username: Username for basic auth
            password: Password for basic auth
            oauth_token: OAuth token for bearer auth
            verify_ssl: Whether to verify SSL certificates
            request_timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.verify_ssl = verify_ssl
        self.request_timeout = request_timeout
        
        # Initialize credential manager and store credentials securely
        self.credential_manager = get_credential_manager()
        self.credential_store = self.credential_manager.get_or_create_store(
            gateway_url=self.base_url,
            username=username,
            password=password,
            oauth_token=oauth_token,
            process_id=str(id(self))  # Use object ID as process identifier
        )
        
        # Store namespace ID for credential operations
        self.namespace_id = self.credential_store.namespace.namespace_id
        
        # Get credentials from store (they're stored securely there)
        self.username, self.password, self.oauth_token = self.credential_store.get_auth_credentials()
        
        # Initialize persistent session (thread-safe)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Ansible Platform Collection',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # Track authentication state
        self._auth_lock = threading.Lock()
        self._last_auth_error = None
        
        # Authenticate (with error handling)
        try:
            self._authenticate()
            logger.info("Authentication successful")
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            self._last_auth_error = e
            # Continue anyway - some operations might work without auth
        
        # Detect API version (cached for lifetime)
        try:
            self.api_version = self._detect_version()
            logger.info(f"PlatformService initialized with API v{self.api_version}")
        except Exception as e:
            logger.warning(f"Version detection failed: {e}, defaulting to v1")
            self.api_version = '1'
        
        # Initialize registry and loader
        self.registry = APIVersionRegistry()
        self.loader = DynamicClassLoader(self.registry)
        
        # Cache for lookups
        self.cache: Dict[str, Any] = {}
        
        # Performance counters (thread-safe)
        self._http_request_count = 0
        self._tls_handshake_count = 1  # 1 handshake when session is created (HTTPS)
        self._lock = threading.Lock()
        
        # Shutdown flag
        self._shutdown_requested = False
        self._shutdown_lock = threading.Lock()
        
        # Retry configuration
        self.retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=True
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
                # The decorator will determine if it's retryable
                response.raise_for_status()  # Will raise requests.HTTPError
            
            return response
        
        # Execute with retry logic
        return _execute_with_retry()
        """
        Make HTTP request with retry logic and error classification.
        
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
        # Set default timeout and verify_ssl if not provided
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.request_timeout
        if 'verify' not in kwargs:
            kwargs['verify'] = self.verify_ssl
        
        # Get the appropriate session method
        session_method = getattr(self.session, method.lower())
        
        # Track request count
        with self._lock:
            self._http_request_count += 1
        
        # Make request with retry logic
        last_exception = None
        for attempt in range(self.retry_config.max_attempts):
            try:
                response = session_method(url, **kwargs)
                
                # Check for HTTP error status codes
                if response.status_code >= 400:
                    # Handle 401 separately (authentication)
                    if response.status_code == 401:
                        # Try to recover authentication
                        if self._handle_auth_error(response):
                            # Retry the request after re-authentication
                            if attempt < self.retry_config.max_attempts - 1:
                                continue
                        
                        # Authentication failed
                        raise AuthenticationError(
                            message=f"Authentication failed: HTTP {response.status_code}",
                            operation=operation,
                            resource=resource,
                            details={
                                'status_code': response.status_code,
                                'url': url,
                                'response_body': response.text[:500]  # Limit response body
                            },
                            status_code=response.status_code
                        )
                    
                    # Create APIError for other HTTP errors
                    error = APIError(
                        message=f"HTTP {response.status_code} error: {response.reason}",
                        operation=operation,
                        resource=resource,
                        details={
                            'status_code': response.status_code,
                            'url': url,
                            'response_body': response.text[:500]
                        },
                        status_code=response.status_code,
                        response_body=response.json() if response.headers.get('content-type', '').startswith('application/json') else None
                    )
                    
                    # Check if retryable and not last attempt
                    if error.retryable and attempt < self.retry_config.max_attempts - 1:
                        delay = self.retry_config.calculate_delay(attempt)
                        logger.warning(
                            f"Retrying {method.upper()} {url} (attempt {attempt + 1}/{self.retry_config.max_attempts}) "
                            f"after {delay:.2f}s: HTTP {response.status_code}"
                        )
                        import time
                        time.sleep(delay)
                        continue
                    else:
                        response.raise_for_status()  # Will raise requests.HTTPError
                
                return response
            
            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < self.retry_config.max_attempts - 1:
                    delay = self.retry_config.calculate_delay(attempt)
                    logger.warning(
                        f"Retrying {method.upper()} {url} (attempt {attempt + 1}/{self.retry_config.max_attempts}) "
                        f"after {delay:.2f}s: Timeout"
                    )
                    import time
                    time.sleep(delay)
                    continue
                else:
                    raise TimeoutError(
                        message=f"Request timed out after {self.retry_config.max_attempts} attempts: {str(e)}",
                        operation=operation,
                        resource=resource,
                        details={'url': url, 'timeout': kwargs.get('timeout')},
                        timeout_seconds=kwargs.get('timeout')
                    )
            
            except (requests.exceptions.ConnectionError, requests.exceptions.SSLError) as e:
                last_exception = e
                if attempt < self.retry_config.max_attempts - 1:
                    delay = self.retry_config.calculate_delay(attempt)
                    logger.warning(
                        f"Retrying {method.upper()} {url} (attempt {attempt + 1}/{self.retry_config.max_attempts}) "
                        f"after {delay:.2f}s: Network error"
                    )
                    import time
                    time.sleep(delay)
                    continue
                else:
                    raise NetworkError(
                        message=f"Network error after {self.retry_config.max_attempts} attempts: {str(e)}",
                        operation=operation,
                        resource=resource,
                        details={'url': url, 'original_exception': str(e)},
                        original_exception=e
                    )
            
            except requests.exceptions.HTTPError as e:
                # HTTPError from raise_for_status()
                response = e.response
                error = APIError(
                    message=f"HTTP {response.status_code} error: {response.reason}",
                    operation=operation,
                    resource=resource,
                    details={
                        'status_code': response.status_code,
                        'url': url,
                        'response_body': response.text[:500]
                    },
                    status_code=response.status_code,
                    response_body=response.json() if response.headers.get('content-type', '').startswith('application/json') else None
                )
                
                if error.retryable and attempt < self.retry_config.max_attempts - 1:
                    delay = self.retry_config.calculate_delay(attempt)
                    logger.warning(
                        f"Retrying {method.upper()} {url} (attempt {attempt + 1}/{self.retry_config.max_attempts}) "
                        f"after {delay:.2f}s: HTTP {response.status_code}"
                    )
                    import time
                    time.sleep(delay)
                    continue
                else:
                    raise error
            
            except Exception as e:
                # Classify and handle other exceptions
                platform_error = classify_exception(e, operation, resource)
                platform_error.details['url'] = url
                
                if platform_error.retryable and attempt < self.retry_config.max_attempts - 1:
                    delay = self.retry_config.calculate_delay(attempt)
                    logger.warning(
                        f"Retrying {method.upper()} {url} (attempt {attempt + 1}/{self.retry_config.max_attempts}) "
                        f"after {delay:.2f}s: {type(e).__name__}"
                    )
                    import time
                    time.sleep(delay)
                    continue
                else:
                    raise platform_error
        
        # If we get here, all retries failed
        if last_exception:
            raise classify_exception(last_exception, operation, resource)
        
        raise RuntimeError(f"Request failed for {method.upper()} {url}")
    
    def _authenticate(self) -> None:
        """Authenticate with the platform API."""
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
                    raise ValueError(f"Authentication error with token: {e}") from e
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
                    raise ValueError(f"Authentication error: {e}") from e
            else:
                error_msg = "Either oauth_token or username/password must be provided"
                self._last_auth_error = ValueError(error_msg)
                raise ValueError(error_msg)
    
    def _check_token_expiration(self) -> Tuple[bool, Optional[float]]:
        """
        Check if current token is expired.
        
        Returns:
            Tuple of (is_expired, seconds_until_expiry)
        """
        return self.credential_manager.check_token_expiration(self.namespace_id)
    
    def _refresh_token(self) -> bool:
        """
        Attempt to refresh OAuth token.
        
        Returns:
            True if token was refreshed, False otherwise
        """
        with self._auth_lock:
            if not self.credential_store.token_info:
                logger.debug("No token info available for refresh")
                return False
            
            token_info = self.credential_store.token_info
            if not token_info.refresh_token:
                logger.debug("No refresh token available")
                return False
            
            # Attempt to refresh token
            # Note: This is a placeholder - actual refresh endpoint depends on Gateway API
            try:
                # Gateway token refresh endpoint (if available)
                refresh_url = f"{self.base_url}/api/gateway/v1/auth/token/refresh/"
                response = self.session.post(
                    refresh_url,
                    json={"refresh_token": token_info.refresh_token},
                    timeout=self.request_timeout,
                    verify=self.verify_ssl
                )
                
                if response.status_code == 200:
                    data = response.json()
                    new_token = data.get('access_token')
                    new_refresh_token = data.get('refresh_token', token_info.refresh_token)
                    expires_in = data.get('expires_in')
                    
                    if new_token:
                        self.credential_store.update_token(
                            token=new_token,
                            refresh_token=new_refresh_token,
                            expires_in=expires_in
                        )
                        # Update session header
                        self.session.headers.update({
                            "Authorization": f"Bearer {new_token}"
                        })
                        logger.info("Token refreshed successfully")
                        return True
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}")
            
            return False
    
    def _re_authenticate(self) -> bool:
        """
        Re-authenticate using stored credentials.
        
        Returns:
            True if re-authentication succeeded, False otherwise
        """
        try:
            self._authenticate()
            return True
        except Exception as e:
            logger.error(f"Re-authentication failed: {e}")
            return False
    
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
                logger.info("Authentication recovered via token refresh")
                return True
        
        # Fall back to re-authentication
        if self._re_authenticate():
            logger.info("Authentication recovered via re-authentication")
            return True
        
        logger.error("Failed to recover authentication")
        return False
    
    def _detect_version(self) -> str:
        """
        Detect platform API version.
        
        Returns:
            Version string (e.g., '1', '2.1')
        """
        try:
            # Try to get version from API
            # Most AAP APIs have a version endpoint or include version in response
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
            logger.warning(f"Failed to detect API version: {e}, using default '1'")
            return '1'
    
    def _build_url(self, endpoint: str, query_params: Optional[Dict] = None) -> str:
        """
        Build full URL for an endpoint.
        
        Args:
            endpoint: API endpoint path
            query_params: Optional query parameters
        
        Returns:
            Full URL string
        """
        # Ensure endpoint starts with /api/gateway/v1
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        if not endpoint.startswith("/api/"):
            endpoint = f"/api/gateway/v{self.api_version}{endpoint}"
        if not endpoint.endswith("/") and "?" not in endpoint:
            endpoint = f"{endpoint}/"
        
        url = f"{self.base_url}{endpoint}"
        
        if query_params:
            url = f"{url}?{urlencode(query_params)}"
        
        return url
    
    def execute(
        self,
        operation: str,
        module_name: str,
        ansible_data_dict: dict
    ) -> dict:
        """
        Execute a generic operation on any resource.
        
        This is the main entry point called by action plugins via RPC.
        
        Args:
            operation: Operation type ('create', 'update', 'delete', 'find')
            module_name: Module name (e.g., 'user', 'organization')
            ansible_data_dict: Ansible dataclass as dict
        
        Returns:
            Result as dict (Ansible format) with timing information
        
        Raises:
            ValueError: If operation is unknown or execution fails
        """
        import time
        
        # Performance timing: Manager processing start
        manager_start = time.perf_counter()
        
        logger.info(f"Executing {operation} on {module_name}")
        
        # Load version-appropriate classes
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
        
        # Execute operation
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
            
            # Performance timing: Manager processing end
            manager_end = time.perf_counter()
            manager_elapsed = manager_end - manager_start
            
            # Extract API call time from context if available
            api_time = 0
            if isinstance(context, dict) and 'timing' in context:
                api_time = context['timing'].get('api_call_time', 0)
            elif hasattr(context, 'timing'):
                api_time = getattr(context.timing, 'api_call_time', 0)
            
            # Calculate our code time in manager (excluding API call which is AAP's time)
            # Manager time includes: transformations, class loading, etc.
            # But API call time is AAP response time, so subtract it
            our_manager_code_time = manager_elapsed - api_time
            
            # Add timing info to result
            if isinstance(result, dict):
                result.setdefault('_timing', {})['manager_processing_time'] = manager_elapsed
                result['_timing']['manager_start'] = manager_start
                result['_timing']['manager_end'] = manager_end
                result['_timing']['api_call_time'] = api_time
                result['_timing']['our_manager_code_time'] = our_manager_code_time
                
                # Add HTTP and TLS metrics (thread-safe read)
                with self._lock:
                    result['_timing']['http_request_count'] = self._http_request_count
                    result['_timing']['tls_handshake_count'] = self._tls_handshake_count
            
            return result
            
        except Exception as e:
            logger.error(
                f"Operation {operation} on {module_name} failed: {e}",
                exc_info=True
            )
            raise
    
    def _create_resource(
        self,
        ansible_data: Any,
        mixin_class: type,
        context: dict
    ) -> dict:
        """
        Create resource with transformation.
        
        Args:
            ansible_data: Ansible dataclass instance
            mixin_class: Transform mixin class
            context: Transformation context
        
        Returns:
            Created resource as dict (Ansible format) with 'changed': True
        """
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
            # Use mixin's from_api method which returns AnsibleUser dataclass
            ansible_instance = mixin_class.from_api(api_result, context)
            # Convert to dict and add 'changed' field for Ansible return
            from dataclasses import asdict
            ansible_result = asdict(ansible_instance)
            ansible_result['changed'] = True
            return ansible_result
        
        return {'changed': True}
    
    def _update_resource(
        self,
        ansible_data: Any,
        mixin_class: type,
        context: dict
    ) -> dict:
        """
        Update resource with transformation.
        
        Args:
            ansible_data: Ansible dataclass instance
            mixin_class: Transform mixin class
            context: Transformation context
        
        Returns:
            Updated resource as dict (Ansible format) with 'changed': True/False
        """
        # Get the resource ID
        resource_id = getattr(ansible_data, 'id', None)
        if not resource_id:
            raise ValueError("Resource ID required for update operation")
        
        # Fetch current state for comparison
        try:
            current_data = self._find_resource(ansible_data, mixin_class, context)
        except Exception:
            # If we can't fetch current state, assume change
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
            # Use mixin's from_api method which returns AnsibleUser dataclass
            ansible_instance = mixin_class.from_api(api_result, context)
            from dataclasses import asdict
            
            # Convert to dict for comparison and return
            new_dict = asdict(ansible_instance)
            current_dict = current_data if isinstance(current_data, dict) else {}
            
            # Compare relevant fields (exclude read-only fields like created, modified, url)
            read_only_fields = {'id', 'created', 'modified', 'url'}
            new_comparable = {k: v for k, v in new_dict.items() if k not in read_only_fields}
            current_comparable = {k: v for k, v in current_dict.items() if k not in read_only_fields}
            
            changed = new_comparable != current_comparable
            
            # Add 'changed' field to result dict
            new_dict['changed'] = changed
            return new_dict
        
        return {'changed': False}
    
    def _delete_resource(
        self,
        ansible_data: Any,
        mixin_class: type,
        context: dict
    ) -> dict:
        """
        Delete resource.
        
        Args:
            ansible_data: Ansible dataclass instance
            mixin_class: Transform mixin class
            context: Transformation context
        
        Returns:
            Empty dict (resource deleted)
        """
        # Get endpoint operations from mixin
        operations = mixin_class.get_endpoint_operations()
        
        # Find delete operation
        delete_op = None
        for op_name, op in operations.items():
            if op_name == 'delete' or (op.required_for == 'delete'):
                delete_op = op
                break
        
        if not delete_op:
            raise ValueError("No delete operation defined for this resource")
        
        # Need ID for delete
        resource_id = ansible_data.id
        if not resource_id:
            raise ValueError("Resource ID required for delete operation")
        
        # Build URL with path parameters
        path = delete_op.path
        if delete_op.path_params:
            for param in delete_op.path_params:
                if param == 'id':
                    path = path.replace(f'{{{param}}}', str(resource_id))
        
        url = self._build_url(path)
        
        # Make DELETE request
        logger.debug(f"Calling DELETE {url}")
        response = self.session.delete(
            url,
            timeout=self.request_timeout,
            verify=self.verify_ssl
        )
        response.raise_for_status()
        
        # Deleting a resource always results in a change
        return {'changed': True}
    
    def _find_resource(
        self,
        ansible_data: Any,
        mixin_class: type,
        context: dict
    ) -> dict:
        """
        Find resource by identifier.
        
        Args:
            ansible_data: Ansible dataclass instance
            mixin_class: Transform mixin class
            context: Transformation context
        
        Returns:
            Found resource as dict (Ansible format)
        """
        # Get endpoint operations from mixin
        operations = mixin_class.get_endpoint_operations()
        
        # Find list operation (for querying) or get operation (for ID lookup)
        list_op = operations.get('list')
        get_op = operations.get('get')
        
        # Get lookup field name (e.g., 'username', 'name')
        lookup_field = mixin_class.get_lookup_field()
        unique_value = getattr(ansible_data, lookup_field, None) or getattr(ansible_data, 'id', None)
        
        if not unique_value:
            raise ValueError(f"Cannot find resource: no {lookup_field} or id provided")
        
        # If we have an ID, use get endpoint
        if hasattr(ansible_data, 'id') and ansible_data.id:
            if not get_op:
                raise ValueError("No GET operation defined for this resource")
            url = self._build_url(get_op.path.replace('{id}', str(ansible_data.id)))
            response = self.session.get(
                url,
                timeout=self.request_timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            api_result = response.json()
        else:
            # Use list endpoint and filter by lookup field
            if not list_op:
                raise ValueError("No LIST operation defined for this resource")
            url = self._build_url(list_op.path, query_params={lookup_field: unique_value})
            logger.debug(f"Calling GET {url} to find {lookup_field}={unique_value}")
            response = self.session.get(
                url,
                timeout=self.request_timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            list_result = response.json()
            
            # Find matching item in results
            results = list_result.get('results', [])
            if not results:
                raise ValueError(f"Resource with {lookup_field}={unique_value} not found")
            
            # Return first match
            api_result = results[0]
        
        # REVERSE TRANSFORM: API → Ansible
        # from_api returns AnsibleUser dataclass, convert to dict for return
        ansible_instance = mixin_class.from_api(api_result, context)
        from dataclasses import asdict
        return asdict(ansible_instance)
    
    def _execute_operations(
        self,
        operations: Dict,
        api_data: Any,
        context: dict,
        required_for: str = None
    ) -> dict:
        """
        Execute potentially multiple API endpoint operations.
        
        Args:
            operations: Dict of EndpointOperations
            api_data: API dataclass instance
            context: Context
            required_for: Filter operations by required_for field
        
        Returns:
            Combined API response dict
        """
        # Filter operations
        relevant_ops = {
            name: op for name, op in operations.items()
            if op.required_for is None or op.required_for == required_for
        }
        
        # Sort by dependencies and order
        sorted_ops = self._sort_operations(relevant_ops)
        
        # Execute in order
        results = {}
        api_data_dict = asdict(api_data)
        
        for op_name in sorted_ops:
            endpoint_op = relevant_ops[op_name]
            
            # Extract fields for this endpoint
            request_data = {}
            for field in endpoint_op.fields:
                if field in api_data_dict and api_data_dict[field] is not None:
                    request_data[field] = api_data_dict[field]
            
            if not request_data:
                logger.debug(f"Skipping {op_name} - no data")
                continue
            
            # Build URL with path parameters
            path = endpoint_op.path
            if endpoint_op.path_params:
                for param in endpoint_op.path_params:
                    if param in results:
                        path = path.replace(f'{{{param}}}', str(results[param]))
                    elif param == 'id' and 'id' in api_data_dict:
                        path = path.replace(f'{{{param}}}', str(api_data_dict['id']))
            
            url = self._build_url(path)
            
            # Make API call
            logger.debug(f"Calling {endpoint_op.method} {url}")
            # Performance timing: API call start
            import time
            api_start = time.perf_counter()
            
            try:
                # Increment HTTP request counter (thread-safe)
                with self._lock:
                    self._http_request_count += 1
                
                response = self.session.request(
                    endpoint_op.method,
                    url,
                    json=request_data,
                    timeout=self.request_timeout,
                    verify=self.verify_ssl
                )
                response.raise_for_status()
                
                # Performance timing: API call end
                api_end = time.perf_counter()
                api_elapsed = api_end - api_start
                
                # Store timing in context for later retrieval
                if hasattr(context, 'timing'):
                    context.timing['api_call_time'] = api_elapsed
                    context.timing['api_call_start'] = api_start
                    context.timing['api_call_end'] = api_end
                elif isinstance(context, dict):
                    context.setdefault('timing', {})['api_call_time'] = api_elapsed
                    context['timing']['api_call_start'] = api_start
                    context['timing']['api_call_end'] = api_end
                    
            except Exception as e:
                logger.error(f"API call failed: {e}")
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
        return results.get('create') or results.get('update') or results.get('main') or {}
    
    def _sort_operations(self, operations: Dict) -> list:
        """
        Sort operations by dependencies and order.
        
        Args:
            operations: Dict of EndpointOperations
        
        Returns:
            List of operation names in execution order
        """
        sorted_ops = []
        remaining = dict(operations)
        
        # Topological sort based on depends_on
        while remaining:
            # Find operations with no unmet dependencies
            ready = [
                name for name, op in remaining.items()
                if op.depends_on is None or op.depends_on in sorted_ops
            ]
            
            if not ready:
                raise ValueError(
                    f"Circular dependency in operations: "
                    f"{list(remaining.keys())}"
                )
            
            # Sort ready operations by order field
            ready.sort(key=lambda name: remaining[name].order)
            
            # Add first ready operation
            sorted_ops.append(ready[0])
            remaining.pop(ready[0])
        
        return sorted_ops
    
    # Helper methods for transformations (called via context)
    
    def lookup_org_ids(self, org_names: list) -> list:
        """
        Convert organization names to IDs.
        
        Args:
            org_names: List of organization names
        
        Returns:
            List of organization IDs
        """
        ids = []
        for name in org_names:
            # Check cache
            cache_key = f'org_name:{name}'
            if cache_key in self.cache:
                ids.append(self.cache[cache_key])
                continue
            
            # API lookup
            url = self._build_url('organizations', query_params={'name': name})
            response = self.session.get(
                url,
                timeout=self.request_timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            results = response.json().get('results', [])
            
            if results:
                org_id = results[0]['id']
                self.cache[cache_key] = org_id
                ids.append(org_id)
            else:
                raise ValueError(f"Organization '{name}' not found")
        
        return ids
    
    def lookup_org_names(self, org_ids: list) -> list:
        """
        Convert organization IDs to names.
        
        Args:
            org_ids: List of organization IDs
        
        Returns:
            List of organization names
        """
        names = []
        for org_id in org_ids:
            # Check reverse cache
            cache_key = f'org_id:{org_id}'
            if cache_key in self.cache:
                names.append(self.cache[cache_key])
                continue
            
            # API lookup
            url = self._build_url(f'organizations/{org_id}/')
            response = self.session.get(
                url,
                timeout=self.request_timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            org = response.json()
            
            name = org['name']
            self.cache[cache_key] = name
            self.cache[f'org_name:{name}'] = org_id  # Store both directions
            names.append(name)
        
        return names
    
    # Aliases for consistency with transform mixins
    def lookup_organization_ids(self, org_names: list) -> list:
        """Alias for lookup_org_ids."""
        return self.lookup_org_ids(org_names)
    
    def lookup_organization_names(self, org_ids: list) -> list:
        """Alias for lookup_org_names."""
        return self.lookup_org_names(org_ids)
    
    def shutdown(self) -> dict:
        """
        Gracefully shutdown the manager service.
        
        This method:
        - Closes the HTTP session
        - Cleans up resources
        - Signals the manager process to exit
        
        Returns:
            dict with shutdown status
        """
        with self._shutdown_lock:
            if self._shutdown_requested:
                logger.debug("Shutdown already requested")
                return {"status": "already_shutdown"}
            
            self._shutdown_requested = True
            logger.info("Shutdown requested for PlatformService")
        
        # Close HTTP session
        try:
            if hasattr(self, 'session') and self.session:
                self.session.close()
                logger.debug("HTTP session closed")
        except Exception as e:
            logger.warning(f"Error closing HTTP session: {e}")
        
        # Clear cache
        try:
            self.cache.clear()
            logger.debug("Cache cleared")
        except Exception as e:
            logger.warning(f"Error clearing cache: {e}")
        
        logger.info("PlatformService shutdown complete")
        return {"status": "shutdown", "message": "Manager service shut down gracefully"}


class PlatformManager(ThreadingMixIn, BaseManager):
    """
    Custom Manager for sharing PlatformService across processes.
    
    Uses ThreadingMixIn to handle concurrent client connections.
    """
    daemon_threads = True
    
    @staticmethod
    def register_shutdown_method(service):
        """Register shutdown method with manager."""
        PlatformManager.register('shutdown', callable=lambda: service.shutdown())


