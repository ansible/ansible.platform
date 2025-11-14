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
from multiprocessing import Process
import time

logger = logging.getLogger(__name__)


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
        # Import here to avoid circular imports
        from ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient
        
        # Check if manager info in hostvars
        hostvars = task_vars.get('hostvars', {})
        inventory_hostname = task_vars.get('inventory_hostname', 'localhost')
        host_vars = hostvars.get(inventory_hostname, {})
        
        socket_path = host_vars.get('platform_manager_socket')
        authkey_b64 = host_vars.get('platform_manager_authkey')
        gateway_url = host_vars.get('gateway_url') or host_vars.get('gateway_hostname')
        
        # Get auth parameters
        gateway_username = host_vars.get('gateway_username') or host_vars.get('aap_username')
        gateway_password = host_vars.get('gateway_password') or host_vars.get('aap_password')
        gateway_token = host_vars.get('gateway_token') or host_vars.get('aap_token')
        gateway_validate_certs = host_vars.get('gateway_validate_certs', True)
        gateway_request_timeout = host_vars.get('gateway_request_timeout', 10.0)
        
        if not gateway_url:
            raise AnsibleError(
                "gateway_url or gateway_hostname must be defined in inventory or host_vars"
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
        
        # Start manager process
        def start_manager():
            """Manager process entry point."""
            from ansible.platform.plugins.plugin_utils.manager.platform_manager import (
                PlatformManager,
                PlatformService
            )
            
            # Create service
            service = PlatformService(
                base_url=gateway_url,
                username=gateway_username,
                password=gateway_password,
                oauth_token=gateway_token,
                verify_ssl=gateway_validate_certs,
                request_timeout=gateway_request_timeout
            )
            
            # Register with manager
            PlatformManager.register(
                'get_platform_service',
                callable=lambda: service
            )
            
            # Start manager server
            manager = PlatformManager(address=socket_path, authkey=authkey)
            manager.start()
            
            # Keep running
            import signal
            signal.pause()
        
        # Spawn process
        process = Process(target=start_manager, daemon=True)
        process.start()
        
        # Wait for socket to be created
        max_wait = 50  # 5 seconds
        for _ in range(max_wait):
            if Path(socket_path).exists():
                break
            time.sleep(0.1)
        else:
            raise RuntimeError(
                f"Manager failed to start within {max_wait * 0.1} seconds"
            )
        
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
        argspec = {
            'options': options,
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
        # Create validator
        validator = ArgumentSpecValidator(argspec)
        
        # Validate
        result = validator.validate(data)
        
        # Check for errors
        if result.error_messages:
            error_msg = (
                f"{direction.title()} validation failed: " +
                ", ".join(result.error_messages)
            )
            raise AnsibleError(error_msg)
        
        return result.validated_parameters
    
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


