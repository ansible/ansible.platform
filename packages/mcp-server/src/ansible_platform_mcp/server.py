"""MCP server for ansible.platform.

Dynamically generates one tool per collection resource from DOCUMENTATION
metadata. Each tool supports dual-mode operation: 'execute' calls the
AAP Gateway API directly; 'emit' returns the equivalent Ansible task YAML.

Uses the low-level MCP server for full control over tool listing and dispatch.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from . import __version__
from .config import ServerConfig
from .discovery import ModuleInfo, discover_modules
from .emitter import emit_task
from .executor import GatewayExecutor
from .schema import build_tool_schema

logger = logging.getLogger(__name__)

TOOL_PREFIX = "ansible_platform_"


def _build_tool_registry(
    collection_root: Path | None = None,
) -> dict[str, tuple[types.Tool, ModuleInfo]]:
    """Discover modules and build MCP Tool objects with JSON Schema.

    Returns:
        Dict mapping tool name -> (Tool definition, ModuleInfo).
    """
    modules = discover_modules(collection_root)
    registry: dict[str, tuple[types.Tool, ModuleInfo]] = {}

    for mod in modules.values():
        tool_name = f"{TOOL_PREFIX}{mod.name}"
        input_schema = build_tool_schema(mod.name, mod.options, mod.has_state)

        description = mod.short_description
        if mod.has_state:
            description += " Operations: create, update, delete, find."
        else:
            description += " Operation: update."
        description += " Set mode to 'emit' to return Ansible task YAML instead of executing."

        tool = types.Tool(
            name=tool_name,
            description=description,
            inputSchema=input_schema,
        )
        registry[tool_name] = (tool, mod)

    logger.info("Built %d MCP tools from collection modules", len(registry))
    return registry


def create_server(collection_root: Path | None = None) -> tuple[Server, dict[str, tuple[types.Tool, ModuleInfo]]]:
    """Create and configure the MCP server.

    Args:
        collection_root: Path to the ansible.platform collection root.

    Returns:
        Tuple of (Server, tool_registry).
    """
    server = Server("ansible-platform")
    config = ServerConfig.from_env()
    executor = GatewayExecutor(config)
    tool_registry = _build_tool_registry(collection_root)

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return [tool for tool, _mod in tool_registry.values()]

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict[str, Any] | None
    ) -> list[types.TextContent]:
        if name not in tool_registry:
            raise ValueError(f"Unknown tool: {name}")

        arguments = dict(arguments or {})
        _tool, mod = tool_registry[name]

        operation = arguments.pop("operation", None)
        if not operation:
            raise ValueError("'operation' argument is required")

        mode = arguments.pop("mode", "execute")

        if mode == "emit":
            yaml_text = emit_task(mod.name, operation, arguments)
            return [types.TextContent(type="text", text=yaml_text)]

        elif mode == "execute":
            if not config.gateway_url:
                raise ValueError(
                    "Cannot execute: AAP_GATEWAY_URL environment variable is not set. "
                    "Use mode='emit' to generate Ansible task YAML without a Gateway connection."
                )
            try:
                result = await asyncio.to_thread(
                    executor.execute, operation, mod.name, arguments
                )
            except Exception as exc:
                error_result = {
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "operation": operation,
                    "resource": mod.name,
                }
                return [types.TextContent(
                    type="text",
                    text=json.dumps(error_result, indent=2),
                )]

            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str),
            )]

        else:
            raise ValueError(f"Unknown mode: {mode!r}. Must be 'execute' or 'emit'.")

    return server, tool_registry


async def run(collection_root: Path | None = None) -> None:
    """Run the MCP server over stdio."""
    server, tool_registry = create_server(collection_root)

    logger.info(
        "Starting ansible-platform MCP server v%s with %d tools",
        __version__,
        len(tool_registry),
    )

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ansible-platform",
                server_version=__version__,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    """Entry point for the ansible-platform-mcp command."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
