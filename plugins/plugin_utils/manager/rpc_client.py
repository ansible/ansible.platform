"""RPC Client for communicating with Platform Manager.

Provides the client-side interface for action plugins to communicate
with the persistent Platform Manager service.
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class ManagerRPCClient:
    """
    Client for communicating with Platform Manager.

    Handles connection to the manager service and provides a simple
    interface for action plugins to execute operations.

    Attributes:
        base_url: Platform base URL
        socket_path: Path to Unix socket
        authkey: Authentication key
        manager: Manager instance
        service_proxy: Proxy to PlatformService
    """

    def __init__(self, base_url: str, socket_path: str, authkey: bytes):
        """
        Initialize RPC client.

        Args:
            base_url: Platform base URL
            socket_path: Path to Unix socket
            authkey: Authentication key
        """
        self.base_url = base_url
        # CRITICAL: Ensure socket_path is always a plain str (Fedora/_AnsibleTaggedStr compatibility)
        # BaseManager.address must be a plain str type, not _AnsibleTaggedStr (str subclass) or Path object
        # On Fedora, BaseManager.address_type() is strict and rejects subclasses
        if socket_path is not None:
            # Force conversion to plain Python str using f-string (not a subclass)
            self.socket_path = f"{socket_path}"  # f-string forces plain str
            # Double-check: ensure it's actually a plain str, not a subclass
            if not isinstance(self.socket_path, str):
                self.socket_path = str(self.socket_path)
        else:
            self.socket_path = socket_path
        self.authkey = authkey

        # Import manager class
        from .platform_manager import PlatformManager

        # Register remote service
        PlatformManager.register("get_platform_service")

        # Connect to manager
        # CRITICAL: BaseManager.address must be a plain str type (not subclass)
        # Use f-string to ensure plain str type
        socket_path_str = f"{self.socket_path}" if self.socket_path is not None else self.socket_path
        # Double-check: ensure it's actually a plain str
        if socket_path_str is not None and not isinstance(socket_path_str, str):
            socket_path_str = str(socket_path_str)
        logger.debug("Connecting to manager at %s (type: %s, is plain str: %s)", socket_path_str, type(socket_path_str), isinstance(socket_path_str, str))
        self.manager = PlatformManager(address=socket_path_str, authkey=authkey)
        self.manager.connect()

        # Get service proxy
        self.service_proxy = self.manager.get_platform_service()
        logger.info("Connected to Platform Manager")

    def execute(self, operation: str, module_name: str, ansible_data: Any) -> Any:
        """
        Execute operation via manager.

        Args:
            operation: Operation type
            module_name: Module name
            ansible_data: Ansible dataclass instance

        Returns:
            Result dict (Ansible format) with timing information
        """
        from dataclasses import asdict, is_dataclass

        # Performance timing: RPC call start
        rpc_start = time.perf_counter()

        # Convert to dict for RPC
        if is_dataclass(ansible_data):
            data_dict = asdict(ansible_data)
        else:
            data_dict = ansible_data

        # Execute via proxy
        result_dict = self.service_proxy.execute(operation, module_name, data_dict)

        # Performance timing: RPC call end
        rpc_end = time.perf_counter()
        rpc_elapsed = rpc_end - rpc_start

        # Add timing info to result if it's a dict
        if isinstance(result_dict, dict):
            result_dict.setdefault("_timing", {})["rpc_time"] = rpc_elapsed
            result_dict["_timing"]["rpc_start"] = rpc_start
            result_dict["_timing"]["rpc_end"] = rpc_end

        return result_dict

    def lookup_resource_id(self, endpoint: str, lookup_field: str, lookup_value: str):
        """
        Resolve a resource name to its integer ID via the manager process.

        Delegates to PlatformService.lookup_resource_id() so the lookup uses
        the manager's active HTTP session (and benefits from its cache).

        Args:
            endpoint: API endpoint name (e.g. 'organizations', 'users')
            lookup_field: Field to filter by (e.g. 'name', 'username')
            lookup_value: Value to look up

        Returns:
            Integer resource ID

        Raises:
            ValueError: If the resource is not found
        """
        return self.service_proxy.lookup_resource_id(endpoint, lookup_field, lookup_value)

    def shutdown_manager(self) -> dict:
        """
        Request manager to shutdown gracefully.

        Returns:
            dict with shutdown status
        """
        try:
            if hasattr(self, "service_proxy") and self.service_proxy:
                result = self.service_proxy.shutdown()
                logger.debug("Manager shutdown response: %s", result)
                return result
        except Exception as e:
            logger.debug("Error calling shutdown on manager: %s", e)
            return {"status": "error", "error": str(e)}
        return {"status": "not_connected"}

    def close(self) -> None:
        """Close connection to manager."""
        if hasattr(self, "manager"):
            self.manager.shutdown()
            logger.debug("Disconnected from Platform Manager")
