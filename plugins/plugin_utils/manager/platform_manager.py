"""Platform Manager - Persistent service for API communication.

This module provides the server-side manager that maintains persistent
connections to the platform API and handles all data transformations.
"""

from __future__ import annotations

import base64
import logging
import threading
import time
from dataclasses import asdict
from multiprocessing.managers import BaseManager
from socketserver import ThreadingMixIn
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple
from urllib.parse import urlencode

if TYPE_CHECKING:
    import requests

from ..platform.base_client import BaseAPIClient
from ..platform.config import GatewayConfig
from ..platform.credential_manager import get_credential_manager
from ..platform.exceptions import AuthenticationError
from ..platform.retry import RetryConfig, retry_http_request
from ..platform.types import TransformContext

logger = logging.getLogger(__name__)


def _get_requests():
    """Lazy import of requests to avoid ModuleNotFoundError during sanity import test."""
    import requests

    return requests


class PlatformService(BaseAPIClient):
    """
    Persistent platform service for experimental connection mode.

    This service maintains a persistent connection and handles all resource operations
    generically. It performs all transformations and API calls.

    Inherits from BaseAPIClient and shares the same interface as DirectHTTPClient:
    - Version detection (APIVersionRegistry, DynamicClassLoader)
    - Error taxonomy (exceptions.py, retry.py)
    - Credential management (credential_manager.py)
    - CRUD operations (transform mixins, endpoint operations)
    - Optimizations (caching, lookup helpers)

    Attributes (from BaseAPIClient):
        base_url: Platform base URL
        api_version: Detected/cached API version
        registry: Version registry
        loader: Class loader
        cache: Lookup cache (org names ↔ IDs, etc.)

    Additional Attributes:
        session: Persistent HTTP session (requests.Session)
        username: Authentication username
        password: Authentication password
        oauth_token: OAuth token for authentication
        verify_ssl: SSL verification flag
    """

    def __init__(self, config: GatewayConfig):
        """
        Initialize platform service.

        Args:
            config: Gateway configuration
        """
        super().__init__(config)

        self.credential_manager = get_credential_manager()
        self.credential_store = self.credential_manager.get_or_create_store(
            gateway_url=self.base_url,
            username=config.username,
            password=config.password,
            oauth_token=config.oauth_token,
            process_id=str(id(self)),  # Use object ID as process identifier
        )

        self.namespace_id = self.credential_store.namespace.namespace_id
        self.username, self.password, self.oauth_token = self.credential_store.get_auth_credentials()

        requests = _get_requests()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Ansible Platform Collection", "Accept": "application/json", "Content-Type": "application/json"})

        self._auth_lock = threading.Lock()
        self._last_auth_error = None

        try:
            self._authenticate()
            logger.info("PlatformService: Authentication successful")
        except Exception as e:
            logger.error("PlatformService: Authentication failed: %s", e)
            self._last_auth_error = e
            # Continue anyway - some operations might work without auth

        self.api_version = self._detect_api_version()
        self.session.headers.update({"X-API-Version": str(self.api_version)})
        logger.info("PlatformService initialized with API v%s", self.api_version)

        self._http_request_count = 0
        self._tls_handshake_count = 1  # 1 handshake when session is created
        self._lock = threading.Lock()

        self._shutdown_requested = False
        self._shutdown_lock = threading.Lock()

        # Idle timeout: last time the service handled user-facing work (RPC / HTTP)
        self._activity_lock = threading.Lock()
        self._last_activity_monotonic = time.monotonic()

        self.retry_config = RetryConfig(max_attempts=3, initial_delay=1.0, max_delay=60.0, exponential_base=2.0, jitter=True)

    def record_activity(self) -> None:
        """Mark the service as recently active (RPC or HTTP traffic)."""
        with self._activity_lock:
            self._last_activity_monotonic = time.monotonic()

    def seconds_since_last_activity(self) -> float:
        """Wall-clock elapsed seconds since the last record_activity() call."""
        with self._activity_lock:
            return time.monotonic() - self._last_activity_monotonic

    def should_exit_for_idle(self) -> bool:
        """True if idle_timeout is enabled and exceeded (and not already shutting down)."""
        if self.config.idle_timeout <= 0:
            return False
        with self._shutdown_lock:
            if self._shutdown_requested:
                return False
        return self.seconds_since_last_activity() >= self.config.idle_timeout

    def _make_request(self, method: str, url: str, operation: str = "http_request", resource: str = "unknown", **kwargs) -> "requests.Response":
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
        self.record_activity()

        @retry_http_request(config=self.retry_config)
        def _execute_with_retry():
            request_kwargs = kwargs.copy()
            if "timeout" not in request_kwargs:
                request_kwargs["timeout"] = self.request_timeout
            if "verify" not in request_kwargs:
                request_kwargs["verify"] = self.verify_ssl

            session_method = getattr(self.session, method.lower())

            # Track request count
            with self._lock:
                self._http_request_count += 1

            response = session_method(url, **request_kwargs)

            if response.status_code >= 400:
                if response.status_code == 401:
                    if self._handle_auth_error(response):
                        response = session_method(url, **request_kwargs)
                        if response.status_code == 401:
                            raise AuthenticationError(
                                message=f"Authentication failed: HTTP {response.status_code}",
                                operation=operation,
                                resource=resource,
                                details={"status_code": response.status_code, "url": url, "response_body": response.text[:500]},
                                status_code=response.status_code,
                            )
                    else:
                        raise AuthenticationError(
                            message=f"Authentication failed: HTTP {response.status_code}",
                            operation=operation,
                            resource=resource,
                            details={"status_code": response.status_code, "url": url, "response_body": response.text[:500]},
                            status_code=response.status_code,
                        )

                response.raise_for_status()

            return response

        return _execute_with_retry()

    def _authenticate(self) -> None:
        """Authenticate with the platform API."""
        requests = _get_requests()
        with self._auth_lock:
            username, password, oauth_token = self.credential_store.get_auth_credentials()

            # Use base URL — API version not known yet
            url = self.base_url

            if oauth_token:
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
                basic_str = base64.b64encode(f"{username}:{password}".encode("ascii"))
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

        # Record activity so the idle monitor does not count auth work as idle time
        self.record_activity()

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

            # Note: actual refresh endpoint depends on Gateway API
            try:
                refresh_url = f"{self.base_url}/api/gateway/v1/auth/token/refresh/"
                response = self.session.post(
                    refresh_url, json={"refresh_token": token_info.refresh_token}, timeout=self.request_timeout, verify=self.verify_ssl
                )

                if response.status_code == 200:
                    data = response.json()
                    new_token = data.get("access_token")
                    new_refresh_token = data.get("refresh_token", token_info.refresh_token)
                    expires_in = data.get("expires_in")

                    if new_token:
                        self.credential_store.update_token(token=new_token, refresh_token=new_refresh_token, expires_in=expires_in)
                        self.session.headers.update({"Authorization": f"Bearer {new_token}"})
                        logger.info("Token refreshed successfully")
                        # Record activity so the idle monitor does not treat a token refresh as idle time
                        self.record_activity()
                        return True
            except Exception as e:
                logger.warning("Token refresh failed: %s", e)

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
            logger.error("Re-authentication failed: %s", e)
            return False

    def _handle_auth_error(self, response: "requests.Response") -> bool:
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

        creds = self.credential_store.get_auth_credentials()
        oauth_token = creds[2] if len(creds) > 2 else None
        if oauth_token and self._refresh_token():
            logger.info("Authentication recovered via token refresh")
            return True

        if self._re_authenticate():
            logger.info("Authentication recovered via re-authentication")
            return True

        logger.error("Failed to recover authentication")
        return False

    def _detect_api_version(self) -> str:
        """
        Detect platform API version dynamically from the live Gateway.

        Detection order:
          1. GET /api/gateway/v1/ping/ — read X-API-Version response header.
             If the ping returns 200 with no header, the /v1/ path is reachable
             so v1 is confirmed.  The JSON body is NOT parsed: the "version"
             field on this endpoint contains the *product* version (e.g. "2.6"
             for AAP Gateway 2.6.x), not the API version.
          2. If the ping endpoint returns non-2xx (older servers), fall back to
             GET /api/gateway/ and parse its X-API-Version header or
             ``current_version`` field.

        If all tiers fail, default to ``'1'``.  Never fall back to
        get_latest_version() — a collection that ships v2 must not assume
        the server supports v2.

        Returns:
            Version string (e.g., '1', '2')
        """
        requests = _get_requests()
        import os
        import re
        import sys
        from pathlib import Path

        supported = self.registry.get_supported_versions()

        _error_log_path = None
        try:
            socket_dir = os.environ.get("ANSIBLE_PLATFORM_SOCKET_DIR")
            if socket_dir:
                inventory_hostname = os.environ.get("ANSIBLE_PLATFORM_HOSTNAME", "localhost")
                _error_log_path = Path(socket_dir) / f"manager_error_{inventory_hostname}.log"
        except Exception:
            pass

        def _hdr_version(resp) -> str:
            """Extract API version from X-API-Version header; return '' if absent."""
            raw = resp.headers.get("X-API-Version", "").lstrip("v")
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
            logger.debug("PlatformService: version detection tier-1 %s", ping_url)

            response = self.session.get(ping_url, timeout=self.request_timeout, verify=self.verify_ssl)
            response.raise_for_status()

            # Only trust the X-API-Version header from the ping endpoint.
            # The JSON body "version" field is the *product* version
            # (e.g. "2.6" for AAP Gateway 2.6.x), NOT the API version.
            # Parsing it would map "2.6" -> major "2" and select the wrong
            # API version on a server that only serves v1 paths.
            v = _hdr_version(response)
            if v:
                logger.info("PlatformService: API version locked in (tier-1 header): v%s", v)
                return v

            # Ping at /api/gateway/v1/ping/ succeeded but no X-API-Version header.
            # Successfully reaching the /v1/ path confirms API v1 is available.
            logger.info("PlatformService: tier-1 ping succeeded, no X-API-Version header — v1 confirmed")
            if "1" in supported:
                return "1"

        except requests.RequestException as e:
            logger.debug("PlatformService: tier-1 ping failed (%s) — trying tier-2", e)
        except Exception as e:
            logger.debug("PlatformService: tier-1 unexpected error (%s) — trying tier-2", e)

        # ── Tier 2: /api/gateway/ (all v1 servers expose this) ────────────
        try:
            root_url = f"{self.base_url.rstrip('/')}/api/gateway/"
            logger.debug("PlatformService: version detection tier-2 %s", root_url)

            response = self.session.get(root_url, timeout=self.request_timeout, verify=self.verify_ssl)
            response.raise_for_status()

            v = _hdr_version(response)
            if v:
                logger.info("PlatformService: API version locked in (tier-2 header): v%s", v)
                return v

            if response.headers.get("Content-Type", "").startswith("application/json"):
                try:
                    body = response.json()
                    # current_version: "/api/gateway/v1/" or "1"
                    if "current_version" in body:
                        m = re.search(r"/v(\d+(?:\.\d+)?)/?$", str(body["current_version"]))
                        raw = m.group(1) if m else str(body["current_version"]).lstrip("v")
                        if raw in supported:
                            logger.info("PlatformService: API version locked in (tier-2 body): v%s", raw)
                            return raw
                        major = raw.split(".")[0]
                        if major in supported:
                            logger.info("PlatformService: API version locked in (tier-2 body major): v%s", major)
                            return major
                    # NOTE: "version" and "available_versions" are intentionally NOT
                    # parsed — "version" is the product version; "available_versions"
                    # lists routing, not collection endpoint compatibility.
                except (ValueError, KeyError, AttributeError) as e:
                    logger.debug("PlatformService: tier-2 body parse error: %s", e)

        except requests.RequestException as e:
            error_msg = f"PlatformService: tier-2 version detection failed: {e}"
            logger.warning(error_msg)
            print(error_msg, file=sys.stderr, flush=True)
        except Exception as e:
            logger.warning("PlatformService: tier-2 unexpected error: %s", e)

        # ── Tier 3: safe default ───────────────────────────────────────────
        if not supported:
            raise RuntimeError("CRITICAL: No API versions discovered in the collection's api/ directory!")
        logger.warning("PlatformService: version detection failed — defaulting to v1")
        if "1" in supported:
            return "1"
        return supported[0]

    def _build_url(self, endpoint: str, query_params: Optional[Dict] = None) -> str:
        """
        Build full URL for an endpoint.

        Args:
            endpoint: API endpoint path
            query_params: Optional query parameters

        Returns:
            Full URL string
        """
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

    def execute(self, operation: str, module_name: str, ansible_data_dict: dict) -> dict:
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
        self.record_activity()
        logger.info("Executing %s on %s", operation, module_name)

        # Pop action-only flags before building dataclass (action sets _platform_enforced for enforced state)
        include_nulls = ansible_data_dict.pop("_platform_enforced", False)

        AnsibleClass, APIClass, MixinClass = self.loader.load_classes_for_module(module_name, self.api_version)
        ansible_instance = AnsibleClass(**ansible_data_dict)
        context = TransformContext(
            manager=self, session=self.session, cache=self.cache, api_version=self.api_version, operation=operation, include_nulls_for_update=include_nulls
        )

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

        except ValueError as e:
            # "Resource not found" is expected during idempotency checks
            if "not found" in str(e):
                logger.debug("Operation %s on %s: %s", operation, module_name, e)
            else:
                logger.error("Operation %s on %s failed: %s", operation, module_name, e)
            raise
        except Exception as e:
            logger.error("Operation %s on %s failed: %s", operation, module_name, e, exc_info=True)
            raise

    def _create_resource(self, ansible_data: Any, mixin_class: type, context: dict) -> dict:
        """
        Create resource with transformation.

        Args:
            ansible_data: Ansible dataclass instance
            mixin_class: Transform mixin class
            context: Transformation context

        Returns:
            Created resource as dict (Ansible format) with 'changed': True
        """
        # FORWARD TRANSFORM: Ansible -> API
        api_data = mixin_class.from_ansible_data(ansible_data, context)

        operations = mixin_class.get_endpoint_operations()
        api_result = self._execute_operations(operations, api_data, context, required_for="create")

        # REVERSE TRANSFORM: API -> Ansible
        if api_result:
            ansible_instance = mixin_class.from_api(api_result, context)
            from dataclasses import asdict

            ansible_result = asdict(ansible_instance)
            ansible_result["changed"] = True
            return ansible_result

        return {"changed": True}

    def _update_resource(self, ansible_data: Any, mixin_class: type, context: dict) -> dict:
        """
        Update resource with transformation.

        Args:
            ansible_data: Ansible dataclass instance
            mixin_class: Transform mixin class
            context: Transformation context

        Returns:
            Updated resource as dict (Ansible format) with 'changed': True/False
        """
        resource_id = getattr(ansible_data, "id", None)
        is_singleton = getattr(mixin_class, "is_singleton", False)
        if not resource_id and not is_singleton:
            raise ValueError("Resource ID required for update operation")

        try:
            current_data = self._find_resource(ansible_data, mixin_class, context)
        except Exception:
            # If we can't fetch current state, assume change
            current_data = {}

        # FORWARD TRANSFORM: Ansible -> API
        api_data = mixin_class.from_ansible_data(ansible_data, context)
        operations = mixin_class.get_endpoint_operations()

        # Snapshot which fields are None after the forward transform — these are
        # fields the user did NOT explicitly provide.  We need this before the
        # current-data merge so we can later distinguish "restored from server"
        # fields from "user-supplied" fields when computing fields_to_null.
        update_op = next((op for op in operations.values() if getattr(op, "required_for", None) == "update"), None)
        user_unset_fields = set()
        if update_op:
            for field in getattr(update_op, "fields", []) or []:
                if getattr(api_data, field, None) is None:
                    user_unset_fields.add(field)

        # For update, some APIs require all required fields in the PATCH body (e.g. http_port
        # requires "number"). Merge current resource values for any update-operation field
        # that is missing/None in api_data so the request body is valid.
        if update_op and current_data:
            current_dict = current_data if isinstance(current_data, dict) else current_data
            for field in getattr(update_op, "fields", []) or []:
                if getattr(api_data, field, None) is None and current_dict.get(field) is not None:
                    setattr(api_data, field, current_dict[field])

        # After the merge, let the mixin declare which fields must be sent as
        # null to clear server-side values that are incompatible with the new
        # resource state (e.g. role/team when map_type changes to is_superuser).
        # Only fields the user did NOT explicitly provide are eligible — if the
        # user provided an incompatible field the API will reject it with a clear
        # validation error, which is the correct behaviour.
        fields_to_null: set = set()
        if hasattr(mixin_class, "get_fields_to_null_for_update"):
            candidate_fields = mixin_class.get_fields_to_null_for_update(api_data)
            for field in candidate_fields:
                if field in user_unset_fields:
                    fields_to_null.add(field)
                    setattr(api_data, field, None)  # keep api_data consistent

        api_result = self._execute_operations(operations, api_data, context, required_for="update", fields_to_null=fields_to_null)

        # REVERSE TRANSFORM: API -> Ansible
        if api_result:
            ansible_instance = mixin_class.from_api(api_result, context)
            from dataclasses import asdict

            new_dict = asdict(ansible_instance)
            current_dict = current_data if isinstance(current_data, dict) else {}
            read_only_fields = {"id", "created", "modified", "url", "changed"}

            # Merge current + PATCH response; don't let None from sparse response
            # overwrite existing values (e.g. associated_authenticators: {} -> None).
            merged = dict(current_dict)
            for k, v in new_dict.items():
                if v is not None or k not in merged:
                    merged[k] = v
            new_dict = merged

            # Primary: compare post-PATCH state vs pre-PATCH state.
            new_comparable = {k: v for k, v in new_dict.items() if k not in read_only_fields}
            current_comparable = {k: v for k, v in current_dict.items() if k not in read_only_fields}
            norm = self._normalize_for_compare
            changed = norm(new_comparable) != norm(current_comparable)

            # Secondary: compare each explicitly requested field against pre-PATCH state.
            # Catches sparse responses and fields the API ignores in its response.
            # Skip lookup field, state, API-normalized fields (e.g. slug), and internal
            # resolved fields (e.g. organization_id set by action plugin but not in API state).
            if not changed:
                lookup_field = mixin_class.get_lookup_field()
                api_normalized_fields = {"slug"}
                internal_fields = {"organization_id"}
                skip_fields = read_only_fields | {"state", lookup_field} | api_normalized_fields | internal_fields
                requested = asdict(ansible_data)
                for k, v in requested.items():
                    if k in skip_fields or v is None:
                        continue
                    if v == {} or v == []:
                        continue
                    current_val = current_dict.get(k)
                    if current_val is None and v is not None:
                        changed = True
                        break
                    if current_val is not None and norm(v) != norm(current_val):
                        # FK fields: user may provide a name string while the API
                        # stores an integer ID (e.g. http_port, service_cluster).
                        # The primary comparison already resolved both sides to
                        # integers via the API response, so skip string-vs-int
                        # mismatches here to avoid spurious changed=True.
                        if isinstance(v, str) and isinstance(current_val, int):
                            continue
                        # FK fields where from_api() converts int IDs to digit strings
                        # (e.g. service_cluster='5'): a non-digit name like 'eda-cluster'
                        # cannot be compared against a digit string without resolving it.
                        # The primary state comparison already handled the real change
                        # detection, so skip here to avoid false changed=True.
                        if isinstance(v, str) and isinstance(current_val, str) and not v.isdigit() and current_val.isdigit():
                            continue
                        changed = True
                        break

            new_dict["changed"] = changed
            return new_dict

        # No PATCH was needed (all requested fields are non-PATCH, e.g. organizations).
        # Still compare requested intent against current state so we report the change.
        from dataclasses import asdict

        current_dict = current_data if isinstance(current_data, dict) else {}
        if current_dict:
            read_only_fields = {"id", "created", "modified", "url", "changed"}
            api_normalized_fields = {"slug"}
            internal_fields = {"organization_id"}
            norm = self._normalize_for_compare
            lookup_field = mixin_class.get_lookup_field()
            skip_fields = read_only_fields | {"state", lookup_field} | api_normalized_fields | internal_fields
            requested = asdict(ansible_data)
            changed = False
            for k, v in requested.items():
                if k in skip_fields or v is None:
                    continue
                if v == {} or v == []:
                    continue
                current_val = current_dict.get(k)
                if current_val is None and v is not None:
                    changed = True
                    break
                if current_val is not None and norm(v) != norm(current_val):
                    # FK: str name vs int ID
                    if isinstance(v, str) and isinstance(current_val, int):
                        continue
                    # FK: non-digit name string vs digit string (from_api str() conversion)
                    # e.g. role_definition='my-role' vs '3100' — can't resolve without manager.
                    if isinstance(v, str) and isinstance(current_val, str) and not v.isdigit() and current_val.isdigit():
                        continue
                    changed = True
                    break
            result = dict(current_dict)
            result["changed"] = changed
            return result

        return {"changed": False}

    @staticmethod
    def _normalize_for_compare(value: Any) -> Any:
        """Normalize a value for change comparison so representation differences (e.g. int vs str dict keys) don't cause false changes."""
        if isinstance(value, dict):
            return {str(k): PlatformService._normalize_for_compare(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
        if isinstance(value, list):
            return [PlatformService._normalize_for_compare(item) for item in value]
        return value

    @staticmethod
    def _deep_merge_for_compare(current: Any, requested: Any) -> Any:
        """Merge current and requested for comparison; requested wins on conflicts.

        Preserves API-only keys in current so idempotent runs don't false-positive.
        """
        if not isinstance(current, dict) or not isinstance(requested, dict):
            return requested
        result = {}
        all_keys = set(str(k) for k in current) | set(str(k) for k in requested)
        for key in sorted(all_keys):
            c = current.get(key) if key in current else current.get(int(key)) if key.isdigit() else None
            r = requested.get(key) if key in requested else requested.get(int(key)) if key.isdigit() else None
            if r is None:
                result[key] = c
            elif c is None:
                result[key] = r
            elif isinstance(c, dict) and isinstance(r, dict):
                result[key] = PlatformService._deep_merge_for_compare(c, r)
            else:
                result[key] = r
        return result

    def _delete_resource(self, ansible_data: Any, mixin_class: type, context: dict) -> dict:
        """
        Delete resource.

        Args:
            ansible_data: Ansible dataclass instance
            mixin_class: Transform mixin class
            context: Transformation context

        Returns:
            Empty dict (resource deleted)
        """
        operations = mixin_class.get_endpoint_operations()

        delete_op = None
        for op_name, op in operations.items():
            if op_name == "delete" or (op.required_for == "delete"):
                delete_op = op
                break

        if not delete_op:
            raise ValueError("No delete operation defined for this resource")

        resource_id = ansible_data.id
        if not resource_id:
            raise ValueError("Resource ID required for delete operation")

        path = delete_op.path
        if delete_op.path_params:
            for param in delete_op.path_params:
                if param == "id":
                    path = path.replace(f"{{{param}}}", str(resource_id))

        url = self._build_url(path)
        logger.debug("Calling DELETE %s", url)
        response = self.session.delete(url, timeout=self.request_timeout, verify=self.verify_ssl)
        response.raise_for_status()
        return {"changed": True, "id": resource_id}

    def _find_resource(self, ansible_data: Any, mixin_class: type, context: dict) -> dict:
        """
        Find resource by identifier.

        Supports three modes:
        1. Singleton (mixin.is_singleton=True): GET the fixed endpoint path directly
        2. ID lookup: GET /resource/{id}/
        3. List+filter: GET /resource/?field=value (including composite-key lookups)

        Args:
            ansible_data: Ansible dataclass instance
            mixin_class: Transform mixin class
            context: Transformation context

        Returns:
            Found resource as dict (Ansible format)
        """
        operations = mixin_class.get_endpoint_operations()
        get_op = operations.get("get")
        list_op = operations.get("list")

        # --- Singleton resources (e.g. settings) ---
        if getattr(mixin_class, "is_singleton", False):
            if not get_op:
                raise ValueError("No GET operation defined for singleton resource")
            url = self._build_url(get_op.path)
            response = self.session.get(url, timeout=self.request_timeout, verify=self.verify_ssl)
            response.raise_for_status()
            api_result = response.json()
            ansible_instance = mixin_class.from_api(api_result, context)
            from dataclasses import asdict

            return asdict(ansible_instance)

        lookup_field = mixin_class.get_lookup_field()
        unique_value = getattr(ansible_data, lookup_field, None) or getattr(ansible_data, "id", None)

        # Support composite-key lookups via get_find_list_query_params.
        # Use FK-resolved API data so query params contain IDs, not names.
        composite_params = {}
        if hasattr(mixin_class, "get_find_list_query_params"):
            api_data = mixin_class.from_ansible_data(ansible_data, context)
            composite_params = mixin_class.get_find_list_query_params(api_data) or {}

        if not unique_value and not composite_params:
            raise ValueError(f"Cannot find resource: no {lookup_field} or id provided")

        # Resolve the resource ID to use for a direct GET lookup.
        # Priority: explicit id field -> numeric name field (caller passed an int PK).
        resolved_id = None
        if hasattr(ansible_data, "id") and ansible_data.id:
            resolved_id = ansible_data.id
        elif unique_value is not None and str(unique_value).strip().isdigit():
            # Caller passed an integer as the lookup field (e.g. name=1001),
            # meaning "look up by primary key".  Use GET /resource/{id}/ directly.
            resolved_id = int(str(unique_value).strip())

        if resolved_id:
            if not get_op:
                raise ValueError("No GET operation defined for this resource")
            url = self._build_url(get_op.path.replace("{id}", str(resolved_id)))
            response = self.session.get(url, timeout=self.request_timeout, verify=self.verify_ssl)
            response.raise_for_status()
            api_result = response.json()

            # Validate composite-key constraints against the fetched resource.
            # Example: team looked up by integer PK must still belong to the
            # expected organization.  If any composite filter field doesn't match
            # what the API returned, treat the resource as not found so that
            # callers (e.g. state: absent with a wrong org) get a no-op.
            if composite_params:
                for param_key, param_val in composite_params.items():
                    result_val = api_result.get(param_key)
                    # Normalise both sides to int when possible for FK comparisons.
                    try:
                        param_val_cmp = int(param_val)
                    except (TypeError, ValueError):
                        param_val_cmp = param_val
                    try:
                        result_val_cmp = int(result_val) if result_val is not None else None
                    except (TypeError, ValueError):
                        result_val_cmp = result_val
                    if result_val_cmp != param_val_cmp:
                        raise ValueError(f"Resource {resolved_id} found but composite key {param_key}={param_val} does not match actual value {result_val}")
        else:
            if not list_op:
                raise ValueError("No LIST operation defined for this resource")
            query_params = {}
            if unique_value:
                query_params[lookup_field] = unique_value
            if composite_params:
                query_params.update(composite_params)
            url = self._build_url(list_op.path, query_params=query_params)
            logger.debug("Calling GET %s to find %s=%s (query_params=%s)", url, lookup_field, unique_value, query_params)
            response = self.session.get(url, timeout=self.request_timeout, verify=self.verify_ssl)
            response.raise_for_status()
            list_result = response.json()

            results = list_result.get("results", [])
            if not results:
                raise ValueError(f"Resource with {lookup_field}={unique_value} not found")
            api_result = results[0]

            # Some API list endpoints return incomplete data for certain fields
            # (e.g. the routes list omits idle_timeout_seconds / request_timeout_seconds
            # even when they have been explicitly set).  When the mixin declares
            # full_resource_lookup=True, follow up with a GET-by-ID so that
            # idempotency comparisons use the complete stored resource state.
            if getattr(mixin_class, "full_resource_lookup", False) and api_result.get("id") and get_op:
                full_url = self._build_url(get_op.path.replace("{id}", str(api_result["id"])))
                logger.debug("full_resource_lookup: GET %s for complete resource data", full_url)
                full_response = self.session.get(full_url, timeout=self.request_timeout, verify=self.verify_ssl)
                if full_response.ok:
                    api_result = full_response.json()

        # REVERSE TRANSFORM: API -> Ansible
        ansible_instance = mixin_class.from_api(api_result, context)
        from dataclasses import asdict

        return asdict(ansible_instance)

    def _execute_operations(self, operations: Dict, api_data: Any, context: dict, required_for: str = None, fields_to_null: set = None) -> dict:
        """
        Execute potentially multiple API endpoint operations.

        Args:
            operations: Dict of EndpointOperations
            api_data: API dataclass instance
            context: Context
            required_for: Filter operations by required_for field
            fields_to_null: Optional set of field names that must be sent as
                explicit null in the request body, even though their value in
                api_data is None.  Used to clear server-side fields that are
                incompatible with a new resource state (e.g. role/team when
                map_type changes to is_superuser).

        Returns:
            Combined API response dict
        """
        relevant_ops = {name: op for name, op in operations.items() if op.required_for is None or op.required_for == required_for}
        sorted_ops = self._sort_operations(relevant_ops)

        results = {}
        api_data_dict = asdict(api_data)
        _fields_to_null = fields_to_null or set()

        for op_name in sorted_ops:
            endpoint_op = relevant_ops[op_name]

            # For update: include "" (empty string) so enforced can clear fields like email
            request_data = {}
            for field in endpoint_op.fields:
                if field not in api_data_dict:
                    continue
                val = api_data_dict[field]
                if val is None:
                    # Include as explicit null only for fields declared by the mixin
                    # as needing to be cleared (e.g. role/team on map_type change).
                    if field in _fields_to_null:
                        request_data[field] = None
                    continue
                request_data[field] = val

            # flatten_body: send the dict field value as the body directly (e.g. settings)
            if getattr(endpoint_op, "flatten_body", False) and len(request_data) == 1:
                request_data = next(iter(request_data.values()))

            if not request_data:
                logger.debug("Skipping %s - no data", op_name)
                continue

            path = endpoint_op.path
            if endpoint_op.path_params:
                for param in endpoint_op.path_params:
                    if param in results:
                        path = path.replace(f"{{{param}}}", str(results[param]))
                    elif param == "id" and "id" in api_data_dict:
                        path = path.replace(f"{{{param}}}", str(api_data_dict["id"]))

            url = self._build_url(path)

            logger.debug("Calling %s %s", endpoint_op.method, url)

            try:
                # Increment HTTP request counter (thread-safe)
                with self._lock:
                    self._http_request_count += 1

                response = self.session.request(endpoint_op.method, url, json=request_data, timeout=self.request_timeout, verify=self.verify_ssl)
                response.raise_for_status()

            except Exception as e:
                logger.error("API call failed: %s", e)
                if hasattr(e, "response") and e.response is not None:
                    logger.error("Response status: %s", e.response.status_code)
                    logger.error("Response body: %s", e.response.text)
                    # Include response body in message so callers (e.g. tests) can assert on
                    # validation errors.  Parse as JSON and use str() so the output uses
                    # Python's single-quote repr (e.g. {'triggers': ['Triggers must be a
                    # valid dict']}) rather than raw JSON double-quotes.  Tests written
                    # against the old AAPModule architecture relied on this format.
                    body_text = getattr(e.response, "text", "") or ""
                    if body_text:
                        import json as _json

                        try:
                            body_formatted = str(_json.loads(body_text))
                        except (_json.JSONDecodeError, ValueError):
                            body_formatted = body_text[:1000]
                        if body_formatted not in str(e):
                            raise ValueError(f"{e}\nResponse body: {body_formatted}") from e
                raise

            result_data = response.json() if response.content else {}
            results[op_name] = result_data

            if "id" in result_data and "id" not in results:
                results["id"] = result_data["id"]

        return results.get("create") or results.get("update") or results.get("main") or {}

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
            ready = [name for name, op in remaining.items() if op.depends_on is None or op.depends_on in sorted_ops]

            if not ready:
                raise ValueError(f"Circular dependency in operations: {list(remaining.keys())}")

            ready.sort(key=lambda name: remaining[name].order)
            sorted_ops.append(ready[0])
            remaining.pop(ready[0])

        return sorted_ops

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
            cache_key = f"org_name:{name}"
            if cache_key in self.cache:
                ids.append(self.cache[cache_key])
                continue

            url = self._build_url("organizations", query_params={"name": name})
            response = self.session.get(url, timeout=self.request_timeout, verify=self.verify_ssl)
            response.raise_for_status()
            results = response.json().get("results", [])

            if results:
                org_id = results[0]["id"]
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
            cache_key = f"org_id:{org_id}"
            if cache_key in self.cache:
                names.append(self.cache[cache_key])
                continue

            url = self._build_url(f"organizations/{org_id}/")
            response = self.session.get(url, timeout=self.request_timeout, verify=self.verify_ssl)
            response.raise_for_status()
            org = response.json()

            name = org["name"]
            self.cache[cache_key] = name
            self.cache[f"org_name:{name}"] = org_id
            names.append(name)

        return names

    # Aliases for consistency with transform mixins
    def lookup_organization_ids(self, names: list) -> list:
        """Alias for lookup_org_ids."""
        return self.lookup_org_ids(names)

    def lookup_organization_names(self, ids: list) -> list:
        """Alias for lookup_org_names."""
        return self.lookup_org_names(ids)

    def lookup_resource_id(self, endpoint: str, lookup_field: str, lookup_value: str) -> Optional[int]:
        """
        Resolve a resource name to ID by GET list with filter.
        Used by mixins to resolve FKs (e.g. service_cluster name -> id).
        """
        self.record_activity()
        if not lookup_value:
            return None
        if str(lookup_value).isdigit():
            return int(lookup_value)
        cache_key = f"{endpoint}:{lookup_field}:{lookup_value}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        url = self._build_url(endpoint, query_params={lookup_field: lookup_value})
        response = self.session.get(url, timeout=self.request_timeout, verify=self.verify_ssl)
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            raise ValueError("Resource '%s' with %s=%s not found" % (endpoint, lookup_field, lookup_value))
        rid = results[0].get("id")
        if rid is not None:
            self.cache[cache_key] = rid
        return rid

    def search_api(self, endpoint: str, query_params: Optional[Dict] = None, return_all: bool = False, max_objects: int = 1000) -> dict:
        """
        Perform a raw GET against any API endpoint and return the JSON response.

        This is the RPC entry-point used by the gateway_api lookup plugin so that
        all HTTP/SSL work stays in the manager subprocess (never in a forked Ansible
        worker process), avoiding the macOS + Python 3.12 fork-safety SIGABRT.

        Args:
            endpoint: API endpoint fragment, e.g. 'applications', 'users', 'settings/ui'
            query_params: Optional key/value filter parameters
            return_all: When True, follow 'next' pagination links and collect all results
            max_objects: Safety cap; raises ValueError when return_all would exceed this

        Returns:
            Raw API response dict.  List endpoints look like
            {'count': N, 'results': [...], 'next': ..., 'previous': ...}.
            Detail endpoints (settings/ui, etc.) are returned as-is.

        Raises:
            ValueError: When the HTTP request fails or max_objects is exceeded
        """
        self.record_activity()
        url = self._build_url(endpoint)
        response = self._make_request("get", url, operation="search_api", resource=endpoint, params=query_params or {})
        data = response.json()

        if return_all and "results" in data:
            total = data.get("count", len(data["results"]))
            if total > max_objects:
                raise ValueError("Endpoint '%s' returned %d objects which exceeds max_objects=%d" % (endpoint, total, max_objects))
            next_url = data.get("next")
            while next_url:
                next_resp = self._make_request("get", next_url, operation="search_api_paginate", resource=endpoint)
                next_data = next_resp.json()
                data["results"].extend(next_data.get("results", []))
                next_url = next_data.get("next")
            data["next"] = None

        return data

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

        try:
            if hasattr(self, "session") and self.session:
                self.session.close()
        except Exception as e:
            logger.warning("Error closing HTTP session: %s", e)

        try:
            self.cache.clear()
        except Exception as e:
            logger.warning("Error clearing cache: %s", e)

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
        PlatformManager.register("shutdown", callable=service.shutdown)
