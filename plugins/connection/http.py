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
  - Mode is controlled by the C(persistent) connection option or
    C(ansible_platform_use_persistent_connection) variable (P3).
  - |
    Connection parameters that define tenancy (when a new persistent manager is created vs reused):
    C(gateway_hostname) (or C(gateway_url)), credentials (C(gateway_username)/password/token), and host.
    One persistent manager per (play, host, connection params); no sharing across different params.
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
      - name: ansible_platform_persistent
    ini:
      - section: platform_connection
        key: persistent
    env:
      - name: ANSIBLE_PLATFORM_PERSISTENT
"""

import base64
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Union

from ansible.plugins.connection import ConnectionBase
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import ProcessManager
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient

if TYPE_CHECKING:
    from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig
    from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient

logger = logging.getLogger(__name__)


class Connection(ConnectionBase):
    """
    Platform connection plugin for HTTP API connections.

    This connection plugin can operate in two modes:
    1. Persistent mode: Uses a persistent manager process (better performance)
    2. Direct mode: Creates new HTTP connections per task (simpler, default)

    Mode is controlled by the 'persistent' connection option.
    """

    transport = "ansible.platform.http"
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

    def get_client(
        self, task_vars: dict, gateway_config: "GatewayConfig", task_env: Optional[dict] = None
    ) -> Tuple[Union["DirectHTTPClient", "ManagerRPCClient"], Optional[Dict[str, Any]]]:
        """
        Dispatcher: Get the appropriate client based on connection configuration.

        This method is the dispatcher within the connection plugin. It is called
        by the action plugin's dispatcher (_dispatch_to_connection) and routes
        to the appropriate client implementation based on the 'persistent' option.

        Dispatch Logic:
        1. Check connection option 'persistent' (if set)
        2. Check variable 'ansible_platform_use_persistent_connection' or 'ansible_platform_persistent' (if set)
        3. Default: False (direct mode)
        4. Route to:
           - persistent: true -> _get_persistent_client() -> ManagerRPCClient
           - persistent: false -> _get_direct_client() -> DirectHTTPClient

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

        def _truthy(val):
            if val is None:
                return False
            if isinstance(val, bool):
                return val
            return str(val).lower() in ("true", "yes", "1")

        try:
            persistent = _truthy(self.get_option("persistent"))
        except (AttributeError, KeyError):
            # Option not defined, check variables (P3: ansible_platform_use_persistent_connection; alias ansible_platform_persistent)
            hostvars = task_vars.get("hostvars", {})
            inventory_hostname = task_vars.get("inventory_hostname", "localhost")
            host_vars = hostvars.get(inventory_hostname, {})
            raw = (
                host_vars.get("ansible_platform_use_persistent_connection")
                or task_vars.get("ansible_platform_use_persistent_connection")
                or host_vars.get("ansible_platform_persistent")
                or task_vars.get("ansible_platform_persistent")
            )
            persistent = _truthy(raw)

        # Route to appropriate client implementation
        if persistent:
            logger.debug("Connection plugin dispatcher: Routing to persistent client (ManagerRPCClient)")
            # task_env is intentionally NOT forwarded to persistent mode: the manager
            # process is spawned once at connection setup time (before any task
            # environment: block is evaluated) and is reused across tasks.
            # Task-level env vars cannot retroactively affect an already-running manager.
            return self._get_persistent_client(task_vars, gateway_config)
        else:
            logger.debug("Connection plugin dispatcher: Routing to direct client (DirectHTTPClient)")
            return self._get_direct_client(task_vars, gateway_config, task_env=task_env)

    def _get_direct_client(
        self, task_vars: dict, gateway_config: "GatewayConfig", task_env: Optional[dict] = None
    ) -> Tuple["ManagerRPCClient", Optional[Dict[str, Any]]]:
        """
        Get ManagerRPCClient for direct mode (non-persistent).

        In direct mode, we still use the manager process architecture (same as persistent mode)
        but spawn a NEW manager for each task and mark it for immediate shutdown.
        This ensures both modes use the same architecture (TransitMixin, API version detection, etc.)
        The only difference is lifecycle management: persistent keeps managers alive, direct shuts them down.

        Args:
            task_vars: Task variables from Ansible
            gateway_config: Gateway configuration
            task_env: Optional dict of resolved task-level environment variables
                (from Ansible task ``environment:`` block). These are overlaid on top
                of the control-node shell environment so that playbook-level cert and
                proxy settings reach the manager subprocess.

        Returns:
            Tuple of (ManagerRPCClient, facts_dict)
        """
        import sys
        from pathlib import Path

        try:
            logger.debug("Platform connection (direct mode): Spawning ephemeral manager (will be shut down after task)")

            # Get inventory hostname for unique identifier
            inventory_hostname = task_vars.get("inventory_hostname", "localhost")
            logger.debug("Inventory hostname: %s", inventory_hostname)

            # Use a very short identifier to avoid "AF_UNIX path too long" error
            # Unix domain socket paths are limited to ~104 characters on macOS
            import hashlib
            import time

            host_hash = hashlib.md5(inventory_hostname.encode()).hexdigest()[:4]
            # Include a per-invocation suffix so loop iterations on the same host
            # each get a unique socket path. Without this, iteration N+1 spawns a
            # new manager at the same path as iteration N, but the action plugin
            # still holds a proxy referencing the old (now dead) manager's object
            # ident, causing a KeyError in multiprocessing.managers.serve_client.
            task_suffix = format(int(time.monotonic() * 1000) % 65536, "04x")
            identifier = f"e{host_hash}{task_suffix}"  # "e" + host + per-task suffix
            logger.debug("Generated identifier: %s", identifier)

            # Generate connection info with shorter socket directory
            socket_dir = Path("/tmp") / "ap"  # Very short path to avoid AF_UNIX limit
            logger.debug("Socket directory: %s", socket_dir)

            try:
                socket_dir.mkdir(exist_ok=True, parents=True)  # Ensure directory exists
                logger.debug("Created socket directory: %s", socket_dir)
            except Exception as e:
                logger.error("Failed to create socket directory %s: %s", socket_dir, e)
                raise

            logger.debug("Generating connection info...")
            conn_info = ProcessManager.generate_connection_info(identifier=identifier, socket_dir=socket_dir, gateway_config=gateway_config)

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

            script_path = Path(__file__).parent.parent / "plugin_utils" / "manager" / "manager_process.py"

            logger.debug("Calculated script_path: %s", script_path)
            logger.debug("Script exists: %s", script_path.exists())

            if not script_path.exists():
                raise FileNotFoundError(f"Manager process script not found at: {script_path}")

            # Spawn ephemeral manager process
            logger.debug("Spawning ephemeral manager process...")
            if task_env:
                logger.debug("Forwarding %d task-level env var(s) to direct manager: %s", len(task_env), list(task_env.keys()))
            process = ProcessManager.spawn_manager_process(
                script_path=script_path,
                socket_path=socket_path,
                socket_dir=str(socket_dir),
                identifier=identifier,
                gateway_config=gateway_config,
                authkey_b64=authkey_b64,
                sys_path=list(sys.path),
                owner_pid=os.getppid(),
                task_env=task_env,
            )
            logger.debug("Manager process spawned with PID: %s", process.pid)

            # Wait for manager to start and create socket
            logger.debug("Waiting for manager process to be ready...")
            ProcessManager.wait_for_process_startup(
                socket_path=socket_path,
                socket_dir=socket_dir,
                identifier=identifier,
                process=process,
                max_wait=50,  # 5 seconds max
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

        # Return client without facts (direct mode doesn't persist facts)
        return client, None

    def _get_persistent_client(self, task_vars: dict, gateway_config: "GatewayConfig") -> Tuple["ManagerRPCClient", Optional[Dict[str, Any]]]:
        """
        Get ManagerRPCClient with persistent manager.

        Args:
            task_vars: Task variables from Ansible
            gateway_config: Gateway configuration

        Returns:
            Tuple of (ManagerRPCClient, facts_dict)
        """
        logger.debug("Platform connection (persistent mode): Getting or spawning manager")

        # Get inventory hostname
        inventory_hostname = task_vars.get("inventory_hostname", "localhost")

        # Generate deterministic connection info based on credentials + host.
        # If an existing manager is already running for these credentials, the
        # socket path will match and we can reuse it.
        socket_dir = Path(tempfile.gettempdir()) / "ansible_platform"
        conn_info = ProcessManager.generate_connection_info(identifier=inventory_hostname, socket_dir=socket_dir, gateway_config=gateway_config)

        expected_socket_path = str(conn_info.socket_path)
        meta_path = expected_socket_path + ".meta"

        # ------------------------------------------------------------------ #
        # Fast path: try to connect without acquiring the lock.               #
        # If a live manager is already running (socket + meta both present    #
        # and PID alive) we can connect immediately and skip the lock         #
        # entirely.  The lock is only needed to serialize the spawn path.     #
        # ------------------------------------------------------------------ #
        if Path(expected_socket_path).exists() and Path(meta_path).exists():
            if ProcessManager.is_socket_stale(expected_socket_path):
                logger.warning(
                    "Stale socket detected at %s (manager process gone). Cleaning up.",
                    expected_socket_path,
                )
                ProcessManager.cleanup_old_socket(expected_socket_path)
            else:
                try:
                    with open(meta_path, "r") as _mf:
                        _meta = json.load(_mf)
                    candidate_authkey_b64 = _meta.get("authkey_b64")
                    if candidate_authkey_b64 and Path(expected_socket_path).is_socket():
                        authkey = base64.b64decode(candidate_authkey_b64)
                        client = ManagerRPCClient(gateway_config.base_url, expected_socket_path, authkey)
                        logger.info("Reusing existing persistent manager via meta file (fast path): %s", expected_socket_path)
                        return client, None  # No ansible_facts — secrets stay on disk
                except Exception as _e:
                    logger.warning(
                        "Could not connect to manager at %s: %s — will retry under lock",
                        expected_socket_path,
                        _e,
                    )
                    ProcessManager.cleanup_old_socket(expected_socket_path)

        # ------------------------------------------------------------------ #
        # Locked spawn path.                                                  #
        # fcntl.flock serializes parallel worker processes: exactly one       #
        # worker spawns a new manager while the others block on the lock,     #
        # then find the running manager on the re-check and connect to it.    #
        # ------------------------------------------------------------------ #
        import fcntl as _fcntl

        lock_path = expected_socket_path + ".lock"
        _lockfile = open(lock_path, "w")
        try:
            _fcntl.flock(_lockfile, _fcntl.LOCK_EX)
            logger.debug("Acquired spawn lock: %s", lock_path)

            # Re-check inside the lock — another worker may have spawned the
            # manager while we were waiting for the exclusive lock.
            if Path(expected_socket_path).exists() and Path(meta_path).exists():
                if ProcessManager.is_socket_stale(expected_socket_path):
                    ProcessManager.cleanup_old_socket(expected_socket_path)
                else:
                    try:
                        with open(meta_path, "r") as _mf:
                            _meta = json.load(_mf)
                        candidate_authkey_b64 = _meta.get("authkey_b64")
                        if candidate_authkey_b64 and Path(expected_socket_path).is_socket():
                            authkey = base64.b64decode(candidate_authkey_b64)
                            client = ManagerRPCClient(gateway_config.base_url, expected_socket_path, authkey)
                            logger.info("Reusing existing persistent manager via meta file (post-lock check): %s", expected_socket_path)
                            return client, None
                    except Exception as _e:
                        logger.warning(
                            "Post-lock connect to manager at %s failed: %s — spawning new",
                            expected_socket_path,
                            _e,
                        )
                        ProcessManager.cleanup_old_socket(expected_socket_path)

            # ------------------------------------------------------------------ #
            # No live manager found — spawn a new one.                            #
            # ------------------------------------------------------------------ #
            logger.info("Spawning new persistent manager for host: %s", inventory_hostname)

            socket_path = conn_info.socket_path
            authkey = conn_info.authkey
            authkey_b64 = conn_info.authkey_b64

            # Clean up old socket if exists
            ProcessManager.cleanup_old_socket(socket_path)

            # Get path to manager process script
            script_path = Path(__file__).parent.parent / "plugin_utils" / "manager" / "manager_process.py"
            logger.debug("Script path for persistent manager: %s", script_path)
            logger.debug("Script exists: %s", script_path.exists())

            if not script_path.exists():
                raise FileNotFoundError(f"Manager script not found at: {script_path}")

            # Spawn manager process
            # Pass os.getppid() as owner_pid — in a worker fork this is the main
            # ansible-playbook process.  The manager's watchdog thread will watch
            # that PID and self-terminate when the playbook process exits.
            process = ProcessManager.spawn_manager_process(
                script_path=script_path,
                socket_path=socket_path,
                socket_dir=str(socket_dir),
                identifier=inventory_hostname,
                gateway_config=gateway_config,
                authkey_b64=authkey_b64,
                sys_path=list(sys.path),
                owner_pid=os.getppid(),
            )

            # Wait for manager to start and create socket
            logger.debug("Waiting for persistent manager process to be ready...")
            ProcessManager.wait_for_process_startup(
                socket_path=socket_path,
                socket_dir=socket_dir,
                identifier=inventory_hostname,
                process=process,
                max_wait=50,  # 5 seconds max
            )
            logger.debug("Persistent manager process is ready")

            # Write companion .meta file so the cleanup callback (and any other
            # process) can discover this manager without going through ansible_facts.
            # Secrets stay on disk — they never appear in task output.
            socket_path_str = str(socket_path)
            _meta_path = socket_path_str + ".meta"
            try:
                with open(_meta_path, "w") as _mf:
                    json.dump({"pid": process.pid, "authkey_b64": authkey_b64, "gateway_url": gateway_config.base_url}, _mf)
                logger.debug("Wrote manager meta file: %s", _meta_path)
            except Exception as _e:
                logger.warning("Could not write manager meta file %s: %s", _meta_path, _e)

            # Connect to manager
            client = ManagerRPCClient(gateway_config.base_url, socket_path_str, authkey)

            logger.info("Successfully spawned and connected to persistent manager: %s", socket_path_str)

        finally:
            _fcntl.flock(_lockfile, _fcntl.LOCK_UN)
            _lockfile.close()
            logger.debug("Released spawn lock: %s", lock_path)

        # Return None for facts — no secrets in ansible_facts output
        return client, None

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
