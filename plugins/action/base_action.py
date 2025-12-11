"""Base action plugin for platform resources.

Provides common functionality inherited by all resource action plugins.
"""

from ansible.plugins.action import ActionBase
from ansible.module_utils.common.arg_spec import ArgumentSpecValidator
from ansible.errors import AnsibleError
from ansible.module_utils.six import string_types
from pathlib import Path
import yaml
import logging
import tempfile
import secrets
import base64
import time
import subprocess
import json
import fcntl

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
    
    def _get_or_spawn_manager(self, task_vars: dict):
        """
        Get existing manager or spawn new one.
        
        Also stores task_vars for use in cleanup() method.
        
        Checks if a manager is already running (stored in hostvars).
        If found, connects to it. If not, spawns a new manager process.
        
        This method is Ansible-specific and handles Ansible constructs like
        task_vars, AnsibleError. The actual gateway config extraction and 
        process management are delegated to platform SDK modules.
        
        Args:
            task_vars: Task variables from Ansible
        
        Returns:
            Tuple of (ManagerRPCClient, facts_dict):
            - ManagerRPCClient: The manager client instance
            - facts_dict: Dict with facts to set (socket, authkey, gateway_url) 
              if new manager was spawned, or None if reusing existing manager.
              The caller should set these facts in the result dict with 
              'ansible_facts' key and '_ansible_facts_cacheable': True.
        
        Raises:
            AnsibleError: If gateway URL is missing
            RuntimeError: If manager fails to start
        """
        import sys
        
        # Import platform SDK modules (generic, not Ansible-specific)
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import (
            extract_gateway_config
        )
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import (
            ProcessManager
        )
        
        # Import Ansible-specific modules
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient
        
        # Store task_vars for cleanup() method
        self._task_vars = task_vars
        
        # Initialize playbook task tracking if this is the first task
        self._initialize_playbook_tracking()
        
        # Check if manager info in hostvars (Ansible-specific)
        hostvars = task_vars.get('hostvars', {})
        inventory_hostname = task_vars.get('inventory_hostname', 'localhost')
        host_vars = hostvars.get(inventory_hostname, {})
        
        logger.info(f"Getting or spawning manager for host: {inventory_hostname}")
        logger.debug(f"Host vars keys: {list(host_vars.keys())}")
        logger.debug(f"All task_vars keys: {list(task_vars.keys())}")
        
        # Check both hostvars and top-level task_vars (facts might be in either location)
        socket_path = (
            host_vars.get('platform_manager_socket') or 
            task_vars.get('platform_manager_socket')
        )
        authkey_b64 = (
            host_vars.get('platform_manager_authkey') or 
            task_vars.get('platform_manager_authkey')
        )
        
        if socket_path:
            logger.info(f"Found existing manager socket: {socket_path}")
            logger.debug(f"Authkey present: {bool(authkey_b64)}")
        else:
            logger.info("No existing manager socket found - will spawn new manager")
        
        # Extract gateway configuration using platform SDK (generic)
        try:
            logger.debug("Extracting gateway configuration from task_args and host_vars")
            gateway_config = extract_gateway_config(
                task_args=self._task.args,
                host_vars=host_vars,
                required=True
            )
            logger.info(f"Gateway configuration extracted successfully: {gateway_config.base_url}")
        except ValueError as e:
            logger.error(f"Failed to extract gateway configuration: {e}")
            raise AnsibleError(str(e)) from e
        
        # Generate expected socket path based on current credentials
        # This ensures we check for the correct manager (matching credentials)
        import tempfile
        socket_dir = Path(tempfile.gettempdir()) / 'ansible_platform'
        logger.debug(f"Generating connection info for identifier: {inventory_hostname}, socket_dir: {socket_dir}")
        
        # Generate expected connection info with current credentials
        expected_conn_info = ProcessManager.generate_connection_info(
            identifier=inventory_hostname,
            socket_dir=socket_dir,
            gateway_config=gateway_config
        )
        expected_socket_path = expected_conn_info.socket_path
        
        # Check if manager with matching credentials already exists
        # First check the stored socket path (for backward compatibility)
        # Then check the expected socket path (credential-aware)
        manager_found = False
        actual_socket_path = None
        actual_authkey_b64 = None
        
        if socket_path and authkey_b64 and Path(socket_path).exists():
            # Check if stored socket path matches expected (same credentials)
            if socket_path == expected_socket_path:
                logger.debug(f"Found existing manager with matching credentials: {socket_path}")
                manager_found = True
                actual_socket_path = socket_path
                actual_authkey_b64 = authkey_b64
            else:
                logger.info(
                    f"Stored manager socket path ({socket_path}) doesn't match expected "
                    f"({expected_socket_path}) - credentials may have changed. "
                    f"Will spawn new manager with current credentials."
                )
        
        # Also check if expected socket path exists (in case facts weren't updated)
        if not manager_found and Path(expected_socket_path).exists() and authkey_b64:
            logger.debug(f"Found manager at expected socket path: {expected_socket_path}")
            # Use expected socket path and stored authkey
            manager_found = True
            actual_socket_path = expected_socket_path
            actual_authkey_b64 = authkey_b64
        
        # If manager already running with matching credentials, try to connect
        if manager_found and actual_socket_path and actual_authkey_b64:
            try:
                authkey = base64.b64decode(actual_authkey_b64)
                client = ManagerRPCClient(gateway_config.base_url, actual_socket_path, authkey)
                logger.info("Connected to existing manager with matching credentials")
                
                # Track this task's manager
                task_uuid = self._get_task_uuid(task_vars)
                BaseResourceActionPlugin._task_to_manager[task_uuid] = actual_socket_path
                
                # Track this manager in playbook tracking (process-safe)
                play_id = self._get_play_id()
                tracking = self._read_tracking_file(play_id)
                if tracking:
                    if 'socket_paths' in tracking:
                        if isinstance(tracking['socket_paths'], list):
                            tracking['socket_paths'] = set(tracking['socket_paths'])
                        tracking['socket_paths'].add(actual_socket_path)
                        self._write_tracking_file(play_id, tracking)
                logger.debug(f"Task {task_uuid} using manager {actual_socket_path}")
                
                # Return client and updated facts (socket path may have changed)
                return client, {
                    'platform_manager_socket': actual_socket_path,
                    'platform_manager_authkey': actual_authkey_b64
                }
            except Exception as e:
                logger.warning(
                    f"Failed to connect to existing manager: {e}. "
                    f"Spawning new one..."
                )
                # Fall through to spawn new one
        
        # Spawn new manager using platform SDK (generic process management)
        logger.info("Spawning new Platform Manager")
        
        # Generate connection info using platform SDK (with credentials)
        conn_info = ProcessManager.generate_connection_info(
            identifier=inventory_hostname,
            socket_dir=socket_dir,
            gateway_config=gateway_config
        )
        socket_path = conn_info.socket_path
        authkey = conn_info.authkey
        authkey_b64 = conn_info.authkey_b64
        
        logger.info(f"Connection info generated: socket_path={socket_path}")
        
        # Clean up old socket if exists
        logger.debug(f"Checking for old socket at: {socket_path}")
        ProcessManager.cleanup_old_socket(socket_path)
        
        # Capture sys.path from parent to ensure child has same imports
        parent_sys_path = list(sys.path)
        logger.debug(f"Parent sys.path has {len(parent_sys_path)} entries")
        logger.debug(f"First few entries: {parent_sys_path[:3]}")
        
        # Get path to manager process script
        script_path = Path(__file__).parent.parent / 'plugin_utils' / 'manager' / 'manager_process.py'
        logger.debug(f"Manager process script path: {script_path}")
        
        # Spawn process using platform SDK (generic)
        logger.info("Spawning manager process...")
        process = ProcessManager.spawn_manager_process(
            script_path=script_path,
            socket_path=socket_path,
            socket_dir=str(socket_dir),
            identifier=inventory_hostname,
            gateway_config=gateway_config,
            authkey_b64=authkey_b64,
            sys_path=parent_sys_path
        )
        
        # Wait for process startup using platform SDK (generic)
        logger.info("Waiting for manager process to start...")
        ProcessManager.wait_for_process_startup(
            socket_path=socket_path,
            socket_dir=socket_dir,
            identifier=inventory_hostname,
            process=process
        )
        logger.info("Manager process started successfully")
        
        # Connect to newly spawned manager
        client = ManagerRPCClient(gateway_config.base_url, socket_path, authkey)
        logger.info(f"Spawned and connected to new manager at {socket_path}")
        
        # Track this task's manager
        task_uuid = self._get_task_uuid(task_vars)
        BaseResourceActionPlugin._task_to_manager[task_uuid] = socket_path
        
        # Track this manager in playbook tracking (process-safe)
        play_id = self._get_play_id()
        tracking = self._read_tracking_file(play_id)
        if tracking:
            tracking['socket_paths'].add(socket_path)
            self._write_tracking_file(play_id, tracking)
        logger.debug(f"Task {task_uuid} using manager {socket_path}")
        
        # Return client and facts to be set (facts will be set in run() method's result)
        return client, {
            'platform_manager_socket': socket_path,
            'platform_manager_authkey': authkey_b64,
            'gateway_url': gateway_config.base_url
        }
    
    def _build_argspec_from_docs(self, documentation: str) -> dict:
        """
        Build argument spec from DOCUMENTATION string.
        
        Parses the YAML documentation and converts it to Ansible's
        ArgumentSpec format for validation.
        
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
        
        options = doc_data.get('options', {})
        
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
                        client = ManagerRPCClient(process_info.get('gateway_url', ''), socket_path, authkey)
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


