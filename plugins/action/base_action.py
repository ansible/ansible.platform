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
    
    def _get_or_spawn_manager(self, task_vars: dict):
        """
        Get existing manager or spawn new one.
        
        Checks if a manager is already running (stored in hostvars).
        If found, connects to it. If not, spawns a new manager process.
        
        Args:
            task_vars: Task variables from Ansible
        
        Returns:
            ManagerRPCClient instance
        
        Raises:
            RuntimeError: If manager fails to start
        """
        import sys
        from multiprocessing import Process
        
        # Import here to avoid circular imports
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient
        
        # Check if manager info in hostvars
        hostvars = task_vars.get('hostvars', {})
        inventory_hostname = task_vars.get('inventory_hostname', 'localhost')
        host_vars = hostvars.get(inventory_hostname, {})
        
        socket_path = host_vars.get('platform_manager_socket')
        authkey_b64 = host_vars.get('platform_manager_authkey')
        
        # Get task arguments (user can pass these per-task or in inventory)
        task_args = self._task.args
        
        # Get gateway URL from task args first, then host_vars
        gateway_url = (
            task_args.get('gateway_url') or 
            task_args.get('gateway_hostname') or
            host_vars.get('gateway_url') or 
            host_vars.get('gateway_hostname')
        )
        
        # Get auth parameters from task args first, then host_vars
        gateway_username = (
            task_args.get('gateway_username') or 
            host_vars.get('gateway_username') or 
            host_vars.get('aap_username')
        )
        gateway_password = (
            task_args.get('gateway_password') or 
            host_vars.get('gateway_password') or 
            host_vars.get('aap_password')
        )
        gateway_token = (
            task_args.get('gateway_token') or 
            host_vars.get('gateway_token') or 
            host_vars.get('aap_token')
        )
        gateway_validate_certs = (
            task_args.get('gateway_validate_certs') 
            if 'gateway_validate_certs' in task_args 
            else host_vars.get('gateway_validate_certs', True)
        )
        gateway_request_timeout = (
            task_args.get('gateway_request_timeout') or 
            host_vars.get('gateway_request_timeout') or 
            10.0
        )
        
        if not gateway_url:
            raise AnsibleError(
                "gateway_url or gateway_hostname must be provided as task parameter or defined in inventory"
            )
        
        # Normalize URL
        if not gateway_url.startswith(('https://', 'http://')):
            gateway_url = f"https://{gateway_url}"
        
        # If manager already running, try to connect
        if socket_path and authkey_b64 and Path(socket_path).exists():
            try:
                authkey = base64.b64decode(authkey_b64)
                client = ManagerRPCClient(gateway_url, socket_path, authkey)
                logger.info("Connected to existing manager")
                return client
            except Exception as e:
                logger.warning(
                    f"Failed to connect to existing manager: {e}. "
                    f"Spawning new one..."
                )
                # Fall through to spawn new one
        
        # Spawn new manager
        logger.info("Spawning new Platform Manager")
        
        # Generate socket path and authkey
        socket_dir = Path(tempfile.gettempdir()) / 'ansible_platform'
        socket_dir.mkdir(exist_ok=True)
        socket_path = str(socket_dir / f'manager_{inventory_hostname}.sock')
        authkey = secrets.token_bytes(32)
        
        # Clean up old socket if exists
        if Path(socket_path).exists():
            try:
                Path(socket_path).unlink()
            except Exception as e:
                logger.warning(f"Failed to remove old socket: {e}")
        
        # Capture sys.path from parent to ensure child has same imports
        parent_sys_path = list(sys.path)
        logger.debug(f"Parent sys.path has {len(parent_sys_path)} entries")
        logger.debug(f"First few entries: {parent_sys_path[:3]}")
        
        # Encode authkey and sys.path for passing as arguments
        authkey_b64 = base64.b64encode(authkey).decode('utf-8')
        import json
        sys_path_json = json.dumps(parent_sys_path)
        sys_path_b64 = base64.b64encode(sys_path_json.encode('utf-8')).decode('utf-8')
        
        # Get path to manager process script
        script_path = Path(__file__).parent.parent / 'plugin_utils' / 'manager' / 'manager_process.py'
        
        # Spawn process using subprocess.Popen (REQUIRED for Ansible plugins on macOS)
        # 
        # Why not multiprocessing.Process?
        # - multiprocessing.Process with spawn imports the entire module (base_action.py)
        # - This includes all Ansible imports which cause crashes on macOS
        # - subprocess.Popen runs a fresh Python interpreter, avoiding import issues
        # - This is the same approach Ansible core uses for similar scenarios
        #
        # Note: We still use BaseManager for RPC communication (that part works fine)
        import subprocess
        import os
        try:
            # Pass sys.path and authkey via environment to avoid arg length limits
            env = os.environ.copy()
            env['ANSIBLE_PLATFORM_SYS_PATH'] = sys_path_b64
            env['ANSIBLE_PLATFORM_AUTHKEY'] = authkey_b64
            
            process = subprocess.Popen(
                [
                    sys.executable,  # Use same Python interpreter
                    str(script_path),
                    socket_path,
                    str(socket_dir),
                    inventory_hostname,
                    gateway_url,
                    gateway_username or '',
                    gateway_password or '',
                    gateway_token or '',
                    str(gateway_validate_certs),
                    str(gateway_request_timeout)
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent
            )
            logger.debug(f"Manager process started with PID: {process.pid}")
        except Exception as e:
            logger.error(f"Failed to start manager process: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise RuntimeError(f"Failed to start manager process: {e}") from e
        
        # Wait for socket to be created
        max_wait = 50  # 5 seconds
        for _ in range(max_wait):
            if Path(socket_path).exists():
                break
            time.sleep(0.1)
        else:
            # Check if there's an error log
            error_log = socket_dir / f'manager_error_{inventory_hostname}.log'
            error_msg = f"Manager failed to start within {max_wait * 0.1} seconds"
            if error_log.exists():
                error_content = error_log.read_text()
                error_msg += f"\n\nManager error log:\n{error_content}"
                error_log.unlink()  # Clean up
            
            # Check if process is still alive (Popen uses poll())
            returncode = process.poll()
            if returncode is not None:
                error_msg += f"\n\nManager process died (exitcode: {returncode})"
            
            raise RuntimeError(error_msg)
        
        # Store info in facts for future tasks
        authkey_b64 = base64.b64encode(authkey).decode('utf-8')
        
        # Set facts so subsequent tasks can reuse this manager
        try:
            self._execute_module(
                module_name='ansible.builtin.set_fact',
                module_args={
                    'platform_manager_socket': socket_path,
                    'platform_manager_authkey': authkey_b64,
                    'gateway_url': gateway_url,
                    'cacheable': True  # Persist across plays
                },
                task_vars=task_vars
            )
        except Exception as e:
            logger.warning(f"Failed to set facts: {e}")
        
        # Connect to newly spawned manager
        client = ManagerRPCClient(gateway_url, socket_path, authkey)
        logger.info(f"Spawned and connected to new manager at {socket_path}")
        
        return client
    
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
        try:
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
            return result.validated_parameters
            
        except Exception as e:
            logger.error(f"Validation error: {e}", exc_info=True)
            raise
    
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


