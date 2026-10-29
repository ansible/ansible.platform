"""Base API Client - Abstract interface for platform API communication.

This module defines the base interface that both standard and experimental
connection modes must implement. All shared functionality (version detection,
error handling, credential management, CRUD operations) is used by both modes.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..platform.config import GatewayConfig
from ..platform.loader import DynamicClassLoader
from ..platform.registry import DEFAULT_SERVICE, APIVersionRegistry

logger = logging.getLogger(__name__)

DEFAULT_WAIT_TIMEOUT = 3600.0
DEFAULT_WAIT_INTERVAL = 10.0
TERMINAL_STATUSES = frozenset({"successful", "failed", "error", "canceled"})


class BaseAPIClient(ABC):
    """
    Abstract base class for platform API clients.

    Both standard mode (DirectHTTPClient) and optional persistent mode (PlatformService)
    inherit from this class and share the same interface and shared layers.

    Shared layers used by both:
    - Version detection (APIVersionRegistry, DynamicClassLoader)
    - Error taxonomy (exceptions.py, retry.py)
    - Credential management (credential_manager.py)
    - CRUD operations (transform mixins, endpoint operations)
    - Optimizations (caching, lookup helpers)
    """

    # Keep batched GET URLs below common reverse-proxy request-line limits.
    MAX_BATCH_LOOKUP_URL_BYTES = 6000

    def __init__(self, config: GatewayConfig):
        """
        Initialize base API client.

        Args:
            config: Gateway configuration
        """
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.verify_ssl = config.verify_ssl
        self.ca_bundle = config.ca_bundle
        self.request_timeout = config.request_timeout

        # Shared: Version detection infrastructure
        self.registry = APIVersionRegistry()
        self.loader = DynamicClassLoader(self.registry)

        # Shared: Per-service API versions (detected lazily)
        self.api_versions: Dict[str, str] = {}

        # Shared: Cache for lookups (org names ↔ IDs, etc.)
        self.cache: Dict[str, Any] = {}

        logger.info("BaseAPIClient initialized: base_url=%s, mode=%s", self.base_url, config.connection_mode)

    @property
    def api_version(self) -> Optional[str]:
        """Gateway API version (backward-compatible accessor)."""
        return self.api_versions.get(DEFAULT_SERVICE)

    @api_version.setter
    def api_version(self, value: Optional[str]) -> None:
        if value is not None:
            self.api_versions[DEFAULT_SERVICE] = value
        else:
            self.api_versions.pop(DEFAULT_SERVICE, None)

    def get_api_version(self, service: str) -> str:
        """Get detected API version for a service, detecting lazily if needed.

        On transient failure the fallback is returned but NOT cached, so the
        next call will retry detection instead of permanently using a guess.
        """
        if service not in self.api_versions:
            try:
                detected = self._detect_service_version(service)
                self.api_versions[service] = detected
            except Exception:
                fallback = self.registry.get_latest_version(service) or "1"
                logger.warning("Version detection failed for %s, defaulting to v%s", service, fallback)
                return fallback
        return self.api_versions[service]

    @property
    def requests_verify(self):
        """TLS verify parameter for HTTP clients (bool or CA bundle path)."""
        config = getattr(self, "config", None)
        if config is not None:
            return config.requests_verify
        if not getattr(self, "verify_ssl", True):
            return False
        ca_bundle = getattr(self, "ca_bundle", None)
        if ca_bundle:
            return ca_bundle
        return True

    def _resource_lookup_cache_key(self, service: str, endpoint: str, lookup_field: str, lookup_value: str, extra_query_params: dict = None) -> str:
        """Build the cache key used by resource-name lookups."""
        key = f"{service}:{endpoint}:{lookup_field}:{lookup_value}"
        if extra_query_params:
            suffix = "&".join(f"{k}={v}" for k, v in sorted(extra_query_params.items()))
            key = f"{key}:{suffix}"
        return key

    def _prepare_resource_lookup(self, service: str) -> None:
        """Allow clients to prepare transport headers before a batch lookup."""

    def _lookup_resource_ids(
        self,
        endpoint: str,
        lookup_field: str,
        lookup_values: list,
        service: str = "gateway",
        extra_query_params: dict = None,
    ) -> dict:
        """Resolve several names with bounded ``__in`` queries where possible."""
        values = list(dict.fromkeys(str(value) for value in lookup_values if value and not str(value).isdigit()))
        cache_keys = {value: self._resource_lookup_cache_key(service, endpoint, lookup_field, value, extra_query_params) for value in values}
        resolved = {value: self.cache[key] for value, key in cache_keys.items() if key in self.cache}
        uncached = [value for value in values if value not in resolved]

        if not uncached:
            return resolved
        if len(uncached) == 1:
            resolved[uncached[0]] = self.lookup_resource_id(endpoint, lookup_field, uncached[0], service=service, extra_query_params=extra_query_params)
            return resolved

        service_version = self.get_api_version(service)
        self._prepare_resource_lookup(service)
        api_path = f"/api/{service}/v{service_version}/{endpoint.strip('/')}/"

        def resolve_batch(batch_values):
            if not batch_values:
                return
            query = {f"{lookup_field}__in": ",".join(batch_values)}
            if extra_query_params:
                query.update(extra_query_params)
            data = self.search_api(
                api_path,
                query_params=query,
                return_all=True,
                max_objects=100000,
            )
            for result in data.get("results", []):
                value = result.get(lookup_field)
                value = str(value) if value is not None else None
                if value in batch_values and value not in resolved:
                    resolved[value] = result.get("id")
                    if resolved[value] is not None:
                        self.cache[cache_keys[value]] = resolved[value]

            for value in batch_values:
                if value not in resolved:
                    raise ValueError("Resource '%s' with %s=%s not found" % (endpoint, lookup_field, value))

        batch_values = []
        for value in uncached:
            if "," in value:
                resolve_batch(batch_values)
                batch_values = []
                resolved[value] = self.lookup_resource_id(endpoint, lookup_field, value, service=service, extra_query_params=extra_query_params)
                continue

            candidate = batch_values + [value]
            query = {f"{lookup_field}__in": ",".join(candidate)}
            url_length = len(self._build_url(api_path, query).encode("utf-8"))
            if url_length <= self.MAX_BATCH_LOOKUP_URL_BYTES:
                batch_values = candidate
                continue

            resolve_batch(batch_values)
            batch_values = []
            single_url_length = len(self._build_url(api_path, {f"{lookup_field}__in": value}).encode("utf-8"))
            if single_url_length <= self.MAX_BATCH_LOOKUP_URL_BYTES:
                batch_values = [value]
            else:
                resolved[value] = self.lookup_resource_id(endpoint, lookup_field, value, service=service, extra_query_params=extra_query_params)
        resolve_batch(batch_values)
        return resolved

    def _ansible_tls_kwargs(self, verify=None):
        """Map TLS verify setting to Ansible Request validate_certs/ca_path kwargs."""
        if verify is None:
            verify = self.requests_verify
        if isinstance(verify, str):
            return {"validate_certs": True, "ca_path": verify}
        return {"validate_certs": bool(verify), "ca_path": None}

    @abstractmethod
    def _detect_api_version(self) -> str:
        """
        Detect Gateway API version from platform.

        Returns:
            API version string (e.g., '1', '2')
        """
        pass

    def _detect_service_version(self, service: str) -> str:
        """
        Detect API version for a specific service by probing its API root.

        For gateway, delegates to _detect_api_version(). For other services,
        probes /api/{service}/ via _probe_service_root() and parses the
        X-API-Version header or current_version body field. Raises on any
        failure so get_api_version() can return an uncached fallback.
        """
        if service == DEFAULT_SERVICE:
            return self._detect_api_version()

        import re

        supported = self.registry.get_supported_versions(service)
        if not supported:
            raise RuntimeError(f"No API versions discovered for service '{service}'")

        headers, body = self._probe_service_root(service)

        raw = (headers.get("X-API-Version", "") or "").lstrip("v")
        if raw and raw in supported:
            logger.info("%s API version detected (header): v%s", service, raw)
            return raw
        if raw:
            major = raw.split(".")[0]
            if major in supported:
                logger.info("%s API version detected (header major): v%s", service, major)
                return major

        if body is not None:
            if not isinstance(body, dict):
                raise ValueError(f"Malformed API response for {service}: expected JSON object, got {type(body).__name__}")
            if "current_version" in body:
                cv = re.search(r"/v(\d+(?:\.\d+)?)/?$", str(body["current_version"]))
                cv_raw = cv.group(1) if cv else str(body["current_version"]).lstrip("v")
                if cv_raw in supported:
                    logger.info("%s API version detected (body): v%s", service, cv_raw)
                    return cv_raw
                cv_major = cv_raw.split(".")[0]
                if cv_major in supported:
                    logger.info("%s API version detected (body major): v%s", service, cv_major)
                    return cv_major

        raise RuntimeError(f"Could not detect API version for service '{service}' from probe response")

    @abstractmethod
    def _probe_service_root(self, service: str):
        """
        Probe /api/{service}/ and return the parsed response.

        Returns:
            Tuple of (headers_dict, body_dict_or_None). body is None when
            the response is not JSON.

        Raises:
            On transport or HTTP errors — these must propagate so that
            get_api_version() does not permanently cache a fallback.
        """
        pass

    @abstractmethod
    def _authenticate(self) -> None:
        """
        Authenticate with the platform.

        This is implemented differently by each mode:
        - Standard mode: Create new session, authenticate
        - Experimental mode: Reuse persistent session

        Raises:
            AuthenticationError: If authentication fails
        """
        pass

    @abstractmethod
    def execute(self, operation: str, module_name: str, ansible_data_dict: dict) -> dict:
        """
        Execute a generic operation on any resource.

        This is the main entry point called by action plugins.
        Both modes implement this using shared layers.

        Args:
            operation: Operation type ('create', 'update', 'delete', 'find')
            module_name: Module name (e.g., 'user', 'organization')
            ansible_data_dict: Ansible dataclass as dict

        Returns:
            Result as dict (Ansible format) with timing information

        Raises:
            ValueError: If operation is unknown or execution fails
        """
        pass

    @abstractmethod
    def _get_json(self, url: str, operation: str = "http_request", resource: str = "unknown") -> dict:
        """GET a URL and return parsed JSON.

        Each client routes this through its own HTTP layer (_make_request),
        gaining retry, 401 re-auth, and PlatformError classification.
        """
        pass

    @abstractmethod
    def _post_json(self, url: str, payload: dict, operation: str = "http_request", resource: str = "unknown") -> dict:
        """POST JSON to a URL and return parsed JSON.

        Each client routes this through its own HTTP layer (_make_request).
        """
        pass

    def launch_resource(self, launch_url: str, payload: dict, service: str = "gateway") -> dict:
        """POST to a launch endpoint and return the created resource."""
        url = self._build_url(launch_url, service=service)
        return self._post_json(url, payload, operation="launch_resource", resource="launch")

    def wait_for_completion(
        self,
        resource_url: str,
        timeout: Optional[float] = None,
        interval: Optional[float] = None,
        service: str = "gateway",
    ) -> dict:
        """Poll a resource URL until it reaches a terminal status.

        Args:
            resource_url: API path to the resource (e.g. /api/controller/v2/jobs/99/).
            timeout: Maximum seconds to wait. None means DEFAULT_WAIT_TIMEOUT.
                Negative values are treated as "no timeout" (wait indefinitely).
            interval: Seconds between polls. None means DEFAULT_WAIT_INTERVAL.
            service: API service name for URL construction.

        Raises:
            WaitTimeoutError: If timeout is exceeded. The exception carries
                ``last_result`` so callers can still report the job's id/status.
                The remote job keeps running; only the client stopped watching.
            ValueError: If interval is not positive.
        """
        from .exceptions import WaitTimeoutError

        if timeout is None:
            timeout = DEFAULT_WAIT_TIMEOUT
        if interval is None:
            interval = DEFAULT_WAIT_INTERVAL
        if interval <= 0:
            raise ValueError("Polling interval must be positive, got %s" % interval)

        url = self._build_url(resource_url, service=service)
        start = time.monotonic()
        last_result: dict = {}
        polled = False
        prev_status = ""

        while True:
            if polled and timeout >= 0:
                elapsed = time.monotonic() - start
                if elapsed >= timeout:
                    raise WaitTimeoutError(
                        "Timed out waiting after %ss" % timeout,
                        operation="wait_for_completion",
                        resource=resource_url,
                        timeout_seconds=timeout,
                        last_result=last_result,
                    )

            last_result = self._get_json(url, operation="wait_poll", resource="launch")
            polled = True

            status = last_result.get("status", "")
            if not status:
                logger.warning("wait_for_completion: response has no 'status' field, url=%s", url)

            if status != prev_status:
                logger.debug("wait_for_completion: %s -> %s (url=%s)", prev_status or "(initial)", status, url)
                prev_status = status

            if status in TERMINAL_STATUSES:
                return last_result

            if timeout >= 0:
                elapsed = time.monotonic() - start
                if elapsed >= timeout:
                    raise WaitTimeoutError(
                        "Timed out waiting after %ss" % timeout,
                        operation="wait_for_completion",
                        resource=resource_url,
                        timeout_seconds=timeout,
                        last_result=last_result,
                    )
                sleep_time = min(interval, max(0, timeout - elapsed))
            else:
                sleep_time = interval

            time.sleep(sleep_time)

    def lookup_organization_ids(self, names: list) -> list:
        """
        Lookup organization IDs from names (shared helper).

        Args:
            names: List of organization names

        Returns:
            List of organization IDs
        """
        # This is a shared helper that both modes can use
        # Implementation will be in the shared CRUD layer
        pass

    def bulk_host_create(self, inventory_id: int, hosts: list, service: str = "controller") -> dict:
        """
        Create hosts in bulk via the Controller bulk/host_create endpoint.

        Args:
            inventory_id: Numeric ID of the target inventory
            hosts: List of host dicts (name, description, enabled, variables, instance_id)
            service: Service name (default: controller)

        Returns:
            API response dict

        Raises:
            ValueError: If the API returns a non-201 status
        """
        raise NotImplementedError

    def lookup_organization_names(self, ids: list) -> list:
        """
        Lookup organization names from IDs (shared helper).

        Args:
            ids: List of organization IDs

        Returns:
            List of organization names
        """
        # This is a shared helper that both modes can use
        # Implementation will be in the shared CRUD layer
        pass
