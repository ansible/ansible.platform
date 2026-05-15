"""Generic Process Manager - Platform SDK.

Generic process management utilities for spawning and connecting to manager processes.
This module is part of the platform SDK and is not Ansible-specific.
"""

import base64
import json
import logging
import os
import secrets
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..platform.config import GatewayConfig

logger = logging.getLogger(__name__)


@dataclass
class ProcessConnectionInfo:
    """Information needed to connect to a manager process."""

    socket_path: str
    authkey: bytes
    authkey_b64: str


class ProcessManager:
    """
    Generic process manager for spawning and managing manager processes.

    This class handles:
    - Socket path generation
    - Authkey generation
    - Process spawning
    - Process startup waiting

    It's generic and not Ansible-specific, making it reusable for CLI, MCP, etc.
    """

    @staticmethod
    def generate_connection_info(identifier: str, socket_dir: Optional[Path] = None, gateway_config: Optional["GatewayConfig"] = None) -> ProcessConnectionInfo:
        """
        Generate connection information for a new manager process.

        Args:
            identifier: Unique identifier (e.g., inventory_hostname)
            socket_dir: Directory for socket files (default: tempdir)
            gateway_config: Gateway configuration (optional, for credential-aware socket path)

        Returns:
            ProcessConnectionInfo with socket_path and authkey
        """
        logger.info("Generating connection info for identifier: %s", identifier)

        if socket_dir is None:
            import tempfile

            socket_dir = Path(tempfile.gettempdir()) / "ansible_platform"

        # Create socket directory with user-only permissions (0700)
        # This prevents other users from enumerating running jobs or accessing error logs
        import os

        socket_dir.mkdir(exist_ok=True)
        try:
            # Set permissions to 0700 (user read/write/execute only)
            os.chmod(socket_dir, 0o700)
            logger.debug("Set socket directory permissions to 0700: %s", socket_dir)
        except OSError as e:
            logger.warning("Failed to set socket directory permissions: %s", e)

        # Include user ID and credentials in socket path to prevent collisions
        # User ID ensures different users on same jump host don't collide
        # Credential hash ensures different credentials get different managers
        import hashlib

        user_id = os.getuid()

        if gateway_config:
            # Create a hash of credentials to include in socket path
            # This ensures different credentials = different socket path = different manager
            cred_string = f"{gateway_config.username or ''}:{gateway_config.password or ''}:{gateway_config.oauth_token or ''}"
            cred_hash = hashlib.sha256(cred_string.encode("utf-8")).hexdigest()[:8]
            socket_path = str(socket_dir / f"manager_{user_id}_{identifier}_{cred_hash}.sock")
            logger.debug("Including user ID (%s) and credentials in socket path (hash: %s...)", user_id, cred_hash[:4])
        else:
            # Backward compatibility: if no gateway_config, use old format but still include user ID
            socket_path = str(socket_dir / f"manager_{user_id}_{identifier}.sock")
            logger.debug("Including user ID (%s) in socket path (no gateway_config provided)", user_id)

        authkey = secrets.token_bytes(32)
        authkey_b64 = base64.b64encode(authkey).decode("utf-8")

        logger.debug("Connection info generated: socket_path=%s, socket_dir=%s, authkey_length=%s", socket_path, socket_dir, len(authkey))

        return ProcessConnectionInfo(socket_path=socket_path, authkey=authkey, authkey_b64=authkey_b64)

    @staticmethod
    def is_socket_stale(socket_path: str) -> bool:
        """
        Check whether the manager process that owns this socket is still alive.

        Uses the companion .meta file (written by base_action.py / http.py at
        spawn time) to retrieve the manager PID, then sends signal 0 to check
        liveness without actually signalling the process.

        Returns:
            True  — socket file exists but the owning process is gone (stale).
            False — socket does not exist, or the owning process is still alive.
        """
        import os as _os

        socket_file = Path(socket_path)
        if not socket_file.exists():
            return False  # nothing to check

        meta_path = Path(f"{socket_path}.meta")
        if not meta_path.exists():
            # No meta file means either the socket is from old code that didn't
            # write meta files, or it hasn't been written yet.  Treat as live
            # so we don't destroy a valid socket on upgrade/rollout.
            logger.debug("is_socket_stale: no meta file for %s — treating as live", socket_path)
            return False

        try:
            import json as _json

            meta = _json.loads(meta_path.read_text())
            pid = meta.get("pid")
            if not pid or not str(pid).isdigit():
                logger.warning("is_socket_stale: meta file has no valid pid for %s", socket_path)
                return True

            pid = int(pid)
            try:
                _os.kill(pid, 0)  # signal 0 = liveness probe, no side-effects
                return False  # process is alive
            except ProcessLookupError:
                logger.warning("is_socket_stale: manager PID %s is gone — stale socket %s", pid, socket_path)
                return True  # PID doesn't exist
            except PermissionError:
                # PID exists but we can't signal it (different owner / security policy).
                # Treat as live — do NOT delete a socket we can't verify is dead.
                logger.debug("is_socket_stale: cannot probe PID %s (PermissionError) — treating as live", pid)
                return False

        except Exception as e:
            logger.warning("is_socket_stale: error reading meta file %s: %s — treating as live", meta_path, e)
            return False

    @staticmethod
    def cleanup_old_socket(socket_path: str) -> None:
        """
        Clean up an old socket file and its companion .meta file if they exist.

        Args:
            socket_path: Path to socket file
        """
        socket_file = Path(socket_path)
        if socket_file.exists():
            try:
                socket_file.unlink()
                logger.debug("Removed old socket: %s", socket_path)
            except Exception as e:
                logger.warning("Failed to remove old socket: %s", e)

        meta_file = Path(f"{socket_path}.meta")
        if meta_file.exists():
            try:
                meta_file.unlink()
                logger.debug("Removed old meta file: %s", meta_file)
            except Exception as e:
                logger.warning("Failed to remove old meta file: %s", e)

    @staticmethod
    def spawn_manager_process(
        script_path: Path,
        socket_path: str,
        socket_dir: str,
        identifier: str,
        gateway_config: "GatewayConfig",  # type: ignore
        authkey_b64: str,
        sys_path: Optional[list] = None,
        owner_pid: Optional[int] = None,
        task_env: Optional[dict] = None,
    ) -> subprocess.Popen:
        """
        Spawn a manager process.

        Args:
            script_path: Path to manager process script
            socket_path: Path to Unix socket
            socket_dir: Directory for socket files
            identifier: Unique identifier (e.g., inventory_hostname)
            gateway_config: Gateway configuration
            authkey_b64: Base64-encoded authkey
            sys_path: Python sys.path to pass to child process
            owner_pid: PID of the owner process (manager self-terminates when owner exits)
            task_env: Resolved task-level environment variables (from Ansible task ``environment:``
                block).  Applied on top of ``os.environ`` so playbook-level cert and proxy
                settings reach the manager subprocess even when they are not present in the
                control-node shell environment.

        Returns:
            Popen process object

        Raises:
            RuntimeError: If process fails to start
        """
        logger.info("Spawning manager process for identifier: %s", identifier)
        logger.debug("Script path: %s, socket: %s, gateway: %s", script_path, socket_path, gateway_config.base_url)

        if sys_path is None:
            sys_path = list(sys.path)

        logger.debug("Preparing to spawn with sys.path containing %s entries", len(sys_path))

        # Encode sys.path for passing via environment
        sys_path_json = json.dumps(sys_path)
        sys_path_b64 = base64.b64encode(sys_path_json.encode("utf-8")).decode("utf-8")

        # Build subprocess environment: shell env + task-level overrides.
        env = os.environ.copy()
        if task_env:
            env.update({k: str(v) for k, v in task_env.items() if v is not None})
            logger.debug("Applied %d task-level environment variable(s) to manager subprocess", len(task_env))

        if env.get("SSL_CERT_FILE") and not env.get("REQUESTS_CA_BUNDLE"):
            env["REQUESTS_CA_BUNDLE"] = env["SSL_CERT_FILE"]
            logger.warning(
                "Deprecated: SSL_CERT_FILE is being mapped to REQUESTS_CA_BUNDLE for backward compatibility. "
                "The manager subprocess uses the requests library which reads REQUESTS_CA_BUNDLE, not SSL_CERT_FILE. "
                "Please set REQUESTS_CA_BUNDLE directly in your environment block. "
                "SSL_CERT_FILE support will be removed in a future release."
            )

        env["ANSIBLE_PLATFORM_SYS_PATH"] = sys_path_b64
        env["ANSIBLE_PLATFORM_AUTHKEY"] = authkey_b64
        if owner_pid is not None:
            # The manager will watch this PID and self-terminate when it exits.
            # Pass the main ansible-playbook process PID so the manager dies
            # automatically when the playbook finishes — zero user config needed.
            env["ANSIBLE_PLATFORM_OWNER_PID"] = str(owner_pid)

        # Build command
        cmd = [
            sys.executable,  # Use same Python interpreter
            str(script_path),
            socket_path,
            socket_dir,
            identifier,
            gateway_config.base_url,
            gateway_config.username or "",
            gateway_config.password or "",
            gateway_config.oauth_token or "",
            str(gateway_config.verify_ssl),
            str(gateway_config.request_timeout),
            str(gateway_config.idle_timeout),
        ]

        logger.debug("Command: %s %s [args: socket_path, socket_dir, identifier, gateway_url, ...]", sys.executable, script_path)

        try:
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent
            )
            logger.info("Manager process started successfully with PID: %s", process.pid)
            return process
        except Exception as e:
            logger.error("Failed to start manager process: %s", e)
            import traceback

            logger.error(traceback.format_exc())
            raise RuntimeError(f"Failed to start manager process: {e}") from e

    @staticmethod
    def wait_for_process_startup(socket_path: str, socket_dir: Path, identifier: str, process: subprocess.Popen, max_wait: int = 50) -> None:
        """
        Wait for manager process to start and create socket.

        Args:
            socket_path: Path to Unix socket
            socket_dir: Directory for socket files
            identifier: Unique identifier (e.g., inventory_hostname)
            process: Process object to monitor
            max_wait: Maximum number of 0.1s intervals to wait

        Raises:
            RuntimeError: If process fails to start within timeout
        """
        logger.info("Waiting for manager process to create socket: %s (max wait: %ss)", socket_path, max_wait * 0.1)

        for attempt in range(max_wait):
            if Path(socket_path).exists():
                logger.info("Socket created successfully after %ss", attempt * 0.1)
                return
            time.sleep(0.1)
            if attempt % 10 == 0 and attempt > 0:  # Log every second
                logger.debug("Still waiting for socket... (%ss elapsed)", attempt * 0.1)

        # Check if there's an error log
        error_log = socket_dir / f"manager_error_{identifier}.log"
        error_msg = f"Manager failed to start within {max_wait * 0.1} seconds"

        if error_log.exists():
            error_content = error_log.read_text()
            error_msg += f"\n\nManager error log:\n{error_content}"
            error_log.unlink()  # Clean up

        # Check if process is still alive
        returncode = process.poll()
        if returncode is not None:
            error_msg += f"\n\nManager process died (exitcode: {returncode})"

        raise RuntimeError(error_msg)


