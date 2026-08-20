"""Lazy PlatformService wrapper for executing operations against AAP Gateway.

Delegates to PlatformService.execute() for all CRUD operations.
The ansible-platform-sdk package provides the collection imports.
"""

from __future__ import annotations

import logging
from typing import Any

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService

from .config import ServerConfig

logger = logging.getLogger(__name__)

_OPERATION_TO_STATE: dict[str, str] = {
    "create": "present",
    "update": "present",
    "delete": "absent",
    "find": "exists",
}


class GatewayExecutor:
    """Lazy wrapper around PlatformService for executing Gateway operations.

    The PlatformService is not created until the first execute() call,
    so the MCP server can start (and serve emit-mode requests) without
    a live Gateway connection.
    """

    def __init__(self, config: ServerConfig) -> None:
        self._config = config
        self._service: PlatformService | None = None

    def _get_service(self) -> PlatformService:
        """Initialize PlatformService on first use."""
        if self._service is not None:
            return self._service

        gateway_config = self._config.to_gateway_config()
        self._service = PlatformService(gateway_config)
        logger.info("PlatformService initialized for %s", gateway_config.base_url)
        return self._service

    def execute(self, operation: str, module_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute an operation against the Gateway.

        Args:
            operation: One of 'create', 'update', 'delete', 'find'.
            module_name: Resource module name (e.g. 'user').
            params: Resource parameters as a plain dict.

        Returns:
            Result dict from PlatformService.execute().

        Raises:
            ValueError: If operation is unknown or gateway URL is not configured.
        """
        service = self._get_service()

        state = _OPERATION_TO_STATE.get(operation)
        if state is None:
            raise ValueError(f"Unknown operation: {operation!r}. Must be one of: {list(_OPERATION_TO_STATE)}")

        ansible_data = dict(params)
        ansible_data["state"] = state

        # Delete and update require the resource ID. If the caller didn't
        # supply one, look up the resource first so the SDK can proceed.
        if operation in ("delete", "update") and not ansible_data.get("id"):
            existing = service.execute("find", module_name, dict(ansible_data))
            resource_id = existing.get("id")
            if not resource_id:
                raise ValueError(f"Cannot {operation}: resource not found for lookup")
            ansible_data["id"] = resource_id

        logger.info("Executing %s on %s", operation, module_name)
        return service.execute(operation, module_name, ansible_data)
