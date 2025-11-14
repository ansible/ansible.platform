"""RPC Client for communicating with Platform Manager.

Provides the client-side interface for action plugins to communicate
with the persistent Platform Manager service.
"""

from multiprocessing.managers import BaseManager
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import base64

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
        self.socket_path = socket_path
        self.authkey = authkey
        
        # Import manager class
        from .platform_manager import PlatformManager
        
        # Register remote service
        PlatformManager.register('get_platform_service')
        
        # Connect to manager
        logger.debug(f"Connecting to manager at {socket_path}")
        self.manager = PlatformManager(
            address=socket_path,
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
            Result dict (Ansible format)
        """
        from dataclasses import asdict, is_dataclass
        
        # Convert to dict for RPC
        if is_dataclass(ansible_data):
            data_dict = asdict(ansible_data)
        else:
            data_dict = ansible_data
        
        # Execute via proxy
        result_dict = self.service_proxy.execute(
            operation,
            module_name,
            data_dict
        )
        
        return result_dict
    
    def close(self) -> None:
        """Close connection to manager."""
        if hasattr(self, 'manager'):
            self.manager.shutdown()
            logger.debug("Disconnected from Platform Manager")


