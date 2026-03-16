#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
author: Ansible Platform Collection Contributors (@rohithakur2590)
name: http
short_description: HTTP connection plugin for Ansible Automation Platform API
description:
  - This connection plugin provides HTTP connections to the Ansible Automation Platform API.
  - |
    It supports two connection modes: persistent (manager process, better performance)
    and direct (new connections per task, default).
  - Mode is controlled by the C(persistent) connection option.
version_added: 1.0.0
options:
  persistent:
    description:
      - Whether to use a persistent manager process for connections.
      - When C(true), a persistent manager process is spawned that maintains HTTP sessions across tasks.
        This provides better performance for playbooks with multiple tasks.
      - When C(false) (default), each task creates a new direct HTTP connection.
    type: boolean
    default: false
    vars:
      - name: ansible_platform_use_persistent_connection
    ini:
      - section: platform_connection
        key: persistent
    env:
      - name: ANSIBLE_PLATFORM_USE_PERSISTENT_CONNECTION
"""

import base64
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Tuple, Optional, Dict, Any, Union

from ansible.plugins.connection import ConnectionBase

if TYPE_CHECKING:
    from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
    from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient
    from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig

logger = logging.getLogger(__name__)


class Connection(ConnectionBase):
    """
    Platform connection plugin for HTTP API connections.

    This connection plugin can operate in two modes:
    1. Persistent mode: Uses a persistent manager process (better performance)
    2. Direct mode: Creates new HTTP connections per task (simpler, default)

    Mode is controlled by the 'persistent' connection option.
    """

    transport = 'ansible.platform.http'
    has_pipelining = False
    become_methods = []

    def __init__(self, *args, **kwargs):
        """Initialize platform connection plugin."""
        super(Connection, self).__init__(*args, **kwargs)
        self._client = None
        self._facts_dict = None

    def _connect(self):
        """
        Establish connection (required by ConnectionBase).

        For platform connection, we don't establish a traditional connection.
        Connection is handled via get_client() which returns HTTP clients.
        This method just marks the connection as connected.
        """
        self._connected = True
        return self

    def _benchmark_record_sessions(self, http_delta: int = 1, tls_delta: int = 1) -> None:
        """
        When BENCHMARK_STATS_FILE is set, increment http_sessions and tls_sessions in that JSON file.
        Used by the benchmark script to report actual session counts (direct vs persistent).
        """
        stats_path = os.environ.get('BENCHMARK_STATS_FILE')
        if not stats_path:
            return
        try:
            data = {'http_sessions': 0, 'tls_sessions': 0}
            path = Path(stats_path)
            if path.exists():
                with open(path, 'r') as f:
                    data = json.load(f)
            data['http_sessions'] = data.get('http_sessions', 0) + http_delta
            data['tls_sessions'] = data.get('tls_sessions', 0) + tls_delta
            with open(path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning("Benchmark stats file update failed: %s", e)

    def get_client(
        self,
        task_vars: dict,
        gateway_config: 'GatewayConfig'
    ) -> Tuple[Union['DirectHTTPClient', 'ManagerRPCClient'], Optional[Dict[str, Any]]]:
        """
        Dispatcher: Get the appropriate client based on connection configuration.

        This method is the dispatcher within the connection plugin. It is called
        by the action plugin's dispatcher (_dispatch_to_connection) and routes
        to the appropriate client implementation based on the 'persistent' option.

        Dispatch Logic:
        1. Check connection option 'persistent' (if set)
        2. Check variable 'ansible_platform_use_persistent_connection' (if set)
        3. Default: False (direct mode)
        4. Route to:
           - persistent: true → _get_persistent_client() → ManagerRPCClient
           - persistent: false → _get_direct_client() → DirectHTTPClient

        Args:
            task_vars: Task variables from Ansible
            gateway_config: Gateway configuration

        Returns:
            Tuple of (client, facts_dict):
            - client: DirectHTTPClient or ManagerRPCClient
            - facts_dict: Dict with facts to set (only for persistent mode), None otherwise
        """
        # DISPATCHER: Determine which client to use based on configuration
        # NOTE: This dispatcher is only reached if action plugin doesn't delegate to module
        # In direct mode, action plugin should delegate to regular module (which can use Request())
        persistent = False  # Default to direct mode

        try:
            persistent = self.get_option('persistent') or False
        except (AttributeError, KeyError):
            # Option not defined, check variables
            hostvars = task_vars.get('hostvars', {})
            inventory_hostname = task_vars.get('inventory_hostname', 'localhost')
            host_vars = hostvars.get(inventory_hostname, {})
            persistent = host_vars.get('ansible_platform_use_persistent_connection') or task_vars.get('ansible_platform_use_persistent_connection') or False

        # Route to appropriate client implementation
        if persistent:
            logger.debug("Connection plugin dispatcher: Routing to persistent client (ManagerRPCClient)")
            return self._get_persistent_client(task_vars, gateway_config)
        else:
            logger.debug("Connection plugin dispatcher: Routing to direct client (DirectHTTPClient)")
            return self._get_direct_client(task_vars, gateway_config)

    def _get_direct_client(
        self,
        task_vars: dict,
        gateway_config: 'GatewayConfig'
    ) -> Tuple['ManagerRPCClient', Optional[Dict[str, Any]]]:
        """
        Get ManagerRPCClient for direct mode (non-persistent).

        In direct mode, we still use the manager process architecture (same as persistent mode)
        but spawn a NEW manager for each task and mark it for immediate shutdown.
        This ensures both modes use the same architecture (TransitMixin, API version detection, etc.)
        The only difference is lifecycle management: persistent keeps managers alive, direct shuts them down.

        Args:
            task_vars: Task variables from Ansible
            gateway_config: Gateway configuration

        Returns:
            Tuple of (ManagerRPCClient, facts_dict)
        """
        import base64
        import sys
        import tempfile
        from pathlib import Path

        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import (
            ProcessManager
        )
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient

        try:
            logger.debug("Platform connection (direct mode): Spawning ephemeral manager (will be shut down after task)")

            # Get inventory hostname for unique identifier
            inventory_hostname = task_vars.get('inventory_hostname', 'localhost')
            logger.debug("Inventory hostname: %s", inventory_hostname)

            # Use a very short identifier to avoid "AF_UNIX path too long" error
            # Unix domain socket paths are limited to ~104 characters on macOS
            import hashlib
            # Hash the hostname to keep it short
            host_hash = hashlib.md5(inventory_hostname.encode()).hexdigest()[:4]
            identifier = f"e{host_hash}"  # "e" for ephemeral + 4-char hash
            logger.debug("Generated identifier: %s", identifier)

            # Generate connection info with shorter socket directory
            socket_dir = Path('/tmp') / 'ap'  # Very short path to avoid AF_UNIX limit
            logger.debug("Socket directory: %s", socket_dir)

            try:
                socket_dir.mkdir(exist_ok=True, parents=True)  # Ensure directory exists
                logger.debug("Created socket directory: %s", socket_dir)
            except Exception as e:
                logger.error("Failed to create socket directory %s: %s", socket_dir, e)
                raise

            logger.debug("Generating connection info...")
            conn_info = ProcessManager.generate_connection_info(
                identifier=identifier,
                socket_dir=socket_dir,
                gateway_config=gateway_config
            )

            socket_path = conn_info.socket_path
            authkey = conn_info.authkey
            authkey_b64 = conn_info.authkey_b64
            logger.debug("Socket path: %s (length: %s)", socket_path, len(socket_path))

            # Clean up old socket if exists
            logger.debug("Cleaning up old socket if exists...")
            ProcessManager.cleanup_old_socket(socket_path)

            # Get path to manager process script
            # __file__ is plugins/connection/platform.py
            # We need plugins/plugin_utils/manager/manager_process.py
            logger.debug("__file__: %s", __file__)
            logger.debug("Parent: %s", Path(__file__).parent)
            logger.debug("Parent.parent: %s", Path(__file__).parent.parent)

            script_path = Path(__file__).parent.parent / 'plugin_utils' / 'manager' / 'manager_process.py'

            logger.debug("Calculated script_path: %s", script_path)
            logger.debug("Script exists: %s", script_path.exists())

            if not script_path.exists():
                raise FileNotFoundError(f"Manager process script not found at: {script_path}")

            # Spawn ephemeral manager process
            logger.debug("Spawning ephemeral manager process...")
            process = ProcessManager.spawn_manager_process(
                script_path=script_path,
                socket_path=socket_path,
                socket_dir=str(socket_dir),
                identifier=identifier,
                gateway_config=gateway_config,
                authkey_b64=authkey_b64,
                sys_path=list(sys.path)
            )
            logger.debug("Manager process spawned with PID: %s", process.pid)

            # Wait for manager to start and create socket
            logger.debug("Waiting for manager process to be ready...")
            ProcessManager.wait_for_process_startup(
                socket_path=socket_path,
                socket_dir=socket_dir,
                identifier=identifier,
                process=process,
                max_wait=50  # 5 seconds max
            )
            logger.debug("Manager process is ready")

        except Exception as e:
            logger.error("Failed to spawn ephemeral manager: %s: %s", type(e).__name__, e)
            import traceback
            logger.error("Traceback: %s", traceback.format_exc())
            raise

        # Connect to manager
        logger.debug("Connecting to ephemeral manager...")
        client = ManagerRPCClient(gateway_config.base_url, socket_path, authkey)

        # Mark the client as ephemeral (should be shut down after task)
        client._ephemeral = True
        client.socket_path = socket_path  # Store for cleanup

        logger.info("Ephemeral manager spawned for %s at %s", gateway_config.base_url, socket_path)

        # Benchmark: each new manager = 1 HTTP session + 1 TLS session
        self._benchmark_record_sessions(1, 1)

        # Return client without facts (direct mode doesn't persist facts)
        return client, None

    def _get_persistent_client(
        self,
        task_vars: dict,
        gateway_config: 'GatewayConfig'
    ) -> Tuple['ManagerRPCClient', Optional[Dict[str, Any]]]:
        """
        Get ManagerRPCClient with persistent manager.

        Args:
            task_vars: Task variables from Ansible
            gateway_config: Gateway configuration

        Returns:
            Tuple of (ManagerRPCClient, facts_dict)
        """
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import (
            ProcessManager
        )
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient

        logger.debug("Platform connection (persistent mode): Getting or spawning manager")

        # Get inventory hostname
        inventory_hostname = task_vars.get('inventory_hostname', 'localhost')

        # Check for existing manager in hostvars
        hostvars = task_vars.get('hostvars', {})
        host_vars = hostvars.get(inventory_hostname, {})

        # Check for manager info in facts
        socket_path_raw = host_vars.get('platform_manager_socket') or task_vars.get('platform_manager_socket')
        authkey_b64 = host_vars.get('platform_manager_authkey') or task_vars.get('platform_manager_authkey')

        # Convert to plain string (Fedora/_AnsibleTaggedStr compatibility)
        socket_path = None
        if socket_path_raw:
            socket_path = f"{socket_path_raw}"
            if not isinstance(socket_path, str):
                socket_path = str(socket_path)

        # Validate socket if found
        if socket_path and Path(socket_path).exists() and authkey_b64:
            # Reuse existing manager (no new HTTP/TLS session)
            try:
                authkey = base64.b64decode(authkey_b64)
                client = ManagerRPCClient(gateway_config.base_url, socket_path, authkey)
                logger.info("Reusing existing persistent manager: %s", socket_path)
                return client, None
            except Exception as e:
                logger.warning("Failed to connect to existing manager: %s, spawning new one", e)

        # Spawn new manager
        logger.info("Spawning new persistent manager for host: %s", inventory_hostname)

        # Generate connection info
        socket_dir = Path(tempfile.gettempdir()) / 'ansible_platform'
        conn_info = ProcessManager.generate_connection_info(
            identifier=inventory_hostname,
            socket_dir=socket_dir,
            gateway_config=gateway_config
        )

        socket_path = conn_info.socket_path
        authkey = conn_info.authkey
        authkey_b64 = conn_info.authkey_b64

        # Clean up old socket if exists
        ProcessManager.cleanup_old_socket(socket_path)

        # Get path to manager process script
        script_path = Path(__file__).parent.parent / 'plugin_utils' / 'manager' / 'manager_process.py'
        logger.debug("Script path for persistent manager: %s", script_path)
        logger.debug("Script exists: %s", script_path.exists())

        if not script_path.exists():
            raise FileNotFoundError(f"Manager script not found at: {script_path}")

        # Spawn manager process
        process = ProcessManager.spawn_manager_process(
            script_path=script_path,
            socket_path=socket_path,
            socket_dir=str(socket_dir),
            identifier=inventory_hostname,
            gateway_config=gateway_config,
            authkey_b64=authkey_b64,
            sys_path=list(sys.path)
        )

        # Wait for manager to start and create socket
        logger.debug("Waiting for persistent manager process to be ready...")
        ProcessManager.wait_for_process_startup(
            socket_path=socket_path,
            socket_dir=socket_dir,
            identifier=inventory_hostname,
            process=process,
            max_wait=50  # 5 seconds max
        )
        logger.debug("Persistent manager process is ready")

        # Connect to manager
        client = ManagerRPCClient(gateway_config.base_url, socket_path, authkey)

        # Benchmark: one new manager = 1 HTTP session + 1 TLS session
        self._benchmark_record_sessions(1, 1)

        # Return facts to set
        facts_dict = {
            'platform_manager_socket': socket_path,
            'platform_manager_authkey': authkey_b64,
            'gateway_url': gateway_config.base_url
        }

        logger.info("Successfully spawned and connected to persistent manager: %s", socket_path)

        return client, facts_dict

    def exec_command(self, cmd, in_data=None, sudoable=True):
        """Not used for platform connection - API calls go through get_client()."""
        raise NotImplementedError("Platform connection uses API calls, not command execution")

    def put_file(self, in_path, out_path):
        """Not used for platform connection."""
        raise NotImplementedError("Platform connection does not support file transfer")

    def fetch_file(self, in_path, out_path):
        """Not used for platform connection."""
        raise NotImplementedError("Platform connection does not support file transfer")

    def close(self):
        """Close connection - cleanup manager if needed."""
        # Manager cleanup is handled by action plugin cleanup() method
        pass
