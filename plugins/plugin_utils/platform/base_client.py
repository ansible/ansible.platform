"""Base API Client - Abstract interface for platform API communication.

This module defines the base interface that both standard and experimental
connection modes must implement. All shared functionality (version detection,
error handling, credential management, CRUD operations) is used by both modes.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

from ..platform.config import GatewayConfig
from ..platform.exceptions import APIError, ValidationError
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
            suffix = json.dumps(extra_query_params, sort_keys=True, separators=(",", ":"), default=str)
            key = f"{key}:{suffix}"
        return key

    def _invalidate_resource_lookup_cache(self, service: str, endpoint_path: str) -> None:
        """Invalidate cached names after a resource mutation."""
        cache = getattr(self, "cache", None)
        if cache is None:
            return

        path_parts = [part for part in endpoint_path.split("?")[0].strip("/").split("/") if part]
        if len(path_parts) < 4 or path_parts[0] != "api" or not path_parts[2].startswith("v"):
            return

        endpoint = path_parts[3]
        prefixes = (f"{service}:{endpoint}:", f"lookup:{service}:{endpoint}:")
        for key in tuple(cache):
            if key.startswith(prefixes):
                cache.pop(key, None)

        # Organization helpers use aliases in addition to normal lookup keys.
        if service == "gateway" and endpoint == "organizations":
            for key in tuple(cache):
                if key.startswith(("org_name:", "org_id:")):
                    cache.pop(key, None)

    def _normalize_resource_lookup(
        self,
        endpoint: str,
        lookup_field: str,
        lookup_value: str,
        service: str,
        extra_query_params: Optional[dict],
    ) -> tuple:
        """Normalize a lookup reference and its filters, including Controller named keys.

        Normalize only the simple Controller key form
        ``resource-name++organization``. Composite Controller keys remain
        unchanged for the list-query fallback; without caller filters,
        lookup_resource_id first tries the complete value against the detail
        endpoint.
        """
        filters = dict(extra_query_params or {})
        value = str(lookup_value)
        if lookup_field != "name" or "++" not in value:
            if service == "controller" and endpoint != "organizations":
                self._normalize_organization_filter(filters, service)
            return value, filters

        # Server-side detail lookup is the source of truth for named keys.
        if service != "controller":
            return value, filters

        # Controller has resource-specific named-key formats (for example,
        # hosts include inventory and organization). Only normalize the simple
        # one-separator form; caller filters may have skipped detail lookup.
        if value.count("++") != 1:
            self._normalize_organization_filter(filters, service)
            return value, filters

        resource_name, organization_name = self._parse_controller_named_key(value)

        # An empty organization component is the documented named URL form for
        # unscoped resources (``name++``). Its list query is just a name query.
        if organization_name is None:
            if not resource_name:
                raise ValueError("Invalid named key %r; a resource name is required" % value)
            return resource_name, filters
        if endpoint == "organizations":
            return value, filters

        self._normalize_organization_filter(filters, service)
        if not resource_name or not organization_name:
            raise ValueError("Invalid Controller named key %r; expected name++organization" % value)

        # Resolve scope IDs in the service whose foreign key consumes them.
        organization_id = self.lookup_resource_id(
            "organizations",
            "name",
            organization_name,
            service=service,
            require_unique=True,
            numeric_is_id=False,
        )
        if organization_id is None:
            raise ValueError("Organization %r from Controller named key %r was not found" % (organization_name, value))

        explicit_organization = filters.get("organization")
        if explicit_organization is not None:
            if self._normalize_composite_value(explicit_organization) != self._normalize_composite_value(organization_id):
                raise ValueError("Controller named key %r conflicts with organization scope %r" % (value, filters["organization"]))

        filters["organization"] = organization_id
        return resource_name, filters

    @staticmethod
    def _parse_controller_named_key(value: str) -> Tuple[str, Optional[str]]:
        """Split a Controller named key into its name and optional organization.

        The trailing ``++`` form represents a resource without organization
        scope, so its organization component is returned as ``None``. For
        scoped keys, everything after the first separator remains the scope.
        """
        resource_name, separator, organization_name = value.partition("++")
        if not separator:
            return value.strip(), None
        if value.endswith("++") and value.count("++") == 1:
            return resource_name.strip(), None
        return resource_name.strip(), organization_name.strip()

    def _normalize_organization_filter(self, filters: dict, service: str) -> None:
        """Replace an organization name or API object with an ID from its owning service."""
        organization = filters.get("organization")
        if organization is None:
            return
        organization_id = self._normalize_composite_value(organization)
        if organization_id is None:
            raise ValueError("Organization scope %r does not include an ID" % organization)
        if not str(organization_id).strip().isdigit():
            organization_id = self.lookup_resource_id("organizations", "name", str(organization_id), service=service, require_unique=True)
        if organization_id is None:
            raise ValueError("Organization %r was not found" % organization)
        filters["organization"] = int(organization_id)

    @staticmethod
    def _normalize_composite_value(value: Any) -> Any:
        """Normalize scalar or nested API foreign keys for scoped ID checks."""
        if isinstance(value, dict):
            value = value.get("id")
        try:
            return int(value)
        except (TypeError, ValueError):
            return value

    def _prepare_resource_lookup(self, service: str) -> None:
        """Allow clients to prepare transport headers before a batch lookup."""

    def lookup_resource_id(
        self,
        endpoint: str,
        lookup_field: str,
        lookup_value: str,
        service: str = "gateway",
        extra_query_params: dict = None,
        require_unique: bool = True,
        numeric_is_id: bool = True,
    ) -> Optional[int]:
        """Resolve an ID or uniquely matched resource name through the shared lookup path.

        Controller named keys are normalized to a resource name and organization
        filter before the request. The cache is used only for explicitly
        non-unique lookups: a cached ID cannot guarantee a later unique lookup
        still has exactly one match.
        """
        if not lookup_value:
            return None
        if numeric_is_id and str(lookup_value).isdigit():
            return int(lookup_value)

        # A detail lookup has no way to apply caller-supplied filters. The
        # composite Controller credential key is an exception when organization
        # is the sole filter: resolve the key directly, then verify its owner.
        named_key = str(lookup_value)
        filters = dict(extra_query_params or {})
        scoped_composite_credential = (
            service == "controller" and endpoint == "credentials" and lookup_field == "name" and named_key.count("++") > 1 and set(filters) == {"organization"}
        )
        if lookup_field == "name" and "++" in named_key and (not filters or scoped_composite_credential):
            if scoped_composite_credential:
                self._normalize_organization_filter(filters, service)
            service_version = self.get_api_version(service)
            self._prepare_resource_lookup(service)
            named_path = f"/api/{service}/v{service_version}/{endpoint.strip('/')}/{quote(named_key, safe='+')}/"
            try:
                named_result = self.search_api(named_path, service=service)
            except APIError as exc:
                if exc.status_code != 404:
                    raise
            else:
                named_resource_id = named_result.get("id")
                if named_resource_id is not None:
                    if scoped_composite_credential:
                        actual_organization = self._normalize_composite_value(named_result.get("organization"))
                        expected_organization = filters["organization"]
                        if actual_organization != expected_organization:
                            raise ValueError(
                                "Credential named key %r resolved to organization %r, not requested organization %r"
                                % (named_key, actual_organization, expected_organization)
                            )
                    return named_resource_id

        lookup_value, extra_query_params = self._normalize_resource_lookup(endpoint, lookup_field, lookup_value, service, extra_query_params)
        cache_key = self._resource_lookup_cache_key(service, endpoint, lookup_field, str(lookup_value), extra_query_params)
        if not require_unique and cache_key in self.cache:
            return self.cache[cache_key]

        service_version = self.get_api_version(service)
        self._prepare_resource_lookup(service)
        api_path = f"/api/{service}/v{service_version}/{endpoint.strip('/')}/"
        query = {lookup_field: lookup_value}
        if extra_query_params:
            query.update(extra_query_params)
        response_data = self.search_api(api_path, query_params=query, service=service)
        results = response_data.get("results", [])
        if not results:
            raise ValueError("Resource '%s' with %s=%s not found" % (endpoint, lookup_field, lookup_value))
        if require_unique and (len(results) > 1 or response_data.get("count", len(results)) > 1 or response_data.get("next")):
            raise ValueError("Resource '%s' with %s=%s matched multiple resources; provide additional filters" % (endpoint, lookup_field, lookup_value))

        resource_id = results[0].get("id")
        if resource_id is not None and not require_unique:
            self.cache[cache_key] = resource_id
        return resource_id

    def _lookup_resource_ids(
        self,
        endpoint: str,
        lookup_field: str,
        lookup_values: list,
        service: str = "gateway",
        extra_query_params: dict = None,
        numeric_is_id: bool = True,
        allow_missing: bool = False,
    ) -> dict:
        """Resolve several values with bounded ``__in`` queries where possible."""
        lookup_filters = dict(extra_query_params or {})
        if service == "controller" and endpoint != "organizations":
            self._normalize_organization_filter(lookup_filters, service)
        input_values = list(dict.fromkeys(str(value) for value in lookup_values if value or (isinstance(value, int) and not isinstance(value, bool))))
        resolved = {}

        def lookup_one(value):
            lookup_kwargs = {"service": service, "extra_query_params": lookup_filters}
            if not numeric_is_id:
                lookup_kwargs["numeric_is_id"] = False
            return self.lookup_resource_id(endpoint, lookup_field, value, **lookup_kwargs)

        named_values = [value for value in input_values if lookup_field == "name" and endpoint != "organizations" and "++" in value]
        for value in named_values:
            try:
                resolved[value] = self.lookup_resource_id(
                    endpoint,
                    lookup_field,
                    value,
                    service=service,
                    extra_query_params=lookup_filters,
                    require_unique=True,
                )
            except ValueError as exc:
                not_found_prefix = "Resource '%s' with %s=" % (endpoint, lookup_field)
                if allow_missing and str(exc).startswith(not_found_prefix) and str(exc).endswith(" not found"):
                    continue
                raise

        values = [value for value in input_values if (not numeric_is_id or not value.isdigit()) and value not in named_values]
        uncached = values

        if not uncached:
            return resolved
        if len(uncached) == 1 and not allow_missing:
            resolved[uncached[0]] = lookup_one(uncached[0])
            return resolved

        service_version = self.get_api_version(service)
        self._prepare_resource_lookup(service)
        api_path = f"/api/{service}/v{service_version}/{endpoint.strip('/')}/"

        def resolve_batch(batch_values):
            if not batch_values:
                return
            query = {f"{lookup_field}__in": ",".join(batch_values)}
            if lookup_filters:
                query.update(lookup_filters)
            data = self.search_api(
                api_path,
                query_params=query,
                return_all=True,
                max_objects=100000,
            )
            matches_by_value = {}
            for result in data.get("results", []):
                value = result.get(lookup_field)
                value = str(value) if value is not None else None
                if value in batch_values:
                    matches_by_value.setdefault(value, []).append(result)

            for value in batch_values:
                matches = matches_by_value.get(value, [])
                if not matches:
                    if allow_missing:
                        continue
                    raise ValidationError("Resource '%s' with %s=%s not found" % (endpoint, lookup_field, value))
                if len(matches) > 1:
                    raise ValidationError("Resource '%s' with %s=%s matched multiple resources; provide additional filters" % (endpoint, lookup_field, value))
                resolved[value] = matches[0].get("id")

        def resolve_exact(value):
            query = {lookup_field: value}
            if lookup_filters:
                query.update(lookup_filters)
            data = self.search_api(api_path, query_params=query, return_all=True, max_objects=100000)
            matches = [result for result in data.get("results", []) if str(result.get(lookup_field)) == value]
            if not matches:
                return
            if len(matches) > 1:
                raise ValidationError("Resource '%s' with %s=%s matched multiple resources; provide additional filters" % (endpoint, lookup_field, value))
            resolved[value] = matches[0].get("id")

        batch_values = []
        for value in uncached:
            if "," in value:
                resolve_batch(batch_values)
                batch_values = []
                if allow_missing:
                    resolve_exact(value)
                else:
                    resolved[value] = lookup_one(value)
                continue

            candidate = batch_values + [value]
            query = {f"{lookup_field}__in": ",".join(candidate)}
            if lookup_filters:
                query.update(lookup_filters)
            url_length = len(self._build_url(api_path, query).encode("utf-8"))
            if url_length <= self.MAX_BATCH_LOOKUP_URL_BYTES:
                batch_values = candidate
                continue

            resolve_batch(batch_values)
            batch_values = []
            single_query = {f"{lookup_field}__in": value}
            if lookup_filters:
                single_query.update(lookup_filters)
            single_url_length = len(self._build_url(api_path, single_query).encode("utf-8"))
            if single_url_length <= self.MAX_BATCH_LOOKUP_URL_BYTES:
                batch_values = [value]
            elif allow_missing:
                resolve_exact(value)
            else:
                resolved[value] = lookup_one(value)
        resolve_batch(batch_values)
        return resolved

    def lookup_resource_ids(
        self,
        endpoint: str,
        lookup_field: str,
        lookup_values: list,
        service: str = "gateway",
        extra_query_params: dict = None,
        numeric_is_id: bool = True,
        allow_missing: bool = False,
    ) -> dict:
        """Resolve multiple resource references through bounded list queries.

        Args:
            endpoint: API endpoint name.
            lookup_field: Field to match for each value.
            lookup_values: Values to resolve.
            service: API service owning the endpoint.
            extra_query_params: Additional filters that scope every lookup.
            numeric_is_id: Treat all-digit values as IDs and omit them from lookup.
            allow_missing: Return matches found without raising for missing values.

        Returns:
            A mapping from normalized lookup values to resource IDs.
        """
        return self._lookup_resource_ids(
            endpoint,
            lookup_field,
            lookup_values,
            service=service,
            extra_query_params=extra_query_params,
            numeric_is_id=numeric_is_id,
            allow_missing=allow_missing,
        )

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
                raise APIError(f"Malformed API response for {service}: expected JSON object, got {type(body).__name__}")
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
    def _post_json(self, url: str, payload: dict, operation: str = "http_request", resource: str = "unknown", retry: bool = True) -> dict:
        """POST JSON to a URL and return parsed JSON.

        Each client routes this through its own HTTP layer (_make_request).
        Set retry to False for operations that must not be repeated after an
        ambiguous transport failure.
        """
        pass

    @abstractmethod
    def search_api(
        self,
        endpoint: str,
        query_params: Optional[Dict] = None,
        return_all: bool = False,
        max_objects: int = 1000,
        service: str = "gateway",
    ) -> dict:
        """Fetch an API endpoint using the concrete client's transport."""
        pass

    def launch_resource(self, launch_url: str, payload: dict, service: str = "gateway", retry: bool = True) -> dict:
        """POST to a launch endpoint and return the created resource.

        Args:
            launch_url: API path to the launch endpoint.
            payload: Request body.
            service: API service name.
            retry: Whether the persistent client may retry transient failures.
                Disable this for non-idempotent actions where a lost response
                could make replaying the POST unsafe.
        """
        url = self._build_url(launch_url, service=service)
        return self._post_json(url, payload, operation="launch_resource", resource="launch", retry=retry)

    def can_cancel_resource(self, resource_id: int, cancel_endpoint_path: str, service: str = "controller") -> bool:
        """Return whether a resource's cancel endpoint currently permits cancellation."""
        endpoint = cancel_endpoint_path.strip("/")
        cancel_path = f"/{endpoint}/{resource_id}/cancel/"
        url = self._build_url(cancel_path, service=service)
        response = self._get_json(url, operation="can_cancel_resource", resource=endpoint)
        if not isinstance(response, dict) or not isinstance(response.get("can_cancel"), bool):
            raise ValueError("Cancel endpoint returned an unexpected response")
        return response["can_cancel"]

    def cancel_resource(
        self,
        resource_id: int,
        cancel_endpoint_path: str,
        fail_if_not_running: bool = False,
        timeout: float = 0,
        interval: float = 1.0,
        service: str = "controller",
        wait: bool = False,
    ) -> dict:
        """Cancel a resource through its ``cancel`` sub-endpoint.

        A 405 response means the resource is no longer cancelable. Treat that
        as a no-op unless the caller requested failure in that case. When
        wait=True, polls until the resource reaches a terminal state; a timeout
        of zero means wait indefinitely. When wait=False (default), returns
        immediately after a successful cancel POST.
        """
        if wait:
            if interval <= 0:
                raise ValueError("Polling interval must be positive, got %s" % interval)
            if timeout < 0:
                raise ValueError("Timeout must be 0 or greater")

        endpoint = cancel_endpoint_path.strip("/")
        cancel_path = f"/{endpoint}/{resource_id}/cancel/"
        url = self._build_url(cancel_path, service=service)

        try:
            self._post_json(url, {}, operation="cancel_resource", resource=endpoint, retry=False)
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code is None:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code != 405:
                raise
            if fail_if_not_running:
                raise ValueError("Resource is not running") from exc
            return {"changed": False, "id": resource_id, "status": "already finished"}

        if not wait:
            return {"changed": True, "id": resource_id, "status": "canceled"}

        completion = self.wait_for_completion(
            f"/{endpoint}/{resource_id}/",
            timeout=-1 if timeout == 0 else timeout,
            interval=interval,
            service=service,
        )
        return {"changed": True, "id": resource_id, "status": completion.get("status", "canceled")}

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
            raise ValidationError("Polling interval must be positive, got %s" % interval)

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

    def lookup_organization_ids(self, names: list, service: str = "gateway") -> list:
        """
        Lookup organization IDs from names (shared helper).

        Args:
            names: List of organization names

        Returns:
            List of organization IDs
        """
        return [self.lookup_resource_id("organizations", "name", name, service=service, require_unique=True) for name in names]

    def lookup_organization_names(self, ids: list, service: str = "gateway") -> list:
        """
        Lookup organization names from IDs (shared helper).

        Args:
            ids: List of organization IDs

        Returns:
            List of organization names
        """
        names = []
        for organization_id in ids:
            if not str(organization_id).strip().isdigit():
                raise ValueError("Organization ID %r must be numeric" % organization_id)
            cache_key = "org_name:%s:%s" % (service, organization_id)
            if cache_key in self.cache:
                names.append(self.cache[cache_key])
                continue

            version = self.get_api_version(service)
            path = "/api/%s/v%s/organizations/%s/" % (service, version, organization_id)
            organization = self.search_api(path, service=service)
            name = organization.get("name")
            if name is None:
                raise ValueError("Organization ID %s was not found in %s" % (organization_id, service))
            self.cache[cache_key] = name
            names.append(name)

        return names
