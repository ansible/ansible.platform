"""RPC Client for communicating with Platform Manager.

Provides the client-side interface for action plugins to communicate
with the persistent Platform Manager service.
"""

from multiprocessing.managers import BaseManager
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import base64
import time
import socket

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

    def __init__(
        self,
        base_url: str,
        socket_path: str,
        authkey: bytes
    ):
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
            if type(self.socket_path) is not str:
                self.socket_path = str(self.socket_path)
        else:
            self.socket_path = socket_path
        self.authkey = authkey
        self.manager = None
        self.service_proxy = None
        self._connected = False
        
        # Import manager class
        from .platform_manager import PlatformManager

        # Register remote service
        PlatformManager.register('get_platform_service')

        # Connect to manager
        # CRITICAL: BaseManager.address must be a plain str type (not subclass)
        # Use f-string to ensure plain str type
        socket_path_str = f"{self.socket_path}" if self.socket_path is not None else self.socket_path
        # Double-check: ensure it's actually a plain str
        if socket_path_str is not None and type(socket_path_str) is not str:
            socket_path_str = str(socket_path_str)
        logger.debug(f"Connecting to manager at {socket_path_str} (type: {type(socket_path_str)}, is plain str: {type(socket_path_str) is str})")
        self.manager = PlatformManager(
            address=socket_path_str,
            authkey=authkey
        )
        self.manager.connect()

        # Get service proxy
        self.service_proxy = self.manager.get_platform_service()
        logger.info("Connected to Platform Manager")

    def execute(
        self,
        operation: str,
        module_name: str,
        ansible_data: Any
    ) -> Any:
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
        logger.debug(f"⏱️  TIMING START: RPC call to manager (operation={operation}, module={module_name}, timestamp={rpc_start:.6f})")
        
        # Convert to dict for RPC
        if is_dataclass(ansible_data):
            data_dict = asdict(ansible_data)
        else:
            data_dict = ansible_data
        
        try:
            if not self._connected:
                self.connect()
            # Execute via proxy
            result_dict = self.service_proxy.execute(
                operation,
                module_name,
                data_dict
            )
            
            # Performance timing: RPC call end
            rpc_end = time.perf_counter()
            rpc_elapsed = rpc_end - rpc_start
            
            # Add timing info to result if it's a dict
            if isinstance(result_dict, dict):
                result_dict.setdefault('_timing', {})['rpc_time'] = rpc_elapsed
                result_dict['_timing']['rpc_start'] = rpc_start
                result_dict['_timing']['rpc_end'] = rpc_end
            
            return result_dict
        except (EOFError, BrokenPipeError, ConnectionRefusedError) as e:
            logger.error(f"RPC connection error during execute: {e}")
            self._cleanup_on_failure()
            raise ConnectionError(f"Manager connection lost: {e}") from e
    
    def connect(self) -> None:
        """Establish connection to the manager."""
        try:
            from .platform_manager import PlatformManager
            if not hasattr(PlatformManager, 'get_platform_service'):
                PlatformManager.register('get_platform_service')
            self.manager = PlatformManager(
                address=self.socket_path, 
                authkey=self.authkey
            )
            logger.debug(f"Connecting to manager at {self.socket_path}...")
            self.manager.connect()
            self.service_proxy = self.manager.get_platform_service()
            self._connected = True
            logger.debug("RPC Connection established")
        except Exception as e:
            logger.error(f"Failed to connect to manager: {e}")
            self._cleanup_on_failure()
            raise

    def check_health(self) -> bool:
        """
        Check if the manager is responsive using an explicit Ping.
        """
        try:
            if not self._connected:
                self.connect()
            if self.service_proxy.ping():
                return True
            return False
        except (EOFError, BrokenPipeError, ConnectionRefusedError, socket.error, AttributeError):
            self._cleanup_on_failure()
            return False
        except Exception as e:
            logger.warning(f"Health check failed unexpectedly: {e}")
            self._cleanup_on_failure()
            return False
    
    def shutdown_manager(self) -> dict:
        """
        Request manager to shutdown gracefully.

        Returns:
            dict with shutdown status
        """
        try:
            if hasattr(self, 'service_proxy') and self.service_proxy:
                result = self.service_proxy.shutdown()
                logger.debug(f"Manager shutdown response: {result}")
                return result
        except Exception as e:
            logger.debug(f"Error calling shutdown on manager: {e}")
            return {"status": "error", "error": str(e)}
        return {"status": "not_connected"}

    def close(self) -> None:
        """Close connection to manager."""
        if hasattr(self, 'manager'):
            self.manager.shutdown()
            logger.debug("Disconnected from Platform Manager")

    def _cleanup_on_failure(self):
        """Reset internal state on connection failure."""
        self._connected = False
        self.manager = None
        self.service_proxy = None
