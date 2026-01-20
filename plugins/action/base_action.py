#!/usr/bin/python
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
import importlib.util
import json
import logging
import os
import secrets
import subprocess
import tempfile
import time
from pathlib import Path

import yaml

from ansible.errors import AnsibleError
from ansible.module_utils.common.arg_spec import ArgumentSpecValidator
from ansible.module_utils.six import string_types
from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import (
    PlatformError,
    AuthenticationError,
    ValidationError,
    NetworkError,
    APIError
)

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

        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import (
            PlatformManager,
            PlatformService
        )

        with open(error_log_path, 'a') as f:
            f.write("Imports successful\n")
            f.flush()

        # Create service
        try:
            service = PlatformService(
                base_url=gateway_url,
                username=gateway_username,
                password=gateway_password,
                oauth_token=gateway_token,
                verify_ssl=gateway_validate_certs,
                request_timeout=gateway_request_timeout
            )
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
    MAX_RETRIES = 1

    def _get_or_spawn_manager(self, task_vars: dict, force_spawn: bool = False):
        """
        Get connection client based on connection mode.

        Also stores task_vars for use in cleanup() method.

        Connection modes:
        - Standard mode (default): Returns DirectHTTPClient (direct HTTP, no persistent process)
        - Experimental mode (opt-in): Returns ManagerRPCClient (persistent manager process)

        This method is Ansible-specific and handles Ansible constructs like
        task_vars, AnsibleError. The actual gateway config extraction and
        process management are delegated to platform SDK modules.

        Args:
            task_vars: Task variables from Ansible
            force_spawn: If True, forces spawning a new manager (ignores existing reuse)

        Returns:
            Tuple of (client, facts_dict):
            - client: DirectHTTPClient (standard) or ManagerRPCClient (experimental)
            - facts_dict: Dict with facts to set (only for experimental mode)
              None for standard mode (no facts needed)

        Raises:
            AnsibleError: If gateway URL is missing
            RuntimeError: If manager fails to start (experimental mode only)
        """
        import sys

        # Import platform SDK modules (generic, not Ansible-specific)
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import (
            extract_gateway_config
        )

        # Extract gateway configuration (includes connection_mode)
        gateway_config = extract_gateway_config(
            task_args=self._task.args,
            host_vars=task_vars,
            required=True
        )

        # Route based on connection mode
        if gateway_config.connection_mode == 'experimental':
            # Experimental mode: Use persistent manager
            return self._get_or_spawn_persistent_manager(task_vars, gateway_config, force_spawn=force_spawn)
        else:
            # Standard mode (default): Use direct HTTP client
            return self._get_direct_client(task_vars, gateway_config)

    def _get_direct_client(self, task_vars: dict, gateway_config):
        """
        Get or create DirectHTTPClient for standard mode.

        Args:
            task_vars: Task variables from Ansible
            gateway_config: Gateway configuration

        Returns:
            Tuple of (DirectHTTPClient, None):
            - DirectHTTPClient: Direct HTTP client instance
            - None: No facts to set (standard mode doesn't need facts)
        """
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient

        logger.info("Using standard connection mode (DirectHTTPClient)")

        # Create direct HTTP client (new instance per task)
        client = DirectHTTPClient(gateway_config)

        logger.info(f"DirectHTTPClient created for {gateway_config.base_url}")

        return client, None

    def _get_or_spawn_persistent_manager(self, task_vars: dict, gateway_config, force_spawn: bool = False):
        """
        Get existing persistent manager or spawn new one (experimental mode).

        This is the original persistent manager logic, now only used when
        connection_mode is 'experimental'.

        Args:
            task_vars: Task variables from Ansible
            gateway_config: Gateway configuration
            force_spawn: Force a fresh process spawn

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

        logger.info("Using experimental connection mode (Persistent Manager)")

        # Store task_vars for cleanup() method
        self._task_vars = task_vars

        # Initialize playbook task tracking if this is the first task
        self._initialize_playbook_tracking()

        # Check if manager info in hostvars (Ansible-specific)
        hostvars = task_vars.get('hostvars', {})
        inventory_hostname = task_vars.get('inventory_hostname', 'localhost')
        host_vars = hostvars.get(inventory_hostname, {})

        logger.info(f"Getting or spawning manager for host: {inventory_hostname}")

        # Check both hostvars and top-level task_vars (facts might be in either location)
        socket_path_from_hostvars = host_vars.get('platform_manager_socket')
        socket_path_from_taskvars = task_vars.get('platform_manager_socket')
        socket_path_raw = socket_path_from_hostvars or socket_path_from_taskvars

        # CRITICAL: Convert to plain string explicitly (Fedora/_AnsibleTaggedStr compatibility)
        # BaseManager expects a plain str type, not _AnsibleTaggedStr (which is a str subclass)
        if socket_path_raw is not None:
            socket_path = f"{socket_path_raw}"  # f-string forces plain str
            if type(socket_path) is not str:
                socket_path = str(socket_path)
        else:
            socket_path = None

        # Get authkey from facts
        authkey_from_hostvars = host_vars.get('platform_manager_authkey')
        authkey_from_taskvars = task_vars.get('platform_manager_authkey')
        authkey_b64 = authkey_from_hostvars or authkey_from_taskvars

        # Validate socket file if found
        if socket_path:
            socket_file = Path(socket_path)
            socket_exists = socket_file.exists()
            if socket_exists and not socket_file.is_socket():
                logger.warning(f"Socket path exists but is not a valid socket: {socket_path}")
                socket_exists = False
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

        # Check if manager with matching credentials already exists
        manager_found = False
        actual_socket_path = None
        actual_authkey_b64 = None

        if not force_spawn and socket_path and authkey_b64:
            stored_path_exists = Path(socket_path).exists()
            if stored_path_exists:
                # Check if stored socket path matches expected (same credentials)
                if socket_path == expected_socket_path:
                    manager_found = True
                    actual_socket_path = socket_path
                    actual_authkey_b64 = authkey_b64
                    logger.info(f"Found existing manager: {socket_path}")
                else:
                    logger.info(f"Credentials changed, will spawn new manager")

        # Also check if expected socket path exists (in case facts weren't updated)
        if not force_spawn and not manager_found and Path(expected_socket_path).exists() and authkey_b64:
            manager_found = True
            actual_socket_path = expected_socket_path
            actual_authkey_b64 = authkey_b64
            logger.info(f"Found manager at expected path: {expected_socket_path}")

        # If manager already running with matching credentials, try to connect
        if manager_found and actual_socket_path and actual_authkey_b64:
            logger.info(f"Connecting to existing manager: {actual_socket_path}")

            try:
                authkey = base64.b64decode(actual_authkey_b64)

                # CRITICAL: Ensure socket_path is a plain str (Fedora/_AnsibleTaggedStr compatibility)
                actual_socket_path_str = f"{actual_socket_path}"  # f-string forces plain str
                if type(actual_socket_path_str) is not str:
                    actual_socket_path_str = str(actual_socket_path_str)

                client = ManagerRPCClient(gateway_config.base_url, actual_socket_path_str, authkey)

                if client.check_health():
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

                    logger.info(f"Connected to existing manager: {actual_socket_path_str}")

                    return client, {
                        'platform_manager_socket': actual_socket_path_str,
                        'platform_manager_authkey': actual_authkey_b64
                    }
                else:
                    logger.warning("Manager connected but failed RPC health check")
            except Exception as e:
                logger.warning(f"Failed to connect to existing manager: {e}, spawning new one")
                # Fall through to spawn new one

        # Spawn new manager
        logger.info(f"Spawning new manager for host: {inventory_hostname}")

        # Generate connection info using platform SDK (with credentials)
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

        logger.info(f"Manager process spawned (PID: {process.pid})")

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

        logger.info(f"Connected to new manager: {socket_path_str} (PID: {process.pid})")

        return client, {
            'platform_manager_socket': socket_path_str,
            'platform_manager_authkey': authkey_b64,
            'gateway_url': gateway_config.base_url
        }
    
    def _handle_exception(self, e):
        result = {'failed': True}
        if isinstance(e, PlatformError):
            result['msg'] = str(e)
            result['error_type'] = e.__class__.__name__
            if hasattr(e, 'status_code') and e.status_code:
                result['status_code'] = e.status_code
            
            if isinstance(e, AuthenticationError): 
                 result['suggestion'] = "Check your gateway_username, gateway_password, or gateway_token."
            elif isinstance(e, ValidationError):
                 result['suggestion'] = "Check your playbook parameters."
            elif isinstance(e, NetworkError):
                 result['suggestion'] = "Check your gateway_hostname and network connectivity."
            elif isinstance(e, APIError):
                 result['suggestion'] = "The Gateway server returned an error. Check Gateway logs or try again later." 
        elif isinstance(e, AnsibleError):
            result['msg'] = str(e)
            result['error_type'] = 'AnsibleError'
        else:
            result['msg'] = f"An unexpected error occurred: {str(e)}"
            result['error_type'] = 'GeneralError'
            import traceback
            result['exception'] = traceback.format_exc()
        return result

    def execute_with_retry(self, manager_client, operation, module_name, data, task_vars):
        """
        Execute an operation with automatic retry on connection failure.
        """
        attempts = 0
        current_client = manager_client
        
        while attempts <= self.MAX_RETRIES:
            try:
                return current_client.execute(operation, module_name, data)
            except (ConnectionError, BrokenPipeError, EOFError) as e:
                attempts += 1
                if attempts > self.MAX_RETRIES:
                    logger.error(f"Max retries ({self.MAX_RETRIES}) reached for operation {operation}")
                    raise e
                logger.warning(f"Connection lost during {operation}. Attempting recovery ({attempts}/{self.MAX_RETRIES})...")
                try:
                    # Retry with force_spawn=True to get a fresh manager
                    new_client, _ = self._get_or_spawn_manager(task_vars, force_spawn=True)
                    current_client = new_client
                    logger.info(f"Recovery successful. Retrying operation...")
                except Exception as spawn_err:
                    logger.error(f"Failed to recover manager: {spawn_err}")
                    raise e

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

        # Start with module's own options
        options = doc_data.get('options', {}).copy()

        # Merge documentation fragments if specified
        extends_fragments = doc_data.get('extends_documentation_fragment', [])
        if not isinstance(extends_fragments, list):
            extends_fragments = [extends_fragments]

        for fragment_name in extends_fragments:
            fragment_options = self._load_documentation_fragment(fragment_name)
            if fragment_options:
                # Merge fragment options into module options
                options.update(fragment_options)

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

            logger.debug(f"Documentation fragment '{fragment_name}' not found, skipping")
            return {}

        except Exception as e:
            logger.warning(f"Failed to load documentation fragment '{fragment_name}': {e}")
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
        logger.debug(f"Creating ArgumentSpecValidator with argspec keys: {list(argspec.keys())}")

        # Create validator - pass all parameters as kwargs
        validator = ArgumentSpecValidator(
            argument_spec=argspec.get('argument_spec', {}),
            mutually_exclusive=argspec.get('mutually_exclusive'),
            required_together=argspec.get('required_together'),
            required_one_of=argspec.get('required_one_of'),
            required_if=argspec.get('required_if'),
            required_by=argspec.get('required_by')
        )

        logger.debug(f"Validating {direction} data with keys: {list(data.keys())}")

        # Validate
        result = validator.validate(data)

        # Check for errors
        if result.error_messages:
            error_msg = (
                f"{direction.title()} validation failed: " +
                ", ".join(result.error_messages)
            )
            raise AnsibleError(error_msg)

        logger.debug(f"Validation successful for {direction}")
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
                logger.warning(f"Error reading tracking file {file_path}: {e}")
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
            logger.warning(f"Error writing tracking file {file_path}: {e}")

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
                logger.debug(f"Deleted tracking file: {file_path}")
        except Exception as e:
            logger.debug(f"Could not delete tracking file {file_path}: {e}")

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
            logger.debug(f"Playbook tracking already initialized for play '{play_id}'")
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
            f"Initialized playbook tracking for play '{play_id}': "
            f"{total_tasks} total tasks (file-based, process-safe)"
        )

    def cleanup(self, force=False):
        """
        Clean up manager processes when all tasks in playbook complete.

        This method is called by Ansible after EACH task completes.
        We track total tasks and completed tasks, and only shutdown when all are done.

        Args:
            force: If True, force cleanup even if async is in use
        """
        # Call parent cleanup first
        super().cleanup(force)

        # Import ProcessManager for cleanup
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import (
            ProcessManager
        )

        # Get play ID
        try:
            play_id = self._get_play_id()
        except Exception as e:
            logger.debug(f"Could not determine play ID for cleanup: {e}")
            return

        # Read tracking data (process-safe)
        tracking = self._read_tracking_file(play_id)
        if tracking is None:
            logger.debug(f"Play '{play_id}' not in tracking (may not have platform tasks)")
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
            f"Task completed for play '{play_id}': "
            f"{completed_tasks}/{total_tasks} tasks completed (process-safe)"
        )

        # Write updated tracking (process-safe)
        self._write_tracking_file(play_id, tracking)

        # Check if all tasks are done
        if completed_tasks >= total_tasks:
            logger.info(
                f"All tasks completed for play '{play_id}' "
                f"({completed_tasks}/{total_tasks}), shutting down manager processes..."
            )

            # Shutdown all managers used by this play
            socket_paths = list(tracking.get('socket_paths', set()))
            for socket_path in socket_paths:
                self._shutdown_manager_process(socket_path, ProcessManager)

            # Clean up tracking file
            self._delete_tracking_file(play_id)
            logger.info(f"Cleanup complete for play '{play_id}'")
        else:
            logger.debug(
                f"Play '{play_id}' still has {total_tasks - completed_tasks} "
                f"task(s) remaining, keeping managers alive"
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
            logger.debug(f"Manager {socket_path} not found in spawned processes")
            return

        process = process_info['process']
        authkey_b64 = process_info.get('authkey_b64')

        # Check if process is still running
        if process.poll() is None:
            logger.debug(f"Manager process still running at {socket_path}, shutting down...")

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
                            logger.debug(f"Sent shutdown signal to manager at {socket_path}: {shutdown_result}")
                        except Exception as e:
                            logger.debug(f"Shutdown RPC failed (manager may have already shut down): {e}")
                        finally:
                            client.close()
                    except Exception as e:
                        logger.debug(f"Could not connect for graceful shutdown: {e}")

                # Wait for graceful shutdown (max 5 seconds)
                try:
                    process.wait(timeout=5)
                    logger.debug(f"Manager process at {socket_path} shut down gracefully")
                except subprocess.TimeoutExpired:
                    logger.warning(f"Manager process at {socket_path} did not shut down gracefully, forcing termination")
                    process.terminate()
                    time.sleep(1)
                    if process.poll() is None:
                        process.kill()
                        process.wait()
            except Exception as e:
                logger.warning(f"Error shutting down manager at {socket_path}: {e}")
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
            logger.debug(f"Cleaned up socket file: {socket_path}")
        except Exception as e:
            logger.debug(f"Could not clean up socket file {socket_path}: {e}")

        # Remove from tracking
        BaseResourceActionPlugin._spawned_processes.pop(socket_path, None)

    def _detect_operation(self, args: dict) -> str:
        """
        Detect operation type from arguments.

        Args:
            args: Module arguments

        Returns:
            Operation name ('create', 'update', 'delete', 'find')
        """
        state = args.get('state', 'present')

        if state == 'absent':
            return 'delete'
        elif state == 'present':
            # Check if ID is provided (update) or not (create)
            if args.get('id'):
                return 'update'
            else:
                return 'create'
        elif state == 'find':
            return 'find'
        else:
            raise AnsibleError(f"Unknown state: {state}")
