#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Base action plugin for platform resources.

Provides common functionality inherited by all resource action plugins.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import base64
import fcntl
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Tuple, Union, Optional, Dict, Any

import yaml

from ansible.errors import AnsibleError
from ansible.module_utils.common.arg_spec import ArgumentSpecValidator
from ansible.plugins.action import ActionBase

if TYPE_CHECKING:
    from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
    from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient

logger = logging.getLogger(__name__)


def _manager_process_entry(socket_path, socket_dir, inventory_hostname, gateway_url,
                           gateway_username, gateway_password, gateway_token,
                           gateway_validate_certs, gateway_request_timeout, authkey_b64, sys_path):
    """
    Entry point for the manager process.

    This is a module-level function so it can be pickled for multiprocessing.spawn.
    Uses the same pattern as python-multiproc repository.
    """
    import sys
    import traceback
    import base64
    from pathlib import Path

    # Redirect stderr to a file for debugging
    error_log_path = Path(socket_dir) / f'manager_error_{inventory_hostname}.log'
    stderr_log = Path(socket_dir) / f'manager_stderr_{inventory_hostname}.log'

    try:
        sys.stderr = open(stderr_log, 'w', buffering=1)
        sys.stdout = open(stderr_log, 'a', buffering=1)
    except Exception as e:
        pass  # Continue without redirecting

    try:
        # Restore parent's sys.path in child process (spawn starts fresh)
        sys.path = sys_path

        # Decode authkey from base64 string
        authkey = base64.b64decode(authkey_b64.encode('utf-8'))

        # Write to log immediately to capture any early failures
        with open(error_log_path, 'w') as f:
            f.write(f"Process started, socket_path={socket_path}\n")
            f.write(f"sys.path has {len(sys_path)} entries\n")
            f.write(f"Manager starting at {socket_path}\n")
            f.write(f"About to create service with base_url={gateway_url}\n")
            f.flush()
    except Exception as e:
        # Can't even write to log, print to stderr
        print(f"ERROR in early startup: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    try:

        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import (
            PlatformManager,
            PlatformService
        )

        with open(error_log_path, 'a') as f:
            f.write("Imports successful\n")
            f.flush()

        # Create GatewayConfig
        try:
            config = GatewayConfig(
                base_url=gateway_url,
                username=gateway_username,
                password=gateway_password,
                oauth_token=gateway_token,
                verify_ssl=gateway_validate_certs,
                request_timeout=gateway_request_timeout,
                connection_mode='experimental'  # Persistent manager is always experimental mode
            )
            with open(error_log_path, 'a') as f:
                f.write("GatewayConfig created successfully\n")
                f.flush()
        except Exception as config_err:
            with open(error_log_path, 'a') as f:
                f.write(f"GatewayConfig creation failed: {config_err}\n")
                f.write(traceback.format_exc())
                f.flush()
            raise

        # Create service
        try:
            service = PlatformService(config)
            with open(error_log_path, 'a') as f:
                f.write("Service created successfully\n")
                f.flush()
        except Exception as service_err:
            with open(error_log_path, 'a') as f:
                f.write(f"Service creation failed: {service_err}\n")
                f.write(traceback.format_exc())
                f.flush()
            raise

        with open(error_log_path, 'a') as f:
            f.write("Service created\n")
            f.flush()

        # Register with manager (must happen before creating manager instance)
        # Store service in a closure to avoid pickling issues
        _service_ref = [service]

        def _get_service():
            return _service_ref[0]

        PlatformManager.register(
            'get_platform_service',
            callable=_get_service
        )

        with open(error_log_path, 'a') as f:
            f.write("Service registered\n")
            f.flush()

        # Create manager instance (like python-multiproc pattern)
        manager = PlatformManager(address=socket_path, authkey=authkey)

        with open(error_log_path, 'a') as f:
            f.write("Manager instance created\n")
            f.flush()

        # Start manager server
        # Note: We use get_server().serve_forever() instead of manager.start()
        # because manager.start() internally uses multiprocessing which causes issues
        # when we're already in a subprocess
        server = manager.get_server()

        with open(error_log_path, 'a') as f:
            f.write("Server obtained, starting serve_forever()\n")
            f.flush()

        server.serve_forever()

    except Exception as e:
        # Log to a temp file for debugging
        with open(error_log_path, 'a') as f:
            f.write(f"\n\nManager startup failed: {e}\n")
            f.write(traceback.format_exc())
        sys.exit(1)


class BaseResourceActionPlugin(ActionBase):
    """
    Base action plugin for all platform resources.

    Provides common functionality:
    - Manager spawning/connection (_get_or_spawn_manager)
    - Input/output validation (_validate_data)
    - ArgumentSpec generation (_build_argspec_from_docs)

    Subclasses must define:
    - MODULE_NAME: Name of the resource (e.g., 'user', 'organization')
    - DOCUMENTATION: Module documentation string
    - ANSIBLE_DATACLASS: The Ansible dataclass type

    Example subclass:
        class ActionModule(BaseResourceActionPlugin):
            MODULE_NAME = 'user'

            def run(self, tmp=None, task_vars=None):
                # Use inherited methods
                manager = self._get_or_spawn_manager(task_vars)
                # ... implement resource-specific logic
    """

    MODULE_NAME = None  # Subclass must override

    # Class-level tracking of spawned manager processes
    # Key: socket_path, Value: (process, socket_path, authkey_b64)
    _spawned_processes = {}  # type: dict

    # Playbook task tracking: track total tasks and completed tasks per play
    # NOTE: Using file-based tracking for process-safety (works across forks)
    # Class-level dict would not work with Ansible's fork/worker processes

    # Track which manager each task uses
    # Key: task_uuid, Value: socket_path
    _task_to_manager = {}  # type: dict

    def _get_or_spawn_manager(
        self,
        task_vars: dict
    ) -> Tuple[Union['DirectHTTPClient', 'ManagerRPCClient'], Optional[Dict[str, Any]]]:
        """
        Dispatcher: Get connection client from the connection plugin.

        This method delegates to the connection plugin (e.g., 'ansible.platform.http')
        which handles routing between persistent and direct (ephemeral) modes.

        Connection modes (determined by connection plugin):
        - Persistent mode: Returns ManagerRPCClient (long-lived manager process)
        - Direct mode: Returns ManagerRPCClient (ephemeral manager, shut down after task)

        Args:
            task_vars: Task variables from Ansible

        Returns:
            Tuple of (client, facts_dict):
            - client: ManagerRPCClient (persistent or ephemeral)
            - facts_dict: Dict with facts to set (only for persistent mode), None otherwise

        Raises:
            AnsibleError: If gateway URL is missing or connection plugin doesn't support get_client()
            RuntimeError: If manager fails to start
        """
        # Import platform SDK modules
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import (
            extract_gateway_config
        )

        # Extract gateway configuration
        gateway_config = extract_gateway_config(
            task_args=self._task.args,
            host_vars=task_vars,
            required=True
        )

        # DISPATCHER: Delegate to connection plugin's get_client() method
        # The connection plugin handles routing to persistent or ephemeral managers
        try:
            if hasattr(self._connection, 'get_client'):
                logger.debug("Dispatching to connection plugin's get_client() method")
                logger.debug("Connection plugin type: %s", type(self._connection))
                logger.debug("Gateway config: %s", gateway_config)

                client, facts_to_set = self._connection.get_client(task_vars, gateway_config)
                logger.debug("Got client from connection plugin: %s", type(client))
                return client, facts_to_set
            else:
                # Fallback: Connection plugin doesn't implement get_client()
                raise AnsibleError(
                    f"Connection plugin '{self._connection.transport}' does not support 'get_client()' method. "
                    "Ensure you are using 'connection: ansible.platform.http' in your playbook."
                )
        except Exception as e:
            logger.error("Failed in _get_or_spawn_manager dispatcher: %s: %s", type(e).__name__, e)
            import traceback
            tb = traceback.format_exc()
            logger.error("Traceback: %s", tb)

            # Write full traceback to file for debugging
            try:
                with open('/tmp/ansible_platform_error.log', 'w') as f:
                    f.write(f"Error: {type(e).__name__}: {e}\n\n")
                    f.write(f"Full Traceback:\n{tb}\n")
            except OSError:
                pass

            raise

    # NOTE: _get_direct_client() method removed - now handled by connection plugin's get_client()

    def _get_or_spawn_persistent_manager(
        self,
        task_vars: dict,
        gateway_config: Any
    ) -> Tuple['ManagerRPCClient', Optional[Dict[str, Any]]]:
        """
        Get existing persistent manager or spawn new one (experimental mode).

        This is the original persistent manager logic, now only used when
        connection_mode is 'experimental'.

        Args:
            task_vars: Task variables from Ansible
            gateway_config: Gateway configuration

        Returns:
            Tuple of (ManagerRPCClient, facts_dict):
            - ManagerRPCClient: The manager client instance
            - facts_dict: Dict with facts to set (socket, authkey, gateway_url)
              if new manager was spawned, or None if reusing existing manager.
        """
        import sys

        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import (
            ProcessManager
        )
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient

        logger.debug("Using experimental connection mode (Persistent Manager)")

        # Store task_vars for cleanup() method
        self._task_vars = task_vars

        # Initialize playbook task tracking if this is the first task
        self._initialize_playbook_tracking()

        # Check if manager info in hostvars (Ansible-specific)
        hostvars = task_vars.get('hostvars', {})
        inventory_hostname = task_vars.get('inventory_hostname', 'localhost')
        host_vars = hostvars.get(inventory_hostname, {})

        logger.info("Checking for existing persistent manager for host: %s", inventory_hostname)

        # Check both hostvars and top-level task_vars (facts might be in either location)
        socket_path_from_hostvars = host_vars.get('platform_manager_socket')
        socket_path_from_taskvars = task_vars.get('platform_manager_socket')
        socket_path_raw = socket_path_from_hostvars or socket_path_from_taskvars

        # CRITICAL: Convert to plain string explicitly (Fedora/_AnsibleTaggedStr compatibility)
        # BaseManager expects a plain str type, not _AnsibleTaggedStr (which is a str subclass)
        if socket_path_raw is not None:
            socket_path = f"{socket_path_raw}"  # f-string forces plain str
            if not isinstance(socket_path, str):
                socket_path = str(socket_path)
            logger.info("   Found socket path in facts: %s", socket_path)
        else:
            socket_path = None
            logger.info("   No socket path found in facts (will spawn new manager)")

        # Get authkey from facts
        authkey_from_hostvars = host_vars.get('platform_manager_authkey')
        authkey_from_taskvars = task_vars.get('platform_manager_authkey')
        authkey_b64 = authkey_from_hostvars or authkey_from_taskvars

        if authkey_b64:
            logger.info("   Found authkey in facts")
        else:
            logger.info("   No authkey found in facts")

        # Validate socket file if found
        if socket_path:
            socket_file = Path(socket_path)
            socket_exists = socket_file.exists()
            if socket_exists:
                if socket_file.is_socket():
                    logger.info("   ✅ Socket file exists and is valid: %s", socket_path)
                else:
                    logger.warning("   ⚠️  Socket path exists but is not a valid socket: %s", socket_path)
                    socket_exists = False
            else:
                logger.info("   ⚠️  Socket path from facts does not exist: %s", socket_path)
        else:
            socket_exists = False

        # Generate expected socket path based on current credentials
        import tempfile
        socket_dir = Path(tempfile.gettempdir()) / 'ansible_platform'

        # Generate expected connection info with current credentials
        expected_conn_info = ProcessManager.generate_connection_info(
            identifier=inventory_hostname,
            socket_dir=socket_dir,
            gateway_config=gateway_config
        )
        expected_socket_path = expected_conn_info.socket_path
        logger.info("   Expected socket path (for current credentials): %s", expected_socket_path)

        # Check if manager with matching credentials already exists
        manager_found = False
        actual_socket_path = None
        actual_authkey_b64 = None

        if socket_path and authkey_b64:
            stored_path_exists = Path(socket_path).exists()
            if stored_path_exists:
                # Check if stored socket path matches expected (same credentials)
                if socket_path == expected_socket_path:
                    manager_found = True
                    actual_socket_path = socket_path
                    actual_authkey_b64 = authkey_b64
                    logger.info("   ✅ Found existing manager with matching credentials: %s", socket_path)
                else:
                    logger.info("   ⚠️  Credentials changed (socket path mismatch), will spawn new manager")
                    logger.info("      Stored: %s", socket_path)
                    logger.info("      Expected: %s", expected_socket_path)

        # Also check if expected socket path exists (in case facts weren't updated)
        if not manager_found and Path(expected_socket_path).exists() and authkey_b64:
            manager_found = True
            actual_socket_path = expected_socket_path
            actual_authkey_b64 = authkey_b64
            logger.debug("Found manager at expected path: %s", expected_socket_path)

        # If manager already running with matching credentials, try to connect
        if manager_found and actual_socket_path and actual_authkey_b64:
            logger.info("Reusing existing persistent manager (host: %s, gateway: %s)", inventory_hostname, gateway_config.base_url)

            try:
                authkey = base64.b64decode(actual_authkey_b64)

                # CRITICAL: Ensure socket_path is a plain str (Fedora/_AnsibleTaggedStr compatibility)
                actual_socket_path_str = f"{actual_socket_path}"  # f-string forces plain str
                if not isinstance(actual_socket_path_str, str):
                    actual_socket_path_str = str(actual_socket_path_str)

                client = ManagerRPCClient(gateway_config.base_url, actual_socket_path_str, authkey)

                # Track this task's manager
                task_uuid = self._get_task_uuid(task_vars)
                BaseResourceActionPlugin._task_to_manager[task_uuid] = actual_socket_path_str

                # Track this manager in playbook tracking (process-safe)
                play_id = self._get_play_id()
                tracking = self._read_tracking_file(play_id)
                if tracking:
                    if 'socket_paths' in tracking:
                        if isinstance(tracking['socket_paths'], list):
                            tracking['socket_paths'] = set(tracking['socket_paths'])
                        tracking['socket_paths'].add(actual_socket_path_str)
                        self._write_tracking_file(play_id, tracking)

                logger.debug("Successfully connected to existing persistent manager: %s", actual_socket_path_str)

                return client, {
                    'platform_manager_socket': actual_socket_path_str,
                    'platform_manager_authkey': actual_authkey_b64
                }
            except Exception as e:
                logger.warning("Failed to connect to existing manager: %s, spawning new one", e)
                # Fall through to spawn new one

        # Spawn new manager
        logger.info("Spawning new persistent manager (host: %s, gateway: %s)", inventory_hostname, gateway_config.base_url)

        # Generate connection info using platform SDK (with credentials)
        conn_info = ProcessManager.generate_connection_info(
            identifier=inventory_hostname,
            socket_dir=socket_dir,
            gateway_config=gateway_config
        )
        socket_path = conn_info.socket_path
        authkey = conn_info.authkey
        authkey_b64 = conn_info.authkey_b64

        logger.debug("Generated socket path: %s", socket_path)

        # Clean up old socket if exists
        ProcessManager.cleanup_old_socket(socket_path)

        # Capture sys.path from parent to ensure child has same imports
        parent_sys_path = list(sys.path)

        # Get path to manager process script
        script_path = Path(__file__).parent.parent / 'plugin_utils' / 'manager' / 'manager_process.py'

        # Spawn process
        process = ProcessManager.spawn_manager_process(
            script_path=script_path,
            socket_path=socket_path,
            socket_dir=str(socket_dir),
            identifier=inventory_hostname,
            gateway_config=gateway_config,
            authkey_b64=authkey_b64,
            sys_path=parent_sys_path
        )

        logger.info("✅ Manager process spawned successfully")
        logger.info("   Process PID: %s", process.pid)
        logger.info("   Socket Path: %s", socket_path)
        logger.info("   Future tasks with same credentials will reuse this manager")

        # Log where to find manager process logs (for debugging version detection, etc.)
        import tempfile
        socket_dir = Path(tempfile.gettempdir()) / 'ansible_platform'
        error_log = socket_dir / f'manager_error_{inventory_hostname}.log'
        stderr_log = socket_dir / f'manager_stderr_{inventory_hostname}.log'
        logger.info("   📋 Manager process logs (version detection, etc.):")
        logger.info("      - Error log: %s", error_log)
        logger.info("      - Stderr log: %s", stderr_log)

        # Wait for process startup
        ProcessManager.wait_for_process_startup(
            socket_path=socket_path,
            socket_dir=socket_dir,
            identifier=inventory_hostname,
            process=process
        )

        # Verify socket file was created
        socket_file = Path(socket_path)
        if not socket_file.exists():
            raise RuntimeError(f"Manager process started but socket file not found: {socket_path}")

        # CRITICAL: Ensure socket_path is a string (Fedora/Path object compatibility)
        socket_path_str = str(socket_path)

        # Connect to newly spawned manager
        client = ManagerRPCClient(gateway_config.base_url, socket_path_str, authkey)

        # Track this task's manager
        task_uuid = self._get_task_uuid(task_vars)
        BaseResourceActionPlugin._task_to_manager[task_uuid] = socket_path_str

        # Track this manager in playbook tracking (process-safe)
        play_id = self._get_play_id()
        tracking = self._read_tracking_file(play_id)
        if tracking:
            if 'socket_paths' not in tracking:
                tracking['socket_paths'] = set()
            if isinstance(tracking['socket_paths'], list):
                tracking['socket_paths'] = set(tracking['socket_paths'])
            tracking['socket_paths'].add(socket_path_str)
            self._write_tracking_file(play_id, tracking)

        logger.info("✅ Connected to new persistent manager")
        logger.info("   Socket: %s", socket_path_str)
        logger.info("   PID: %s", process.pid)
        logger.info("=" * 80)

        return client, {
            'platform_manager_socket': socket_path_str,
            'platform_manager_authkey': authkey_b64,
            'gateway_url': gateway_config.base_url
        }

    def _build_argspec_from_docs(self, documentation: str) -> dict:
        """
        Build argument spec from DOCUMENTATION string.

        Parses the YAML documentation and merges documentation fragments
        (e.g., ansible.platform.auth) before converting to ArgumentSpec format.

        Args:
            documentation: DOCUMENTATION string from module

        Returns:
            ArgumentSpec dict suitable for ArgumentSpecValidator

        Raises:
            ValueError: If documentation cannot be parsed
        """
        try:
            doc_data = yaml.safe_load(documentation)
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse DOCUMENTATION: {e}") from e

        # Merge fragments first, then module options so module's own options take precedence
        # (e.g. user module state choices merged/replaced/gathered/deleted override fragment's state)
        options = {}
        extends_fragments = doc_data.get('extends_documentation_fragment', [])
        if not isinstance(extends_fragments, list):
            extends_fragments = [extends_fragments]
        for fragment_name in extends_fragments:
            fragment_options = self._load_documentation_fragment(fragment_name)
            if fragment_options:
                options.update(fragment_options)
        options.update(doc_data.get('options', {}))

        # Build argspec in Ansible format
        # ArgumentSpecValidator expects 'argument_spec' key, not 'options'
        argspec = {
            'argument_spec': options,
            'mutually_exclusive': doc_data.get('mutually_exclusive', []),
            'required_together': doc_data.get('required_together', []),
            'required_one_of': doc_data.get('required_one_of', []),
            'required_if': doc_data.get('required_if', []),
        }

        return argspec

    def _load_documentation_fragment(self, fragment_name: str) -> dict:
        """
        Load documentation fragment options.

        Args:
            fragment_name: Fragment name (e.g., 'ansible.platform.auth')

        Returns:
            Dict of options from fragment, or empty dict if not found
        """
        try:
            # Fragment name format: 'ansible.platform.auth' or 'auth'
            if '.' in fragment_name:
                # Full collection path: 'ansible.platform.auth'
                parts = fragment_name.split('.')
                if len(parts) >= 3:
                    collection = '.'.join(parts[:-1])  # 'ansible.platform'
                    fragment = parts[-1]  # 'auth'
                else:
                    fragment = fragment_name
            else:
                # Just fragment name: 'auth'
                fragment = fragment_name

            # Try to load fragment from doc_fragments
            fragment_path = Path(__file__).parent.parent / 'doc_fragments' / f'{fragment}.py'

            if fragment_path.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location(f"doc_fragment_{fragment}", fragment_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Get DOCUMENTATION from ModuleDocFragment class
                    if hasattr(module, 'ModuleDocFragment'):
                        fragment_class = module.ModuleDocFragment
                        fragment_doc = getattr(fragment_class, 'DOCUMENTATION', '')

                        if fragment_doc:
                            fragment_data = yaml.safe_load(fragment_doc)
                            return fragment_data.get('options', {})

            logger.debug("Documentation fragment '%s' not found, skipping", fragment_name)
            return {}

        except Exception as e:
            logger.warning("Failed to load documentation fragment '%s': %s", fragment_name, e)
            return {}

    def _validate_data(
        self,
        data: dict,
        argspec: dict,
        direction: str
    ) -> dict:
        """
        Validate data against argument spec.

        Uses Ansible's built-in ArgumentSpecValidator to validate
        both input (from playbook) and output (from manager).

        Args:
            data: Data dict to validate
            argspec: Argument specification
            direction: 'input' or 'output' (for error messages)

        Returns:
            Validated and normalized data dict

        Raises:
            AnsibleError: If validation fails
        """
        logger.debug("Creating ArgumentSpecValidator with argspec keys: %s", list(argspec.keys()))

        # Create validator - pass all parameters as kwargs
        validator = ArgumentSpecValidator(
            argument_spec=argspec.get('argument_spec', {}),
            mutually_exclusive=argspec.get('mutually_exclusive'),
            required_together=argspec.get('required_together'),
            required_one_of=argspec.get('required_one_of'),
            required_if=argspec.get('required_if'),
            required_by=argspec.get('required_by')
        )

        logger.debug("Validating %s data with keys: %s", direction, list(data.keys()))

        # Validate
        result = validator.validate(data)

        # Check for errors
        if result.error_messages:
            error_msg = (
                f"{direction.title()} validation failed: " +
                ", ".join(result.error_messages)
            )
            raise AnsibleError(error_msg)

        logger.debug("Validation successful for %s", direction)
        return result

    def _get_play_id(self):
        """
        Get unique identifier for current play.

        Uses play name and hosts to create a unique ID.
        """
        task = self._task
        play = getattr(task, '_play', None)
        if play:
            play_name = getattr(play, 'name', None) or 'unknown'
            hosts = getattr(play, 'hosts', [])
            hosts_str = ','.join(str(h) for h in hosts[:3])  # First 3 hosts for uniqueness
            play_id = f"{play_name}::{hosts_str}"
        else:
            play_id = 'unknown_play'
        return play_id

    def _get_task_uuid(self, task_vars):
        """
        Get unique identifier for current task.

        Uses play name, task name, and hostname to create a unique ID.
        """
        task = self._task
        play = getattr(task, '_play', None)
        play_name = getattr(play, 'name', None) or 'unknown'
        task_name = getattr(task, 'name', None) or getattr(task, '_uuid', None) or 'unnamed'
        hostname = task_vars.get('inventory_hostname', 'localhost')
        # Use task's internal UUID if available, otherwise construct one
        task_uuid = getattr(task, '_uuid', None) or f"{play_name}::{task_name}::{hostname}"
        return str(task_uuid)

    def _get_tracking_file_path(self, play_id):
        """
        Get path to tracking file for this play (process-safe).

        Args:
            play_id: Unique play identifier

        Returns:
            Path to tracking file
        """
        import tempfile
        tracking_dir = Path(tempfile.gettempdir()) / 'ansible_platform_tracking'
        tracking_dir.mkdir(exist_ok=True)
        # Sanitize play_id for filename
        safe_play_id = play_id.replace('/', '_').replace(':', '_').replace(' ', '_')
        return tracking_dir / f'playbook_{safe_play_id}.json'

    def _read_tracking_file(self, play_id):
        """
        Read tracking data from file (process-safe with file locking).

        Args:
            play_id: Unique play identifier

        Returns:
            dict with tracking data, or None if file doesn't exist
        """
        file_path = self._get_tracking_file_path(play_id)
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                    try:
                        data = json.load(f)
                        # Convert socket_paths list back to set
                        if 'socket_paths' in data and isinstance(data['socket_paths'], list):
                            data['socket_paths'] = set(data['socket_paths'])
                        return data
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except (IOError, json.JSONDecodeError) as e:
                logger.warning("Error reading tracking file %s: %s", file_path, e)
                return None
        return None

    def _write_tracking_file(self, play_id, data):
        """
        Write tracking data to file (process-safe with file locking).

        Args:
            play_id: Unique play identifier
            data: dict with tracking data
        """
        file_path = self._get_tracking_file_path(play_id)
        try:
            # Convert socket_paths set to list for JSON serialization
            data_copy = data.copy()
            if 'socket_paths' in data_copy and isinstance(data_copy['socket_paths'], set):
                data_copy['socket_paths'] = list(data_copy['socket_paths'])

            with open(file_path, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock for writing
                try:
                    json.dump(data_copy, f, indent=2)
                    f.flush()
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except IOError as e:
            logger.warning("Error writing tracking file %s: %s", file_path, e)

    def _delete_tracking_file(self, play_id):
        """
        Delete tracking file for this play.

        Args:
            play_id: Unique play identifier
        """
        file_path = self._get_tracking_file_path(play_id)
        try:
            if file_path.exists():
                file_path.unlink()
                logger.debug("Deleted tracking file: %s", file_path)
        except Exception as e:
            logger.debug("Could not delete tracking file %s: %s", file_path, e)

    def _initialize_playbook_tracking(self):
        """
        Initialize tracking for the current playbook.

        Counts total tasks in the play (pre_tasks + tasks + post_tasks).
        Only initializes once per play.
        """
        play_id = self._get_play_id()

        # Check if already initialized (process-safe file read)
        existing_tracking = self._read_tracking_file(play_id)
        if existing_tracking is not None:
            logger.debug("Playbook tracking already initialized for play '%s'", play_id)
            return

        # Initialize tracking (process-safe)
        task = self._task
        play = getattr(task, '_play', None)

        total_tasks = 0
        if play:
            # Count tasks in pre_tasks, tasks, and post_tasks
            pre_tasks = getattr(play, 'pre_tasks', []) or []
            tasks = getattr(play, 'tasks', []) or []
            post_tasks = getattr(play, 'post_tasks', []) or []

            # Count all tasks (including tasks in blocks)
            def count_tasks_in_list(task_list):
                count = 0
                for item in task_list:
                    # Check if it's a block
                    if hasattr(item, 'block') and item.block:
                        # Count tasks in block
                        count += count_tasks_in_list(item.block)
                    elif hasattr(item, 'tasks') and item.tasks:
                        # It's a block with tasks attribute
                        count += count_tasks_in_list(item.tasks)
                    else:
                        # It's a regular task
                        count += 1
                return count

            total_tasks = (
                count_tasks_in_list(pre_tasks) +
                count_tasks_in_list(tasks) +
                count_tasks_in_list(post_tasks)
            )

        # Initialize tracking (process-safe file write)
        tracking_data = {
            'total_tasks': total_tasks,
            'completed_tasks': 0,
            'socket_paths': []
        }
        self._write_tracking_file(play_id, tracking_data)

        logger.info(
            "Initialized playbook tracking for play '%s': %s total tasks (file-based, process-safe)",
            play_id, total_tasks
        )

    def cleanup(self, force=False):
        """
        Clean up manager processes when all tasks in playbook complete.

        This method is called by Ansible after EACH task completes.
        - For ephemeral managers (direct mode): Shut down immediately
        - For persistent managers: Track tasks and shutdown when all are done

        Args:
            force: If True, force cleanup even if async is in use
        """
        # Call parent cleanup first
        super().cleanup(force)

        # Import ProcessManager for cleanup
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import (
            ProcessManager
        )

        # Check if we have an ephemeral manager (direct mode) that should be shut down immediately
        if hasattr(self, '_client') and hasattr(self._client, '_ephemeral') and self._client._ephemeral:
            logger.info("Shutting down ephemeral manager (direct mode)")
            try:
                socket_path = getattr(self._client, 'socket_path', None)
                if socket_path:
                    self._shutdown_manager_process(socket_path, ProcessManager)
                    logger.info("Ephemeral manager shut down: %s", socket_path)
            except Exception as e:
                logger.warning("Failed to shutdown ephemeral manager: %s", e)
            # Don't process persistent manager tracking for ephemeral managers
            return

        # Get play ID
        try:
            play_id = self._get_play_id()
        except Exception as e:
            logger.debug("Could not determine play ID for cleanup: %s", e)
            return

        # Read tracking data (process-safe)
        tracking = self._read_tracking_file(play_id)
        if tracking is None:
            logger.debug("Play '%s' not in tracking (may not have platform tasks)", play_id)
            return

        # Increment completed tasks counter (process-safe with file locking)
        # Use atomic read-modify-write pattern
        tracking['completed_tasks'] = tracking.get('completed_tasks', 0) + 1

        total_tasks = tracking.get('total_tasks', 0)
        completed_tasks = tracking['completed_tasks']

        # Convert socket_paths list to set if needed
        if 'socket_paths' in tracking:
            if isinstance(tracking['socket_paths'], list):
                tracking['socket_paths'] = set(tracking['socket_paths'])

        logger.debug(
            "Task completed for play '%s': %s/%s tasks completed (process-safe)",
            play_id, completed_tasks, total_tasks
        )

        # Write updated tracking (process-safe)
        self._write_tracking_file(play_id, tracking)

        # Check if all tasks are done
        if completed_tasks >= total_tasks:
            logger.info(
                "All tasks completed for play '%s' (%s/%s), shutting down manager processes...",
                play_id, completed_tasks, total_tasks
            )

            # Shutdown all managers used by this play
            socket_paths = list(tracking.get('socket_paths', set()))
            for socket_path in socket_paths:
                self._shutdown_manager_process(socket_path, ProcessManager)

            # Clean up tracking file
            self._delete_tracking_file(play_id)
            logger.info("Cleanup complete for play '%s'", play_id)
        else:
            logger.debug(
                "Play '%s' still has %s task(s) remaining, keeping managers alive",
                play_id, total_tasks - completed_tasks
            )

    def _shutdown_manager_process(self, socket_path, ProcessManager):
        """
        Shutdown a specific manager process.

        Args:
            socket_path: Socket path of the manager to shutdown
            ProcessManager: ProcessManager class for cleanup utilities
        """
        process_info = BaseResourceActionPlugin._spawned_processes.get(socket_path)
        if not process_info:
            logger.debug("Manager %s not found in spawned processes", socket_path)
            return

        process = process_info['process']
        authkey_b64 = process_info.get('authkey_b64')

        # Check if process is still running
        if process.poll() is None:
            logger.debug("Manager process still running at %s, shutting down...", socket_path)

            try:
                # Try graceful shutdown via RPC
                if authkey_b64 and Path(socket_path).exists():
                    try:
                        authkey = base64.b64decode(authkey_b64)
                        from .plugin_utils.manager.rpc_client import ManagerRPCClient
                        # CRITICAL: Ensure socket_path is a string (Fedora/Path object compatibility)
                        socket_path_str = str(socket_path)
                        client = ManagerRPCClient(process_info.get('gateway_url', ''), socket_path_str, authkey)
                        # Call shutdown method
                        try:
                            shutdown_result = client.shutdown_manager()
                            logger.debug("Sent shutdown signal to manager at %s: %s", socket_path, shutdown_result)
                        except Exception as e:
                            logger.debug("Shutdown RPC failed (manager may have already shut down): %s", e)
                        finally:
                            client.close()
                    except Exception as e:
                        logger.debug("Could not connect for graceful shutdown: %s", e)

                # Wait for graceful shutdown (max 5 seconds)
                try:
                    process.wait(timeout=5)
                    logger.debug("Manager process at %s shut down gracefully", socket_path)
                except subprocess.TimeoutExpired:
                    logger.warning("Manager process at %s did not shut down gracefully, forcing termination", socket_path)
                    process.terminate()
                    time.sleep(1)
                    if process.poll() is None:
                        process.kill()
                        process.wait()
            except Exception as e:
                logger.warning("Error shutting down manager at %s: %s", socket_path, e)
                # Force kill as fallback
                try:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                except Exception:
                    pass

        # Clean up socket file
        try:
            ProcessManager.cleanup_old_socket(socket_path)
            logger.debug("Cleaned up socket file: %s", socket_path)
        except Exception as e:
            logger.debug("Could not clean up socket file %s: %s", socket_path, e)

        # Remove from tracking
        BaseResourceActionPlugin._spawned_processes.pop(socket_path, None)

    def _detect_operation(self, args: dict) -> str:
        """
        Detect operation type from arguments (CRUD-aligned state).

        Args:
            args: Module arguments

        Returns:
            Operation name ('create', 'update', 'delete', 'find', 'enforced').
            'enforced' is handled by the action plugin (find then merge and create/update).
        """
        state = args.get('state', 'present')

        if state in ('absent', 'deleted'):
            return 'delete'
        elif state == 'present':
            if args.get('id'):
                return 'update'
            return 'create'
        elif state in ('exists', 'find', 'gathered'):
            return 'find'
        elif state in ('enforced', 'merged'):
            return 'enforced'
        else:
            raise AnsibleError(f"Unknown state: {state}")
