"""Direct HTTP Client - Standard connection mode.

This module provides a direct HTTP client for standard mode (default).
It uses Ansible's module_utils.urls.Request (same as current collection)
without a persistent manager process, but shares all the same layers
(version detection, error handling, credential management, CRUD operations).
"""

import base64
import json
import logging
import re
import threading
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from ansible.module_utils.six.moves.http_cookiejar import CookieJar
from ansible.module_utils.six.moves.urllib.error import HTTPError

# Use Ansible's HTTP client instead of requests library for better worker process compatibility
from ansible.module_utils.urls import ConnectionError, Request, SSLValidationError

from .base_client import BaseAPIClient
from .config import GatewayConfig
from .credential_manager import get_credential_manager
from .exceptions import APIError, AuthenticationError
from .retry import RetryConfig
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
            process_id=str(id(self)),  # Use object ID as process identifier
        )

        # Store namespace ID for credential operations
        self.namespace_id = self.credential_store.namespace.namespace_id

        # Get credentials from store (they're stored securely there)
        self.username, self.password, self.oauth_token = self.credential_store.get_auth_credentials()

        # Initialize session using Ansible's Request (like current collection)
        # This is more compatible with Ansible worker processes
        self.session = Request(cookies=CookieJar(), validate_certs=self.verify_ssl, timeout=self.request_timeout)
        self.session.headers.update({"User-Agent": "Ansible Platform Collection", "Accept": "application/json", "Content-Type": "application/json"})

        # Track authentication state
        self._auth_lock = threading.Lock()
        self._last_auth_error = None

        # Performance counters
        self._http_request_count = 0
        self._tls_handshake_count = 1  # 1 handshake when session is created (HTTPS)
        self._lock = threading.Lock()

        # Retry configuration
        self.retry_config = RetryConfig(max_attempts=3, initial_delay=1.0, max_delay=60.0, exponential_base=2.0, jitter=True)

        # Defer authentication and version detection until first request
        # This prevents HTTP requests during worker process initialization
        self.api_version = None  # Will be set on first request
        self._authenticated = False
        logger.info("DirectHTTPClient: Initialized (authentication deferred until first request)")

    def _detect_api_version(self) -> str:
        """
        Detect API version dynamically by querying the live Gateway.

        Detection order:
          1. GET /api/gateway/v1/ping/ — read X-API-Version response header.
             If the ping returns 200 with no header, the /v1/ path is reachable
             so v1 is confirmed.  The JSON body is NOT parsed: the "version"
             field on this endpoint contains the *product* version (e.g. "2.6"
             for AAP Gateway 2.6.x), not the API version.
          2. If the ping endpoint returns non-2xx (older servers without that
             endpoint), fall back to GET /api/gateway/ and parse its
             X-API-Version header or ``current_version`` field.

        If all tiers fail, default to ``'1'``.  Never fall back to
        get_latest_version() — a collection that ships v2 must not assume
        the server supports v2.
        """
        logger.info("DirectHTTPClient: Detecting API version dynamically from platform...")

        supported = self.registry.get_supported_versions()

        def _hdr_version(resp) -> str:
            """Extract API version from X-API-Version header; return '' if absent."""
            headers = getattr(resp, "headers", {})
            raw = (headers.get("X-API-Version", "") if hasattr(headers, "get") else "").lstrip("v")
            if raw and raw in supported:
                return raw
            if raw:
                major = raw.split(".")[0]
                if major in supported:
                    return major
            return ""

        # ── Tier 1: /api/gateway/v1/ping/ ─────────────────────────────────
        try:
            ping_url = f"{self.base_url.rstrip('/')}/api/gateway/v1/ping/"
            logger.debug("DirectHTTPClient: version detection tier-1 %s", ping_url)
            response = self.session.open("GET", ping_url, validate_certs=self.verify_ssl, timeout=self.request_timeout)

            # Only trust the X-API-Version header from the ping endpoint.
            # The JSON body "version" field is the *product* version
            # (e.g. "2.6" for AAP Gateway 2.6.x), NOT the API version.
            # Parsing it would map "2.6" -> major "2" and select the wrong
            # API version on a server that only serves v1 paths.
            v = _hdr_version(response)
            if v:
                logger.info("DirectHTTPClient: API version locked in (tier-1 header): v%s", v)
                return v

            # Ping at /api/gateway/v1/ping/ succeeded but no X-API-Version header.
            # Successfully reaching the /v1/ path confirms API v1 is available.
            logger.info("DirectHTTPClient: tier-1 ping succeeded, no X-API-Version header — v1 confirmed")
            if "1" in supported:
                return "1"

        except Exception as e:
            logger.debug("DirectHTTPClient: tier-1 ping failed (%s) — trying tier-2", e)

        # ── Tier 2: /api/gateway/ (all v1 servers expose this) ────────────
        try:
            root_url = f"{self.base_url.rstrip('/')}/api/gateway/"
            logger.debug("DirectHTTPClient: version detection tier-2 %s", root_url)
            response = self.session.open("GET", root_url, validate_certs=self.verify_ssl, timeout=self.request_timeout)

            v = _hdr_version(response)
            if v:
                logger.info("DirectHTTPClient: API version locked in (tier-2 header): v%s", v)
                return v

            try:
                body_bytes = response.read()
                body = json.loads(body_bytes) if body_bytes else {}
                if "current_version" in body:
                    m = re.search(r"/v(\d+(?:\.\d+)?)/?$", str(body["current_version"]))
                    raw = m.group(1) if m else str(body["current_version"]).lstrip("v")
                    if raw in supported:
                        logger.info("DirectHTTPClient: API version locked in (tier-2 body): v%s", raw)
                        return raw
                    major = raw.split(".")[0]
                    if major in supported:
                        logger.info("DirectHTTPClient: API version locked in (tier-2 body major): v%s", major)
                        return major
                # NOTE: "version" and "available_versions" are intentionally NOT
                # parsed — "version" is the product version; "available_versions"
                # lists routing, not collection endpoint compatibility.
            except Exception as exc:
                logger.debug("DirectHTTPClient: tier-2 body parse error: %s", exc)

        except Exception as e:
            logger.warning("DirectHTTPClient: tier-2 detection failed (%s)", e)

        # ── Tier 3: safe default ───────────────────────────────────────────
        if not supported:
            raise RuntimeError("CRITICAL: No API versions discovered in the collection's api/ directory!")
        logger.warning("DirectHTTPClient: version detection failed — defaulting to v1")
        if "1" in supported:
            return "1"
        return supported[0]

    def _authenticate(self) -> None:
        """
        Set authentication headers in session (no test request).

        This just configures the session with auth headers.
        Authentication will be validated when actual API calls are made.

        Raises:
            AuthenticationError: If no credentials provided
        """
        with self._auth_lock:
            # Get fresh credentials from store
            username, password, oauth_token = self.credential_store.get_auth_credentials()

            if oauth_token:
                # OAuth token authentication - just set header
                header = {"Authorization": f"Bearer {oauth_token}"}
                self.session.headers.update(header)
                self._last_auth_error = None
                logger.info("DirectHTTPClient: OAuth token configured")
            elif username and password:
                # Basic authentication - just set header
                basic_str = base64.b64encode(f"{username}:{password}".encode("ascii"))
                header = {"Authorization": f"Basic {basic_str.decode('ascii')}"}
                self.session.headers.update(header)
                self._last_auth_error = None
                logger.info("DirectHTTPClient: Basic auth configured")
            else:
                raise AuthenticationError(message="No authentication credentials provided", operation="authenticate", resource="auth", details={})

    def _make_request(self, method: str, url: str, operation: str = "http_request", resource: str = "unknown", **kwargs):
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
        # Set default timeout and verify_ssl if not provided
        request_kwargs = kwargs.copy()
        timeout = request_kwargs.pop("timeout", self.request_timeout)
        verify = request_kwargs.pop("verify", self.verify_ssl)

        # Prepare data for JSON requests
        data = None
        if "json" in request_kwargs:
            data = json.dumps(request_kwargs.pop("json"))
        elif "data" in request_kwargs:
            data = request_kwargs.pop("data")

        # Parse URL (Ansible's Request.open() expects a parsed URL or string)
        if isinstance(url, str):
            parsed_url = urlparse(url)
        else:
            parsed_url = url

        try:
            # Use Ansible's Request.open() - this is compatible with Ansible worker processes
            # Single connection per task - no persistence, just like current collection
            logger.info("DirectHTTPClient: Making %s request to %s", method.upper(), url)

            # Ensure session is properly initialized
            if not hasattr(self.session, "open"):
                raise RuntimeError("Session does not have 'open' method. Session type: %s" % type(self.session))

            # Get URL string - Ansible's Request.open() accepts string URLs
            # Use geturl() if it's a ParseResult, otherwise use the string directly
            if hasattr(parsed_url, "geturl"):
                url_str = parsed_url.geturl()
            else:
                url_str = str(url)

            logger.info("DirectHTTPClient: Calling session.open() with method=%s, url=%s", method.upper(), url_str)
            logger.info("DirectHTTPClient: Session type: %s", type(self.session))
            logger.info("DirectHTTPClient: Session has open method: %s", hasattr(self.session, "open"))

            # Ansible's Request.open() makes the HTTP request
            # This is the same approach used by current ansible.platform collection
            # Wrap in try-except to catch any exceptions before worker crashes
            try:
                response = self.session.open(
                    method.upper(),
                    url_str,
                    validate_certs=verify,
                    timeout=timeout,
                    follow_redirects=True,
                    data=data,
                )
                status = getattr(response, "status", getattr(response, "code", "unknown"))
                logger.info("DirectHTTPClient: Response received: status=%s", status)
            except BaseException as open_err:
                # Catch ALL exceptions including SystemExit, KeyboardInterrupt, etc.
                logger.error("DirectHTTPClient: session.open() raised exception: %s: %s", type(open_err).__name__, open_err)
                import traceback

                logger.error("DirectHTTPClient: session.open() traceback: %s", traceback.format_exc())
                # Re-raise to let upper-level handlers deal with it
                raise
        except SSLValidationError as ssl_err:
            logger.error("DirectHTTPClient: SSL validation error: %s", ssl_err)
            raise
        except ConnectionError as con_err:
            logger.error("DirectHTTPClient: Connection error: %s", con_err)
            raise
        except HTTPError as he:
            # Ansible's Request.open() raises HTTPError for 4xx/5xx responses
            status = he.code

            # Handle 401 separately (authentication recovery)
            if status == 401:
                # Try to recover authentication
                if self._handle_auth_error(he):
                    # Retry the request after re-authentication
                    try:
                        response = self.session.open(
                            method.upper(),
                            parsed_url.geturl() if hasattr(parsed_url, "geturl") else str(url),
                            validate_certs=verify,
                            timeout=timeout,
                            follow_redirects=True,
                            data=data,
                        )
                        # Success - return the response
                        return response
                    except HTTPError as he2:
                        if he2.code == 401:
                            # Still 401 after recovery attempt
                            try:
                                response_body = he2.read()[:500] if hasattr(he2, "read") else str(he2)
                            except Exception:
                                response_body = str(he2)
                            raise AuthenticationError(
                                message=f"Authentication failed: HTTP {he2.code}",
                                operation=operation,
                                resource=resource,
                                details={"status_code": he2.code, "url": url, "response_body": response_body},
                                status_code=he2.code,
                            )
                        raise
                else:
                    # Authentication recovery failed
                    try:
                        response_body = he.read()[:500] if hasattr(he, "read") else str(he)
                    except Exception:
                        response_body = str(he)
                    raise AuthenticationError(
                        message=f"Authentication failed: HTTP {he.code}",
                        operation=operation,
                        resource=resource,
                        details={"status_code": he.code, "url": url, "response_body": response_body},
                        status_code=he.code,
                    )

            # For other HTTP errors, raise appropriate exception
            try:
                response_body = he.read()[:500] if hasattr(he, "read") else str(he)
            except Exception:
                response_body = str(he)
            raise APIError(
                message=f"API request failed: HTTP {he.code}",
                operation=operation,
                resource=resource,
                details={"status_code": he.code, "url": url, "response_body": response_body},
                status_code=he.code,
            )
        except Exception as e:
            logger.error("DirectHTTPClient: HTTP request failed: %s", e)
            import traceback

            logger.error("DirectHTTPClient: Traceback: %s", traceback.format_exc())
            raise

        # Success - return the response
        return response

    def _handle_auth_error(self, response) -> bool:
        """
        Handle authentication error (401) and attempt recovery.

        Args:
            response: HTTPError with 401 status (from Ansible's Request.open())

        Returns:
            True if authentication was recovered, False otherwise
        """
        # Check if it's an HTTPError with 401 status
        if hasattr(response, "code"):
            status = response.code
        elif hasattr(response, "status"):
            status = response.status
        else:
            return False

        if status != 401:
            return False

        logger.warning("Received 401 Unauthorized, attempting to recover authentication")

        # Try token refresh first (if using OAuth)
        creds = self.credential_store.get_auth_credentials()
        oauth_token = creds[2] if len(creds) > 2 else None
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
            logger.error("Re-authentication failed: %s", e)
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
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"

        # Build base URL
        url = f"{self.base_url}{endpoint}"

        # Add query parameters if provided
        if query_params:
            from urllib.parse import urlencode

            url = f"{url}?{urlencode(query_params)}"

        return url

    def lookup_resource_id(self, endpoint: str, lookup_field: str, lookup_value: str):
        """
        Resolve a resource name to ID by GET list with filter.
        Compatible with PlatformService.lookup_resource_id interface.
        Used by API mixins to resolve FKs (e.g. authenticator name -> id).

        Args:
            endpoint: API resource endpoint name (e.g. 'authenticators', 'service_clusters')
            lookup_field: Field to filter on (e.g. 'name')
            lookup_value: Value to look up

        Returns:
            Resource ID (int) or None
        """
        if not lookup_value:
            return None
        if str(lookup_value).isdigit():
            return int(lookup_value)

        cache_key = f"lookup:{endpoint}:{lookup_field}:{lookup_value}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Detect API version if not done yet
        if self.api_version is None:
            try:
                self.api_version = self._detect_api_version()
            except Exception:
                self.api_version = "1"
            self.session.headers.update({"X-API-Version": str(self.api_version)})

        # Build the URL: /api/gateway/v{version}/{endpoint}/?{lookup_field}={lookup_value}
        api_path = f"/api/gateway/v{self.api_version}/{endpoint}/"
        url = self._build_url(api_path, {lookup_field: lookup_value})

        response = self._make_request("GET", url, operation="lookup", resource=endpoint)

        try:
            response_body = response.read()
            response_data = json.loads(response_body) if response_body else {}
        except Exception:
            response_data = {}

        results = response_data.get("results", [])
        if not results:
            raise ValueError("Resource '%s' with %s=%s not found" % (endpoint, lookup_field, lookup_value))

        rid = results[0].get("id")
        if rid is not None:
            self.cache[cache_key] = rid
        return rid

    def execute(self, operation: str, module_name: str, ansible_data_dict=None, **kwargs) -> dict:
        """
        Execute a generic operation on any resource.

        This is the main entry point called by action plugins.
        Uses the same shared CRUD logic as PlatformService.

        Args:
            operation: Operation type ('create', 'update', 'delete', 'find')
            module_name: Module name (e.g., 'user', 'organization')
            ansible_data_dict: Ansible dataclass or dict
        kwargs: Optional alias: ansible_data (matches ManagerRPCClient API)

        Returns:
            Result as dict (Ansible format) with timing information

        Raises:
            ValueError: If operation is unknown or execution fails
        """
        from dataclasses import asdict, is_dataclass

        # Support callers that pass ansible_data= as a keyword argument.
        if ansible_data_dict is None and "ansible_data" in kwargs:
            ansible_data_dict = kwargs.get("ansible_data")

        # Convert to dict if dataclass (for consistency with ManagerRPCClient)
        if is_dataclass(ansible_data_dict):
            ansible_data_dict = asdict(ansible_data_dict)
        # else: already a dict

        logger.info("Executing %s on %s", operation, module_name)

        # Lazy initialization: Authenticate on first request
        if not self._authenticated:
            try:
                self._authenticate()
                self._authenticated = True
                logger.info("DirectHTTPClient: Authentication successful")
            except Exception as e:
                logger.error("DirectHTTPClient: Authentication failed: %s", e)
                self._last_auth_error = e
                raise

        # Lazy initialization: Detect API version on first request
        if self.api_version is None:
            try:
                self.api_version = self._detect_api_version()
                logger.info("DirectHTTPClient: API version detected: v%s", self.api_version)
            except Exception as e:
                logger.warning("DirectHTTPClient: Version detection failed: %s, defaulting to v1", e)
                self.api_version = "1"
            self.session.headers.update({"X-API-Version": str(self.api_version)})

        # Load version-appropriate classes (shared layer)
        AnsibleClass, APIClass, MixinClass = self.loader.load_classes_for_module(module_name, self.api_version)
        # Pop action-only flags before building dataclass (action sets _platform_enforced for enforced state)
        include_nulls = ansible_data_dict.pop("_platform_enforced", False)

        # Reconstruct Ansible dataclass
        ansible_instance = AnsibleClass(**ansible_data_dict)

        # Build transformation context (using dataclass for type safety)
        context = TransformContext(
            manager=self, session=self.session, cache=self.cache, api_version=self.api_version, operation=operation, include_nulls_for_update=include_nulls
        )

        # Execute operation (shared CRUD logic)
        try:
            if operation == "create":
                result = self._create_resource(ansible_instance, MixinClass, context)
            elif operation == "update":
                result = self._update_resource(ansible_instance, MixinClass, context)
            elif operation == "delete":
                result = self._delete_resource(ansible_instance, MixinClass, context)
            elif operation == "find":
                result = self._find_resource(ansible_instance, MixinClass, context)
            else:
                raise ValueError(f"Unknown operation: {operation}")

            return result

        except Exception as e:
            logger.error("Operation %s on %s failed: %s", operation, module_name, e)
            raise

    # CRUD operation methods (shared logic - same as PlatformService)
    # These will be extracted to a shared module later, but for now
    # we'll duplicate them here to get standard mode working

    def _create_resource(self, ansible_data: Any, mixin_class: type, context: TransformContext) -> dict:
        """Create resource with transformation."""
        # FORWARD TRANSFORM: Ansible -> API
        logger.info("DirectHTTPClient: Forward transform for %s: %s", mixin_class.__name__, ansible_data)
        api_data = mixin_class.from_ansible_data(ansible_data, context)
        logger.info("DirectHTTPClient: API data for %s: %s", mixin_class.__name__, api_data)
        # Get endpoint operations from mixin
        operations = mixin_class.get_endpoint_operations()
        logger.info("DirectHTTPClient: Operations for %s: %s", mixin_class.__name__, operations)
        # Execute operations (potentially multi-endpoint)
        api_result = self._execute_operations(operations, api_data, context, required_for="create")
        logger.info("DirectHTTPClient: API result for %s: %s", mixin_class.__name__, api_result)

        # REVERSE TRANSFORM: API -> Ansible
        if api_result:
            # from_api returns AnsibleUser dataclass
            ansible_instance = mixin_class.from_api(api_result, context)
            from dataclasses import asdict

            ansible_result = asdict(ansible_instance)
            ansible_result["changed"] = True
            logger.info("DirectHTTPClient: Ansible result for %s: %s", mixin_class.__name__, ansible_result)
            return ansible_result

        return {"changed": True}

    def _update_resource(self, ansible_data: Any, mixin_class: type, context: TransformContext) -> dict:
        """Update resource with transformation."""
        # Get the resource ID (not required for singleton resources)
        resource_id = getattr(ansible_data, "id", None)
        is_singleton = getattr(mixin_class, "is_singleton", False)
        if not resource_id and not is_singleton:
            raise ValueError("Resource ID required for update operation")

        # Fetch current state for comparison
        try:
            current_data = self._find_resource(ansible_data, mixin_class, context)
        except Exception:
            current_data = {}

        # FORWARD TRANSFORM: Ansible -> API
        api_data = mixin_class.from_ansible_data(ansible_data, context)

        # Get endpoint operations from mixin
        operations = mixin_class.get_endpoint_operations()

        # Pre-PATCH idempotency check: compare only the fields we'd update.
        # Timestamps (modified, created, url) change on every PATCH so they
        # must be excluded from the comparison.
        _skip_for_idempotency = {"modified", "created", "url", "state"}
        update_op = operations.get("update")
        if update_op and update_op.fields and current_data:
            would_update = {}
            for field in update_op.fields:
                value = getattr(api_data, field, None)
                if value is not None:
                    would_update[field] = value
            needs_update = any(
                str(current_data.get(f)) != str(would_update[f])
                for f in would_update
                if f not in _skip_for_idempotency
                # Skip encrypted/write-only fields: the API returns "$encrypted$"
                # as a placeholder for hashed values (passwords, secrets). These
                # can never be meaningfully compared to the plaintext desired value,
                # so we always treat them as already correct and skip the PATCH for
                # that field — same logic as AAPModule.fields_could_be_same().
                and current_data.get(f) != "$encrypted$"
            )
            if not needs_update:
                # Nothing to change — return current state with changed=False
                result = dict(current_data)
                result["changed"] = False
                return result

        # Execute update operation
        api_result = self._execute_operations(operations, api_data, context, required_for="update")

        # REVERSE TRANSFORM: API -> Ansible
        if api_result:
            # from_api returns AnsibleUser dataclass
            ansible_instance = mixin_class.from_api(api_result, context)
            from dataclasses import asdict

            ansible_result = asdict(ansible_instance)
            # We actually sent a PATCH so this is a real change
            ansible_result["changed"] = True
            return ansible_result

        return {"changed": False}

    def _delete_resource(self, ansible_data: Any, mixin_class: type, context: TransformContext) -> dict:
        """Delete resource."""
        # Get the resource ID
        resource_id = getattr(ansible_data, "id", None)
        if not resource_id:
            raise ValueError("Resource ID required for delete operation")

        # Get endpoint operations from mixin
        operations = mixin_class.get_endpoint_operations()
        delete_op = operations.get("delete")

        if not delete_op:
            raise ValueError(f"Delete operation not defined for {mixin_class.__name__}")

        # Build URL
        url = self._build_url(delete_op.path.format(id=resource_id))

        # Execute delete
        _response = self._make_request(delete_op.method, url, operation="delete", resource=mixin_class.__name__)

        return {"changed": True, "deleted": True}

    def _find_resource(self, ansible_data: Any, mixin_class: type, context: TransformContext) -> dict:
        """Find resource by lookup field.

        Supports three modes:
        1. Singleton (mixin.is_singleton=True): GET the fixed endpoint path directly
        2. ID lookup: GET /resource/{id}/
        3. List+filter: GET /resource/?field=value (including composite-key lookups)
        """
        # Get endpoint operations from mixin
        operations = mixin_class.get_endpoint_operations()
        get_op = operations.get("get")
        list_op = operations.get("list")

        # --- Singleton resources (e.g. settings) ---
        if getattr(mixin_class, "is_singleton", False):
            if not get_op:
                raise ValueError(f"No GET operation defined for singleton {mixin_class.__name__}")
            url = self._build_url(get_op.path)
            with self._lock:
                self._http_request_count += 1
            response = self._make_request(get_op.method, url, operation="find", resource=mixin_class.__name__)
            try:
                response_body = response.read()
                api_result = json.loads(response_body) if response_body else {}
            except Exception:
                api_result = {}
            ansible_instance = mixin_class.from_api(api_result, context)
            from dataclasses import asdict

            return asdict(ansible_instance)

        # --- Standard CRUD resources ---
        if not list_op:
            raise ValueError(f"List operation not defined for {mixin_class.__name__}")

        # Get lookup field from mixin
        lookup_field = mixin_class.get_lookup_field()
        logger.info("DirectHTTPClient: Lookup field for %s: %s", mixin_class.__name__, lookup_field)
        lookup_value = getattr(ansible_data, lookup_field, None)
        logger.info("DirectHTTPClient: Lookup value for %s: %s", mixin_class.__name__, lookup_field)

        # Compute composite-key query params first so they can be used both in
        # ID-based validation and in the list-based fallback path.
        composite_params = {}
        if hasattr(mixin_class, "get_find_list_query_params"):
            try:
                api_data_for_find = mixin_class.from_ansible_data(ansible_data, context)
                composite_params = mixin_class.get_find_list_query_params(api_data_for_find) or {}
            except Exception as cp_exc:
                logger.debug("DirectHTTPClient: composite params computation failed: %s", cp_exc)
                raise

        # --- ID-based direct lookup: if the lookup value is a bare integer ---
        # (or a digit string), the caller is referencing the resource by its
        # primary key rather than its name.  Use GET /resource/{id}/ directly
        # instead of a list-filter, which would find nothing.
        if get_op and lookup_value is not None and str(lookup_value).strip().isdigit():
            try:
                id_url = self._build_url(get_op.path.format(id=int(str(lookup_value).strip())))
                logger.info("DirectHTTPClient: ID-based lookup URL for %s: %s", mixin_class.__name__, id_url)
                with self._lock:
                    self._http_request_count += 1
                id_response = self._make_request(get_op.method, id_url, operation="find", resource=mixin_class.__name__)
                id_body = id_response.read()
                id_data = json.loads(id_body) if id_body else {}
                if id_data.get("id"):
                    # Validate composite-key constraints against the fetched resource.
                    # E.g. a team looked up by integer PK must still belong to the
                    # expected organization.  If a composite field doesn't match,
                    # treat the resource as not found so callers get a no-op.
                    composite_match = True
                    for param_key, param_val in composite_params.items():
                        result_val = id_data.get(param_key)
                        try:
                            pv = int(param_val)
                        except (TypeError, ValueError):
                            pv = param_val
                        try:
                            rv = int(result_val) if result_val is not None else None
                        except (TypeError, ValueError):
                            rv = result_val
                        if rv != pv:
                            composite_match = False
                            break
                    if composite_match:
                        ansible_instance = mixin_class.from_api(id_data, context)
                        from dataclasses import asdict

                        logger.info("DirectHTTPClient: ID-based lookup succeeded for %s id=%s", mixin_class.__name__, lookup_value)
                        return asdict(ansible_instance)
                    else:
                        raise ValueError(f"Resource {lookup_value} found but composite key constraints {composite_params} do not match")
            except Exception as id_exc:
                logger.info("DirectHTTPClient: ID-based lookup failed for %s id=%s: %s", mixin_class.__name__, lookup_value, id_exc)
                raise

        if not lookup_value and not composite_params:
            raise ValueError(f"Lookup field '{lookup_field}' not found in data")
        query_params = {}
        if lookup_value:
            query_params[lookup_field] = lookup_value
        if composite_params:
            query_params.update(composite_params)
        # Build URL with query parameter(s)
        url = self._build_url(list_op.path, query_params)
        logger.info("DirectHTTPClient: URL for %s: %s", mixin_class.__name__, url)
        # Execute list request
        logger.info("DirectHTTPClient: About to call _make_request for find: method=%s, url=%s", list_op.method, url)
        try:
            # Increment HTTP request counter (thread-safe)
            with self._lock:
                self._http_request_count += 1
            logger.info("DirectHTTPClient: HTTP request counter incremented for find: %s", self._http_request_count)
            response = self._make_request(list_op.method, url, operation="find", resource=mixin_class.__name__)
            logger.info("DirectHTTPClient: Response for %s: %s", mixin_class.__name__, response)
        except Exception as req_e:
            logger.error("DirectHTTPClient: _make_request for find raised exception: %s", req_e)
            import traceback

            logger.error("DirectHTTPClient: _make_request for find traceback: %s", traceback.format_exc())
            raise
        # Parse response - Ansible's Request response uses .read() to get body
        try:
            response_body = response.read()
            response_data = json.loads(response_body) if response_body else {}
        except Exception as e:
            logger.error("DirectHTTPClient: Failed to parse response: %s", e)
            response_data = {}
        results = response_data.get("results", [])
        logger.info("DirectHTTPClient: Results for %s: %s", mixin_class.__name__, results)
        if results:
            # Return first match
            api_data = results[0]
            # from_api returns AnsibleUser dataclass, convert to dict for return
            ansible_instance = mixin_class.from_api(api_data, context)
            logger.info("DirectHTTPClient: Ansible instance for %s: %s", mixin_class.__name__, ansible_instance)
            from dataclasses import asdict

            return asdict(ansible_instance)

        # Not found
        raise ValueError(f"Resource not found: {lookup_field}={lookup_value}")

    def _execute_operations(self, operations: Dict, api_data: Any, context: TransformContext, required_for: str = None) -> dict:
        """
        Execute endpoint operations (potentially multi-endpoint).

        This handles operations that may require multiple API calls
        (e.g., create user, then associate organizations).
        """
        results = {}
        logger.info("DirectHTTPClient: Executing operations for %s: %s", operations, api_data)

        # Filter operations by required_for
        relevant_ops = {name: op for name, op in operations.items() if op.required_for == required_for or required_for is None}
        logger.info("DirectHTTPClient: Relevant operations for %s: %s", operations, relevant_ops)
        # Sort by order
        sorted_ops = sorted(relevant_ops.items(), key=lambda x: x[1].order)

        for op_name, endpoint_op in sorted_ops:
            # Check dependencies
            if endpoint_op.depends_on and endpoint_op.depends_on not in results:
                continue
            logger.info("DirectHTTPClient: Checking dependencies for %s: %s", endpoint_op, endpoint_op.depends_on)
            # Build URL
            url = endpoint_op.path
            logger.info("DirectHTTPClient: Building URL for %s: %s", endpoint_op, url)
            if endpoint_op.path_params:
                # Replace path parameters
                for param in endpoint_op.path_params:
                    param_value = results.get("id") or getattr(api_data, "id", None)
                    if param_value:
                        url = url.replace(f"{{{param}}}", str(param_value))
            logger.info("DirectHTTPClient: URL after replacing path parameters: %s", url)
            url = self._build_url(url)
            logger.info("DirectHTTPClient: URL after building URL: %s", url)
            # Prepare request data; include "" on update so enforced can clear e.g. email
            request_data = {}
            if endpoint_op.fields:
                for field in endpoint_op.fields:
                    value = getattr(api_data, field, None)
                    if value is None:
                        continue
                    request_data[field] = value

            # flatten_body: send the dict field value as the body directly (e.g. settings)
            if getattr(endpoint_op, "flatten_body", False) and len(request_data) == 1:
                request_data = next(iter(request_data.values()))

            # Skip secondary (dependent) operations that have no data to send.
            # This prevents calling e.g. /users/{id}/organizations/ when organizations is not set.
            if endpoint_op.depends_on and not request_data:
                logger.info("DirectHTTPClient: Skipping secondary operation %s (no data to send)", op_name)
                continue

            try:
                # Increment HTTP request counter (thread-safe)
                with self._lock:
                    self._http_request_count += 1
                response = self._make_request(
                    endpoint_op.method,
                    url,
                    json=request_data,
                    operation=op_name,
                    resource=endpoint_op.path.split("/")[-2] if "/" in endpoint_op.path else "unknown",
                )

            except Exception as e:
                logger.error("DirectHTTPClient: API call failed: %s", e)
                if hasattr(e, "code"):
                    logger.error("Response status: %s", e.code)
                elif hasattr(e, "response") and e.response is not None:
                    status = getattr(e.response, "status", getattr(e.response, "code", "unknown"))
                    logger.error("Response status: %s", status)
                raise

            # Store result - Ansible's Request response uses .read() to get body
            try:
                response_body = response.read()
                result_data = json.loads(response_body) if response_body else {}
            except Exception as e:
                logger.warning("DirectHTTPClient: Failed to parse response JSON: %s", e)
                result_data = {}
            results[op_name] = result_data

            # Store ID for dependent operations
            if "id" in result_data and "id" not in results:
                results["id"] = result_data["id"]

        # Return main result
        return results.get("create") or results.get("update") or results.get("get") or results

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

    def direct_request(self, method: str, path: str, data=None) -> dict:
        """
        Make a raw authenticated HTTP request and return parsed JSON.

        Used by action plugins for non-standard endpoints (e.g. settings/all/).

        Args:
            method: HTTP method ('GET', 'PATCH', 'POST', 'PUT', 'DELETE')
            path: API path (e.g. '/api/gateway/v1/settings/all/')
            data: Optional dict to JSON-encode as request body

        Returns:
            Parsed JSON response dict (empty dict on empty body)
        """
        if not self._authenticated:
            self._authenticate()
            self._authenticated = True

        if self.api_version is None:
            try:
                self.api_version = self._detect_api_version()
            except Exception:
                self.api_version = "1"
            self.session.headers.update({"X-API-Version": str(self.api_version)})

        url = self._build_url(path)
        kwargs = {}
        if data is not None:
            kwargs["data"] = json.dumps(data).encode("utf-8")

        response = self._make_request(method.upper(), url, operation="direct_request", resource=path, **kwargs)
        try:
            response_body = response.read()
            return json.loads(response_body) if response_body else {}
        except Exception:
            return {}
