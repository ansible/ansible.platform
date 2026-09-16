"""MCP server configuration from environment variables.

Maps environment variables to GatewayConfig for the ansible.platform SDK.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig


@dataclass(frozen=True)
class ServerConfig:
    """MCP server configuration resolved from environment variables.

    Env vars:
        AAP_GATEWAY_URL        Gateway base URL (required for execute mode)
        AAP_USERNAME           Basic-auth username
        AAP_PASSWORD           Basic-auth password
        AAP_TOKEN              OAuth / personal access token
        AAP_VALIDATE_CERTS     SSL verification (default: true)
        AAP_REQUEST_TIMEOUT    HTTP request timeout in seconds (default: 10)
    """

    gateway_url: Optional[str]
    username: Optional[str]
    password: Optional[str]
    token: Optional[str]
    validate_certs: bool
    request_timeout: float

    @classmethod
    def from_env(cls) -> ServerConfig:
        """Build configuration from environment variables."""
        validate_raw = os.environ.get("AAP_VALIDATE_CERTS", "true").lower()
        validate_certs = validate_raw not in ("false", "0", "no")

        timeout_raw = os.environ.get("AAP_REQUEST_TIMEOUT", "10")
        try:
            request_timeout = float(timeout_raw)
        except ValueError:
            request_timeout = 10.0

        return cls(
            gateway_url=os.environ.get("AAP_GATEWAY_URL"),
            username=os.environ.get("AAP_USERNAME"),
            password=os.environ.get("AAP_PASSWORD"),
            token=os.environ.get("AAP_TOKEN"),
            validate_certs=validate_certs,
            request_timeout=request_timeout,
        )

    def to_gateway_config(self) -> GatewayConfig:
        """Convert to a GatewayConfig instance.

        Raises:
            ValueError: If gateway_url is not set.
        """
        if not self.gateway_url:
            raise ValueError(
                "AAP_GATEWAY_URL environment variable is required for execute mode. "
                "Set it to the base URL of your AAP Gateway (e.g. https://gateway.example.com)."
            )

        return GatewayConfig(
            base_url=self.gateway_url,
            username=self.username,
            password=self.password,
            oauth_token=self.token,
            verify_ssl=self.validate_certs,
            request_timeout=self.request_timeout,
        )
