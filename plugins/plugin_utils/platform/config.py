"""Platform SDK - Gateway Configuration.

Generic configuration extraction for platform gateway connections.
This module is part of the platform SDK and is not Ansible-specific.
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GatewayConfig:
    """Gateway connection configuration.
    
    This is a generic configuration object that can be used by any
    entry point (Ansible, CLI, MCP, etc.).
    """
    base_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    oauth_token: Optional[str] = None
    verify_ssl: bool = True
    request_timeout: float = 10.0
    
    def __post_init__(self):
        """Normalize URL after initialization."""
        original_url = self.base_url
        self.base_url = self._normalize_url(self.base_url)
        if original_url != self.base_url:
            logger.debug(f"Normalized gateway URL: {original_url} -> {self.base_url}")
        logger.info(f"GatewayConfig initialized: base_url={self.base_url}, verify_ssl={self.verify_ssl}, timeout={self.request_timeout}")
    
    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normalize gateway URL.
        
        Args:
            url: Gateway URL (may or may not have protocol)
            
        Returns:
            Normalized URL with protocol
        """
        if not url:
            return url
        
        if not url.startswith(('https://', 'http://')):
            return f"https://{url}"
        
        return url


def extract_gateway_config(
    task_args: Optional[Dict[str, Any]] = None,
    host_vars: Optional[Dict[str, Any]] = None,
    required: bool = True
) -> GatewayConfig:
    """
    Extract gateway configuration from task arguments and host variables.
    
    This is a generic function that extracts gateway configuration from
    any dict-like structure. It's not Ansible-specific and can be used
    by CLI tools, MCP tools, or other entry points.
    
    Args:
        task_args: Task/command arguments (higher priority)
        host_vars: Host/inventory variables (lower priority)
        required: Whether gateway_url is required (default: True)
        
    Returns:
        GatewayConfig object with normalized values
        
    Raises:
        ValueError: If required gateway_url is missing
    """
    task_args = task_args or {}
    host_vars = host_vars or {}
    
    logger.debug(f"Extracting gateway config from task_args (keys: {list(task_args.keys())}) and host_vars (keys: {list(host_vars.keys())})")
    
    # Get gateway URL from task args first, then host_vars
    gateway_url = (
        task_args.get('gateway_url') or 
        task_args.get('gateway_hostname') or
        host_vars.get('gateway_url') or 
        host_vars.get('gateway_hostname')
    )
    logger.debug(f"Gateway URL extracted: {gateway_url}")
    
    # Get auth parameters from task args first, then host_vars
    gateway_username = (
        task_args.get('gateway_username') or 
        host_vars.get('gateway_username') or 
        host_vars.get('aap_username')
    )
    gateway_password = (
        task_args.get('gateway_password') or 
        host_vars.get('gateway_password') or 
        host_vars.get('aap_password')
    )
    gateway_token = (
        task_args.get('gateway_token') or 
        host_vars.get('gateway_token') or 
        host_vars.get('aap_token')
    )
    gateway_validate_certs = (
        task_args.get('gateway_validate_certs') 
        if 'gateway_validate_certs' in task_args 
        else host_vars.get('gateway_validate_certs', True)
    )
    gateway_request_timeout = (
        task_args.get('gateway_request_timeout') or 
        host_vars.get('gateway_request_timeout') or 
        10.0
    )
    
    if required and not gateway_url:
        logger.error("Gateway URL is required but not found in task_args or host_vars")
        raise ValueError(
            "gateway_url or gateway_hostname must be provided as task parameter or defined in inventory"
        )
    
    # Log auth method being used (without exposing secrets)
    auth_method = "token" if gateway_token else ("username/password" if gateway_username else "none")
    logger.info(f"Gateway config extracted: url={gateway_url}, auth_method={auth_method}, verify_ssl={gateway_validate_certs}, timeout={gateway_request_timeout}")
    
    config = GatewayConfig(
        base_url=gateway_url or '',
        username=gateway_username,
        password=gateway_password,
        oauth_token=gateway_token,
        verify_ssl=gateway_validate_certs,
        request_timeout=gateway_request_timeout
    )
    
    logger.debug(f"GatewayConfig created successfully")
    return config

