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
        
        # If manager already running, try to connect
        if socket_path and authkey_b64 and Path(socket_path).exists():
            try:
                authkey = base64.b64decode(authkey_b64)
                client = ManagerRPCClient(gateway_config.base_url, socket_path, authkey)
                logger.info("Connected to existing manager")
                # Return client and None for facts (no new facts to set when reusing)
                return client, None
            except Exception as e:
                logger.warning(
                    f"Failed to connect to existing manager: {e}. "
                    f"Spawning new one..."
                )
                # Fall through to spawn new one
        
        # Spawn new manager using platform SDK (generic process management)
        logger.info("Spawning new Platform Manager")
        
        # Generate connection info using platform SDK
        import tempfile
        socket_dir = Path(tempfile.gettempdir()) / 'ansible_platform'
        logger.debug(f"Generating connection info for identifier: {inventory_hostname}, socket_dir: {socket_dir}")
        
        conn_info = ProcessManager.generate_connection_info(
            identifier=inventory_hostname,
            socket_dir=socket_dir
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


