"""Base API Client - Abstract interface for platform API communication.

This module defines the base interface that both standard and experimental
connection modes must implement. All shared functionality (version detection,
error handling, credential management, CRUD operations) is used by both modes.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..platform.config import GatewayConfig
from ..platform.loader import DynamicClassLoader
from ..platform.registry import DEFAULT_SERVICE, APIVersionRegistry

logger = logging.getLogger(__name__)


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

    def manage_associations(
        self,
        base_path: str,
        resource_id: int,
        association_field: str,
        desired_items: list,
        lookup_endpoint: str,
        lookup_field: str,
    ) -> bool:
        """
        Sync an association sub-endpoint for a resource.

        Compares the desired list of associated items against the current
        associations and performs associate/disassociate operations as needed.

        Args:
            base_path: API base path for the resource (e.g. '/api/controller/v2/job_templates')
            resource_id: ID of the parent resource
            association_field: Sub-endpoint name (e.g. 'credentials', 'labels')
            desired_items: List of names or IDs to associate
            lookup_endpoint: API endpoint for resolving names (e.g. 'credentials')
            lookup_field: Field to filter by when resolving (e.g. 'name')

        Returns:
            True if any associations were changed, False otherwise
        """
        raise NotImplementedError("%s must implement manage_associations()" % type(self).__name__)

    def manage_sub_resource(
        self,
        base_path: str,
        resource_id: int,
        sub_path: str,
        data: Optional[dict] = None,
    ) -> bool:
        """
        Manage a secondary sub-endpoint resource (e.g. survey_spec).

        Compares the desired data against the current state and updates if
        different.  An empty dict signals deletion of the sub-resource.

        Args:
            base_path: API base path for the parent resource
            resource_id: ID of the parent resource
            sub_path: Sub-endpoint path (e.g. 'survey_spec')
            data: Desired state.  Empty dict {} means delete.

        Returns:
            True if the sub-resource was changed, False otherwise
        """
        raise NotImplementedError("%s must implement manage_sub_resource()" % type(self).__name__)

    def copy_resource(
        self,
        module_name: str,
        source_name_or_id: str,
        new_name: str,
        copy_endpoint_path: str,
    ) -> dict:
        """
        Copy a resource via its /copy/ sub-endpoint.

        Args:
            module_name: Module name for find lookup (e.g. 'job_template')
            source_name_or_id: Name or ID of the source resource to copy
            new_name: Name for the new (copied) resource
            copy_endpoint_path: API base path (e.g. '/api/controller/v2/job_templates')

        Returns:
            dict: The copied resource data from the API response
        """
        raise NotImplementedError("%s must implement copy_resource()" % type(self).__name__)

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