def _af_unix_available():
    """Return True if AF_UNIX sockets can be created on this system."""
    import socket as _socket

    try:
        s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        s.close()
        return True
    except (OSError, AttributeError):
        return False


def spawn_ephemeral_client(task_vars, gateway_config, task_env=None):
    """
    Spawn an ephemeral manager process and return (client, None).

    Used when the connection plugin does not support get_client() (e.g. connection: local),
    so the action plugin can still run platform tasks by spawning a short-lived manager.

    On systems where AF_UNIX sockets are unavailable (e.g. sandboxed VMs), falls back to
    DirectHTTPClient which makes HTTP requests directly without a manager process.

    Callers (e.g. action plugin) should prefer connection: ansible.platform.http when
    persistent mode or connection-level config is desired.

    Args:
        task_vars: Ansible task variables (must contain inventory_hostname or default 'localhost').
        gateway_config: Gateway configuration.
        task_env: Optional dict of resolved task-level environment variables.  These are
            overlaid on top of the control-node shell environment so that playbook-level
            ``environment:`` blocks (e.g. SSL_CERT_FILE, REQUESTS_CA_BUNDLE) reach the
            manager subprocess.

    Returns:
        Tuple of (client, None). Facts are never set for ephemeral (local) path.
    """
    import hashlib
    import time

    from .rpc_client import ManagerRPCClient

    # Fallback to DirectHTTPClient when AF_UNIX sockets are not available
    if not _af_unix_available():
        logger.info("AF_UNIX sockets unavailable; falling back to DirectHTTPClient for ephemeral connection: local")
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient

        client = DirectHTTPClient(gateway_config)
        client._ephemeral = True
        return (client, None)

    inventory_hostname = task_vars.get("inventory_hostname", "localhost")
    host_hash = hashlib.md5(inventory_hostname.encode()).hexdigest()[:4]

    # Use a per-invocation time suffix so each ephemeral manager gets a UNIQUE
    # socket path.  Without this, orphaned managers from prior tasks (which are
    # never explicitly killed for connection: local) hold a reference to the
    # same socket path.  When those orphans eventually exit, Python's
    # SocketListener._unlink finalizer calls os.unlink(socket_path) — deleting
    # the *current* task's socket file and causing FileNotFoundError in
    # ManagerRPCClient._incref() even though connect() succeeded moments before.
    task_suffix = format(int(time.monotonic() * 1000) % 65536, "04x")
    identifier = f"e{host_hash}{task_suffix}"

    socket_dir = Path("/tmp") / "ap"
    socket_dir.mkdir(exist_ok=True, parents=True)

    conn_info = ProcessManager.generate_connection_info(identifier=identifier, socket_dir=socket_dir, gateway_config=gateway_config)
    socket_path = conn_info.socket_path
    authkey = conn_info.authkey
    ProcessManager.cleanup_old_socket(socket_path)

    script_path = Path(__file__).parent / "manager_process.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Manager process script not found at: {script_path}")

    process = ProcessManager.spawn_manager_process(
        script_path=script_path,
        socket_path=socket_path,
        socket_dir=str(socket_dir),
        identifier=identifier,
        gateway_config=gateway_config,
        authkey_b64=conn_info.authkey_b64,
        sys_path=list(sys.path),
        # Pass ansible-playbook's PID so the manager self-terminates when the
        # playbook exits.  This prevents accumulation of orphaned manager
        # processes across successive test runs.
        owner_pid=os.getppid(),
        task_env=task_env,
    )
    ProcessManager.wait_for_process_startup(socket_path=socket_path, socket_dir=socket_dir, identifier=identifier, process=process, max_wait=50)

    client = ManagerRPCClient(gateway_config.base_url, socket_path, authkey)
    client._ephemeral = True
    client.socket_path = socket_path
    logger.info("Ephemeral manager spawned for connection: local at %s", gateway_config.base_url)
    return (client, None)
