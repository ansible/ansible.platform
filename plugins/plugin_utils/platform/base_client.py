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
from ..platform.registry import APIVersionRegistry

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
        self.request_timeout = config.request_timeout

        # Shared: Version detection infrastructure
        self.registry = APIVersionRegistry()
        self.loader = DynamicClassLoader(self.registry)

        # Shared: API version (detected during initialization)
        self.api_version: Optional[str] = None

        # Shared: Cache for lookups (org names ↔ IDs, etc.)
        self.cache: Dict[str, Any] = {}

        logger.info("BaseAPIClient initialized: base_url=%s, mode=%s", self.base_url, config.connection_mode)

    @abstractmethod
    def _detect_api_version(self) -> str:
        """
        Detect API version from platform.

        This is implemented differently by each mode:
        - Standard mode: Direct HTTP request to /ping endpoint
        - Experimental mode: Same, but cached in persistent process

        Returns:
            API version string (e.g., '1', '2')
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
