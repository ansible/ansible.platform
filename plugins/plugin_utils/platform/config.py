"""Platform SDK - Gateway Configuration.

Generic configuration extraction for platform gateway connections.
This module is part of the platform SDK and is not Ansible-specific.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

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
    connection_mode: str = "standard"  # "standard" or "experimental"
    idle_timeout: float = 3600.0

    def __post_init__(self):
        """Normalize URL after initialization."""
        original_url = self.base_url
        self.base_url = self._normalize_url(self.base_url)
        if original_url != self.base_url:
            logger.debug(
                "Normalized gateway URL: %s -> %s",
                original_url,
                self.base_url,
            )
        logger.info(
            "GatewayConfig initialized: base_url=%s, verify_ssl=%s, timeout=%s, idle_timeout=%s",
            self.base_url,
            self.verify_ssl,
            self.request_timeout,
            self.idle_timeout,
        )

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

        if not url.startswith(("https://", "http://")):
            return f"https://{url}"

        return url


def extract_gateway_config(
    task_args: Optional[Dict[str, Any]] = None,
    host_vars: Optional[Dict[str, Any]] = None,
    required: bool = True,
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

    logger.debug(
        "Extracting gateway config from task_args (keys: %s) and host_vars (keys: %s)",
        list(task_args.keys()),
        list(host_vars.keys()),
    )

    # Get gateway URL from task args first, then host_vars
    gateway_url = task_args.get("gateway_url") or task_args.get("gateway_hostname") or host_vars.get("gateway_url") or host_vars.get("gateway_hostname")
    logger.debug("Gateway URL extracted: %s", gateway_url)

    # Get auth parameters from task args first, then host_vars
    gateway_username = task_args.get("gateway_username") or host_vars.get("gateway_username") or host_vars.get("aap_username")
    gateway_password = task_args.get("gateway_password") or host_vars.get("gateway_password") or host_vars.get("aap_password")
    gateway_token_raw = (
        task_args.get("gateway_token")
        or host_vars.get("gateway_token")
        or
        # Only fall back to the aap_token ansible_fact when no username/password
        # credentials are available.  The token module stores a read-scoped token
        # in aap_token after creation; picking it up here would cause all
        # subsequent tasks in the same play to authenticate as that limited token
        # instead of the admin user, leading to 403 errors.
        (host_vars.get("aap_token") if not gateway_username and not gateway_password else None)
    )
    # The token module sets aap_token as a dict ({"token": "...", "id": ...}).
    # Extract the actual token string if we got a dict.
    if isinstance(gateway_token_raw, dict):
        gateway_token = gateway_token_raw.get("token")
    else:
        gateway_token = gateway_token_raw
    gateway_validate_certs = task_args.get("gateway_validate_certs") if "gateway_validate_certs" in task_args else host_vars.get("gateway_validate_certs", True)
    gateway_request_timeout = task_args.get("gateway_request_timeout") or host_vars.get("gateway_request_timeout") or 10.0
    # How long (seconds) the persistent manager process may sit idle — i.e. receive
    # no RPC or API traffic — before it shuts itself down and removes its socket.
    # This prevents orphaned manager processes from accumulating across playbook runs.
    # Default: 3600 s (1 hour).  Set to 0 to disable idle-based shutdown entirely.
    # Accepted variable names (task arg takes priority over host var):
    #   gateway_idle_timeout  /  ansible_platform_manager_idle_timeout
    gateway_idle_timeout = (
        task_args.get("gateway_idle_timeout") or host_vars.get("gateway_idle_timeout") or host_vars.get("ansible_platform_manager_idle_timeout")
    )
    # Connection mode: "standard" (default) or "experimental" (persistent manager)
    connection_mode = task_args.get("platform_connection_mode") or host_vars.get("platform_connection_mode") or "standard"

    if required and not gateway_url:
        logger.error("Gateway URL is required but not found in task_args or host_vars")
        raise ValueError("gateway_url or gateway_hostname must be provided as task parameter or defined in inventory")

    # Log auth method being used (without exposing secrets)
    if gateway_token:
        auth_method = "token"
    elif gateway_username:
        auth_method = "username/password"
    else:
        auth_method = "none"
    logger.info(
        "Gateway config extracted: url=%s, auth_method=%s, verify_ssl=%s, timeout=%s",
        gateway_url,
        auth_method,
        gateway_validate_certs,
        gateway_request_timeout,
    )

    config = GatewayConfig(
        base_url=gateway_url or "",
        username=gateway_username,
        password=gateway_password,
        oauth_token=gateway_token,
        verify_ssl=gateway_validate_certs,
        request_timeout=gateway_request_timeout,
        connection_mode=connection_mode,
        idle_timeout=(float(gateway_idle_timeout) if gateway_idle_timeout is not None else 3600.0),
    )

    logger.debug("GatewayConfig created successfully")
    return config
