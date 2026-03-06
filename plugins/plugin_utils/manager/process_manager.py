"""Generic Process Manager - Platform SDK.

Generic process management utilities for spawning and connecting to manager processes.
This module is part of the platform SDK and is not Ansible-specific.
"""

import sys
import os
import subprocess
import secrets
import base64
import json
import time
import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from dataclasses import dataclass

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
    def generate_connection_info(
        identifier: str,
        socket_dir: Optional[Path] = None,
        gateway_config: Optional['GatewayConfig'] = None
    ) -> ProcessConnectionInfo:
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
            socket_dir = Path(tempfile.gettempdir()) / 'ansible_platform'

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
            cred_hash = hashlib.sha256(cred_string.encode('utf-8')).hexdigest()[:8]
            socket_path = str(socket_dir / f'manager_{user_id}_{identifier}_{cred_hash}.sock')
            logger.debug("Including user ID (%s) and credentials in socket path (hash: %s...)", user_id, cred_hash[:4])
        else:
            # Backward compatibility: if no gateway_config, use old format but still include user ID
            socket_path = str(socket_dir / f'manager_{user_id}_{identifier}.sock')
            logger.debug("Including user ID (%s) in socket path (no gateway_config provided)", user_id)

        authkey = secrets.token_bytes(32)
        authkey_b64 = base64.b64encode(authkey).decode('utf-8')

        logger.debug("Connection info generated: socket_path=%s, socket_dir=%s, authkey_length=%s", socket_path, socket_dir, len(authkey))

        return ProcessConnectionInfo(
            socket_path=socket_path,
            authkey=authkey,
            authkey_b64=authkey_b64
        )

    @staticmethod
    def cleanup_old_socket(socket_path: str) -> None:
        """
        Clean up old socket file if it exists.

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

    @staticmethod
    def spawn_manager_process(
        script_path: Path,
        socket_path: str,
        socket_dir: str,
        identifier: str,
        gateway_config: 'GatewayConfig',  # type: ignore
        authkey_b64: str,
        sys_path: Optional[list] = None
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
        sys_path_b64 = base64.b64encode(sys_path_json.encode('utf-8')).decode('utf-8')

        # Prepare environment
        env = os.environ.copy()
        env['ANSIBLE_PLATFORM_SYS_PATH'] = sys_path_b64
        env['ANSIBLE_PLATFORM_AUTHKEY'] = authkey_b64

        # Build command
        cmd = [
            sys.executable,  # Use same Python interpreter
            str(script_path),
            socket_path,
            socket_dir,
            identifier,
            gateway_config.base_url,
            gateway_config.username or '',
            gateway_config.password or '',
            gateway_config.oauth_token or '',
            str(gateway_config.verify_ssl),
            str(gateway_config.request_timeout)
        ]

        logger.debug("Command: %s %s [args: socket_path, socket_dir, identifier, gateway_url, ...]", sys.executable, script_path)

        try:
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent
            )
            logger.info("Manager process started successfully with PID: %s", process.pid)
            return process
        except Exception as e:
            logger.error("Failed to start manager process: %s", e)
            import traceback
            logger.error(traceback.format_exc())
            raise RuntimeError(f"Failed to start manager process: {e}") from e

    @staticmethod
    def wait_for_process_startup(
        socket_path: str,
        socket_dir: Path,
        identifier: str,
        process: subprocess.Popen,
        max_wait: int = 50
    ) -> None:
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
        error_log = socket_dir / f'manager_error_{identifier}.log'
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
