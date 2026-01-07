"""Base action plugin for platform resources.

Provides common functionality inherited by all resource action plugins.
"""

from ansible.plugins.action import ActionBase
from ansible.module_utils.common.arg_spec import ArgumentSpecValidator
from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import (
    PlatformError,
    AuthenticationError,
    ValidationError,
    NetworkError,
    APIError
)
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
import os

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
        
        # Trace playcontext availability
        logger.info("=" * 80)
        logger.info("TRACING PLAYCONTEXT AVAILABILITY")
        logger.info("=" * 80)
        
        # Check if _play_context attribute exists
        has_play_context_attr = hasattr(self, '_play_context')
        logger.info(f"hasattr(self, '_play_context'): {has_play_context_attr}")
        
        if has_play_context_attr:
            play_context = getattr(self, '_play_context', None)
            logger.info(f"self._play_context is not None: {play_context is not None}")
            if play_context is not None:
                logger.info(f"self._play_context type: {type(play_context)}")
                logger.info(f"self._play_context attributes: {dir(play_context)}")
                # Log some common play_context attributes if they exist
                for attr in ['remote_addr', 'remote_user', 'connection', 'become', 'become_user', 'become_method']:
                    if hasattr(play_context, attr):
                        value = getattr(play_context, attr, None)
                        logger.info(f"self._play_context.{attr}: {value}")
        else:
            logger.warning("self._play_context attribute does not exist")
        
        # Check if _play attribute exists (another way play context might be accessed)
        has_play_attr = hasattr(self, '_play')
        logger.info(f"hasattr(self, '_play'): {has_play_attr}")
        if has_play_attr:
            play = getattr(self, '_play', None)
            logger.info(f"self._play is not None: {play is not None}")
            if play is not None:
                logger.info(f"self._play type: {type(play)}")
                logger.info(f"self._play attributes: {dir(play)}")
        
        # Check if _task attribute exists
        has_task_attr = hasattr(self, '_task')
        logger.info(f"hasattr(self, '_task'): {has_task_attr}")
        if has_task_attr:
            task = getattr(self, '_task', None)
            logger.info(f"self._task is not None: {task is not None}")
            if task is not None:
                logger.info(f"self._task type: {type(task)}")
                # Check if task has play_context
                if hasattr(task, '_play_context'):
                    task_play_context = getattr(task, '_play_context', None)
                    logger.info(f"self._task._play_context is not None: {task_play_context is not None}")
                    if task_play_context is not None:
                        logger.info(f"self._task._play_context type: {type(task_play_context)}")
        
        # Check all instance attributes that might contain play context
        logger.info(f"All instance attributes: {[attr for attr in dir(self) if not attr.startswith('__')]}")
        logger.info("=" * 80)
        
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
        logger.info("=" * 80)
        logger.info("SOCKET PATH RETRIEVAL")
        logger.info("=" * 80)
        logger.info(f"Retrieving socket path from facts...")
        logger.info(f"  Checking hostvars['{inventory_hostname}']['platform_manager_socket']...")
        socket_path_from_hostvars = host_vars.get('platform_manager_socket')
        logger.info(f"    Value from hostvars: {socket_path_from_hostvars}")
        logger.info(f"    Type: {type(socket_path_from_hostvars)}")
        
        logger.info(f"  Checking task_vars['platform_manager_socket']...")
        socket_path_from_taskvars = task_vars.get('platform_manager_socket')
        logger.info(f"    Value from task_vars: {socket_path_from_taskvars}")
        logger.info(f"    Type: {type(socket_path_from_taskvars)}")
        
        # Determine which source was used
        socket_path_raw = socket_path_from_hostvars or socket_path_from_taskvars
        socket_path_source = "hostvars" if socket_path_from_hostvars else ("task_vars" if socket_path_from_taskvars else "none")
        
        # CRITICAL: Convert to plain string explicitly (Fedora/_AnsibleTaggedStr compatibility)
        # BaseManager expects a plain str type, not _AnsibleTaggedStr (which is a str subclass)
        # On Fedora, BaseManager.address_type() is strict and rejects subclasses
        if socket_path_raw is not None:
            # Force conversion to plain Python str (not a subclass)
            # Use string slicing or new string creation to ensure plain str type
            socket_path = f"{socket_path_raw}"  # f-string forces plain str
            # Double-check: ensure it's actually a plain str, not a subclass
            if type(socket_path) is not str:
                socket_path = str(socket_path)
            logger.info(f"  Raw socket_path type: {type(socket_path_raw)}")
            logger.info(f"  Converted socket_path type: {type(socket_path)}")
            logger.info(f"  Is plain str (not subclass): {type(socket_path) is str}")
            logger.info(f"  Socket path value: {socket_path}")
        else:
            socket_path = None
        
        logger.info(f"  Selected socket_path: {socket_path}")
        logger.info(f"  Source: {socket_path_source}")
        
        logger.info(f"Retrieving authkey from facts...")
        logger.info(f"  Checking hostvars['{inventory_hostname}']['platform_manager_authkey']...")
        authkey_from_hostvars = host_vars.get('platform_manager_authkey')
        logger.info(f"    Present: {bool(authkey_from_hostvars)}")
        logger.info(f"    Length: {len(authkey_from_hostvars) if authkey_from_hostvars else 0}")
        
        logger.info(f"  Checking task_vars['platform_manager_authkey']...")
        authkey_from_taskvars = task_vars.get('platform_manager_authkey')
        logger.info(f"    Present: {bool(authkey_from_taskvars)}")
        logger.info(f"    Length: {len(authkey_from_taskvars) if authkey_from_taskvars else 0}")
        
        authkey_b64 = authkey_from_hostvars or authkey_from_taskvars
        authkey_source = "hostvars" if authkey_from_hostvars else ("task_vars" if authkey_from_taskvars else "none")
        logger.info(f"  Selected authkey source: {authkey_source}")
        logger.info(f"  Final authkey present: {bool(authkey_b64)}")
        logger.info(f"  Final authkey length: {len(authkey_b64) if authkey_b64 else 0}")
        
        logger.info("=" * 80)
        logger.info("SOCKET FILE VALIDATION")
        logger.info("=" * 80)
        
        if socket_path:
            logger.info(f"Validating socket file: {socket_path}")
            socket_file = Path(socket_path)
            
            # Check if path is absolute
            logger.info(f"  Path is absolute: {socket_file.is_absolute()}")
            logger.info(f"  Path resolved: {socket_file.resolve()}")
            
            # Check if file exists
            socket_exists = socket_file.exists()
            logger.info(f"  File exists: {socket_exists}")
            
            if socket_exists:
                try:
                    stat_info = socket_file.stat()
                    logger.info(f"  File size: {stat_info.st_size} bytes")
                    logger.info(f"  File mode: {oct(stat_info.st_mode)}")
                    logger.info(f"  File UID: {stat_info.st_uid}")
                    logger.info(f"  File GID: {stat_info.st_gid}")
                    logger.info(f"  Modified time: {stat_info.st_mtime}")
                    
                    # Check if it's actually a socket
                    is_socket = socket_file.is_socket()
                    logger.info(f"  Is socket file: {is_socket}")
                    
                    # Check if it's a regular file (stale socket)
                    is_file = socket_file.is_file()
                    logger.info(f"  Is regular file: {is_file}")
                    
                    # Check parent directory
                    parent_dir = socket_file.parent
                    logger.info(f"  Parent directory: {parent_dir}")
                    logger.info(f"  Parent exists: {parent_dir.exists()}")
                    logger.info(f"  Parent is directory: {parent_dir.is_dir()}")
                    if parent_dir.exists():
                        logger.info(f"  Parent permissions: {oct(parent_dir.stat().st_mode)}")
                    
                    # Check if socket is readable/writable
                    logger.info(f"  Socket readable: {os.access(socket_path, os.R_OK)}")
                    logger.info(f"  Socket writable: {os.access(socket_path, os.W_OK)}")
                    
                    if is_socket:
                        logger.info(f"✅ Socket file exists and is a valid Unix socket")
                    elif is_file:
                        logger.warning(f"⚠️  Socket path exists but is a regular file (stale socket?)")
                    else:
                        logger.warning(f"⚠️  Socket path exists but is not a socket or file")
                        
                except OSError as e:
                    logger.error(f"  Error accessing socket file: {e}")
                    logger.error(f"  Error type: {type(e).__name__}")
                    socket_exists = False
            else:
                logger.info(f"  Socket file does not exist")
                # Check if parent directory exists
                parent_dir = socket_file.parent
                logger.info(f"  Parent directory: {parent_dir}")
                logger.info(f"  Parent exists: {parent_dir.exists()}")
                if not parent_dir.exists():
                    logger.warning(f"  ⚠️  Parent directory does not exist - socket cannot be created here")
            
            logger.info(f"✅ Found socket path in facts: {socket_path} (from {socket_path_source})")
        else:
            logger.info("❌ No socket path found in facts")
            logger.info("  Will need to spawn new manager")
        
        logger.info("=" * 80)
        
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
        
        logger.info("=" * 80)
        logger.info("MANAGER PATH VALIDATION AND COMPARISON")
        logger.info("=" * 80)
        logger.info(f"Generating expected socket path based on current credentials...")
        logger.info(f"  Identifier: {inventory_hostname}")
        logger.info(f"  Socket directory: {socket_dir}")
        logger.info(f"  Gateway URL: {gateway_config.base_url}")
        logger.info(f"  Expected socket path: {expected_socket_path}")
        logger.info(f"")
        logger.info(f"Comparing stored vs expected socket paths...")
        logger.info(f"  Stored socket path (from facts): {socket_path}")
        logger.info(f"  Expected socket path (current creds): {expected_socket_path}")
        
        if socket_path:
            paths_match = socket_path == expected_socket_path
            logger.info(f"  Paths match: {paths_match}")
            if not paths_match:
                logger.info(f"  Path difference:")
                logger.info(f"    Stored:    {socket_path}")
                logger.info(f"    Expected: {expected_socket_path}")
                # Show character-by-character comparison if similar
                if len(socket_path) == len(expected_socket_path):
                    diff_chars = [i for i, (a, b) in enumerate(zip(socket_path, expected_socket_path)) if a != b]
                    if diff_chars:
                        logger.info(f"    First difference at position: {diff_chars[0]}")
        else:
            logger.info(f"  Paths match: N/A (no stored path)")
        
        # Check if manager with matching credentials already exists
        # First check the stored socket path (for backward compatibility)
        # Then check the expected socket path (credential-aware)
        manager_found = False
        actual_socket_path = None
        actual_authkey_b64 = None
        
        logger.info("")
        logger.info("Checking stored socket path...")
        if socket_path and authkey_b64:
            stored_path_exists = Path(socket_path).exists()
            logger.info(f"  Stored socket path: {socket_path}")
            logger.info(f"  Authkey present: {bool(authkey_b64)}")
            logger.info(f"  Socket file exists: {stored_path_exists}")
            
            if stored_path_exists:
                # Check if stored socket path matches expected (same credentials)
                if socket_path == expected_socket_path:
                    logger.info(f"  ✅ Stored socket path matches expected path - same credentials")
                    logger.info(f"     This indicates we're reusing the same manager")
                    manager_found = True
                    actual_socket_path = socket_path
                    actual_authkey_b64 = authkey_b64
                else:
                    logger.info("=" * 80)
                    logger.info("⚠️  CREDENTIAL MISMATCH DETECTED")
                    logger.info("=" * 80)
                    logger.info(f"   Stored socket path: {socket_path}")
                    logger.info(f"   Expected socket path: {expected_socket_path}")
                    logger.info(f"   The stored path exists but doesn't match expected path")
                    logger.info(f"   This suggests credentials changed - will spawn new manager")
            else:
                logger.info(f"  ⚠️  Stored socket path in facts but file does not exist")
                logger.info(f"     Manager may have crashed or been cleaned up")
        else:
            if not socket_path:
                logger.info(f"  ❌ No socket path in facts")
            if not authkey_b64:
                logger.info(f"  ❌ No authkey in facts")
        
        # Also check if expected socket path exists (in case facts weren't updated)
        logger.info("")
        logger.info("Checking expected socket path (fallback check)...")
        if not manager_found:
            expected_path_exists = Path(expected_socket_path).exists()
            logger.info(f"  Expected socket path: {expected_socket_path}")
            logger.info(f"  Socket file exists: {expected_path_exists}")
            logger.info(f"  Authkey available: {bool(authkey_b64)}")
            
            if expected_path_exists and authkey_b64:
                logger.info("=" * 80)
                logger.info("✅ FOUND MANAGER AT EXPECTED PATH (facts may not be updated)")
                logger.info("=" * 80)
                logger.info(f"   Expected socket path exists: {expected_socket_path}")
                logger.info(f"   Using stored authkey from facts")
                logger.info(f"   This suggests facts weren't updated but manager is running")
                # Use expected socket path and stored authkey
                manager_found = True
                actual_socket_path = expected_socket_path
                actual_authkey_b64 = authkey_b64
            else:
                if not expected_path_exists:
                    logger.info(f"  ❌ Expected socket path does not exist")
                if not authkey_b64:
                    logger.info(f"  ❌ Authkey not available")
        
        logger.info("=" * 80)
        logger.info(f"Manager reuse decision: {'✅ REUSE EXISTING' if manager_found else '🆕 SPAWN NEW'}")
        logger.info("=" * 80)
        
        # If manager already running with matching credentials, try to connect
        if manager_found and actual_socket_path and actual_authkey_b64:
            logger.info("=" * 80)
            logger.info("🔄 REUSING EXISTING MANAGER")
            logger.info("=" * 80)
            logger.info(f"Manager socket path: {actual_socket_path}")
            logger.info(f"Attempting to connect to existing manager...")
            
            try:
                authkey = base64.b64decode(actual_authkey_b64)
                logger.info(f"Authkey decoded successfully (length: {len(authkey)} bytes)")
                
                # CRITICAL: Ensure socket_path is a plain str (Fedora/_AnsibleTaggedStr compatibility)
                # BaseManager expects a plain str type, not _AnsibleTaggedStr (which is a str subclass)
                # On Fedora, BaseManager.address_type() is strict and rejects subclasses
                # Force conversion to plain Python str using f-string
                actual_socket_path_str = f"{actual_socket_path}"  # f-string forces plain str
                # Double-check: ensure it's actually a plain str, not a subclass
                if type(actual_socket_path_str) is not str:
                    actual_socket_path_str = str(actual_socket_path_str)
                logger.info(f"Socket path type before conversion: {type(actual_socket_path)}")
                logger.info(f"Socket path after conversion: {actual_socket_path_str} (type: {type(actual_socket_path_str)})")
                logger.info(f"Is plain str (not subclass): {type(actual_socket_path_str) is str}")
                
                # Pass plain string to ManagerRPCClient (Fedora compatibility)
                client = ManagerRPCClient(gateway_config.base_url, actual_socket_path_str, authkey)
                
                # Track this task's manager
                task_uuid = self._get_task_uuid(task_vars)
                task_name = getattr(self._task, 'name', 'unknown')
                play_name = getattr(self._play, 'name', 'unknown') if hasattr(self, '_play') else 'unknown'
                
                logger.info("=" * 80)
                logger.info("✅ SUCCESSFULLY CONNECTED TO EXISTING MANAGER")
                logger.info("=" * 80)
                logger.info(f"Task UUID: {task_uuid}")
                logger.info(f"Task name: {task_name}")
                logger.info(f"Play name: {play_name}")
                logger.info(f"Manager socket: {actual_socket_path_str}")
                logger.info(f"Host: {inventory_hostname}")
                logger.info(f"Gateway URL: {gateway_config.base_url}")
                logger.info(f"Task-to-manager mapping: {task_uuid} -> {actual_socket_path_str}")
                
                # Use string version for tracking (ensure consistency)
                BaseResourceActionPlugin._task_to_manager[task_uuid] = actual_socket_path_str
                
                # Log all tasks using this manager
                tasks_using_this_manager = [
                    tid for tid, sock in BaseResourceActionPlugin._task_to_manager.items()
                    if str(sock) == actual_socket_path_str  # Compare as strings
                ]
                logger.info(f"Total tasks using this manager: {len(tasks_using_this_manager)}")
                logger.info(f"Task IDs using this manager: {tasks_using_this_manager}")
                
                # Track this manager in playbook tracking (process-safe)
                play_id = self._get_play_id()
                tracking = self._read_tracking_file(play_id)
                if tracking:
                    if 'socket_paths' in tracking:
                        if isinstance(tracking['socket_paths'], list):
                            tracking['socket_paths'] = set(tracking['socket_paths'])
                        tracking['socket_paths'].add(actual_socket_path_str)  # Store as string
                        self._write_tracking_file(play_id, tracking)
                        logger.info(f"Updated playbook tracking: manager {actual_socket_path_str} registered")
                
                logger.info("=" * 80)
                
                # Return client and updated facts (socket path may have changed)
                # CRITICAL: Return string, not Path object (Fedora compatibility)
                return client, {
                    'platform_manager_socket': actual_socket_path_str,
                    'platform_manager_authkey': actual_authkey_b64
                }
            except Exception as e:
                logger.warning("=" * 80)
                logger.warning("❌ FAILED TO CONNECT TO EXISTING MANAGER")
                logger.warning("=" * 80)
                logger.warning(f"Socket path: {actual_socket_path}")
                logger.warning(f"Error: {e}")
                logger.warning(f"Error type: {type(e).__name__}")
                import traceback
                logger.warning(f"Traceback:\n{traceback.format_exc()}")
                logger.warning("Falling back to spawning new manager...")
                logger.warning("=" * 80)
                # Fall through to spawn new one
        
        # Spawn new manager using platform SDK (generic process management)
        logger.info("=" * 80)
        logger.info("🆕 SPAWNING NEW MANAGER")
        logger.info("=" * 80)
        logger.info(f"Reason: {'No existing manager found' if not manager_found else 'Failed to connect to existing manager'}")
        logger.info(f"Host: {inventory_hostname}")
        logger.info(f"Gateway URL: {gateway_config.base_url}")
        
        # Generate connection info using platform SDK (with credentials)
        conn_info = ProcessManager.generate_connection_info(
            identifier=inventory_hostname,
            socket_dir=socket_dir,
            gateway_config=gateway_config
        )
        socket_path = conn_info.socket_path
        authkey = conn_info.authkey
        authkey_b64 = conn_info.authkey_b64
        
        logger.info(f"Generated new manager connection info:")
        logger.info(f"  Socket path: {socket_path}")
        logger.info(f"  Authkey length: {len(authkey)} bytes")
        logger.info(f"  Authkey (b64): {authkey_b64[:20]}... (truncated)")
        
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
        
        logger.info(f"✅ Manager process spawned successfully")
        logger.info(f"  Process PID: {process.pid}")
        logger.info(f"  Socket path: {socket_path}")
        logger.info(f"  Process returncode: {process.returncode}")
        
        # Wait for process startup using platform SDK (generic)
        logger.info("Waiting for manager process to start and create socket...")
        ProcessManager.wait_for_process_startup(
            socket_path=socket_path,
            socket_dir=socket_dir,
            identifier=inventory_hostname,
            process=process
        )
        
        # Verify socket file was created
        socket_file = Path(socket_path)
        if socket_file.exists():
            logger.info(f"✅ Socket file created successfully")
            logger.info(f"  Socket path: {socket_path}")
            logger.info(f"  Socket file size: {socket_file.stat().st_size} bytes")
            logger.info(f"  Socket file is socket: {socket_file.is_socket()}")
        else:
            logger.error(f"❌ Socket file was not created: {socket_path}")
            raise RuntimeError(f"Manager process started but socket file not found: {socket_path}")
        
        logger.info("Manager process started successfully")
        
        # Connect to newly spawned manager
        logger.info("Connecting to newly spawned manager...")
        
        # CRITICAL: Ensure socket_path is a string (Fedora/Path object compatibility)
        # BaseManager expects a string, not a Path object
        socket_path_str = str(socket_path)
        logger.info(f"Socket path type before conversion: {type(socket_path)}")
        logger.info(f"Socket path after str() conversion: {socket_path_str} (type: {type(socket_path_str)})")
        
        client = ManagerRPCClient(gateway_config.base_url, socket_path_str, authkey)
        
        # Track this task's manager
        task_uuid = self._get_task_uuid(task_vars)
        task_name = getattr(self._task, 'name', 'unknown')
        play_name = getattr(self._play, 'name', 'unknown') if hasattr(self, '_play') else 'unknown'
        
        logger.info("=" * 80)
        logger.info("✅ SUCCESSFULLY SPAWNED AND CONNECTED TO NEW MANAGER")
        logger.info("=" * 80)
        logger.info(f"Task UUID: {task_uuid}")
        logger.info(f"Task name: {task_name}")
        logger.info(f"Play name: {play_name}")
        logger.info(f"Manager socket: {socket_path_str}")
        logger.info(f"Manager PID: {process.pid}")
        logger.info(f"Host: {inventory_hostname}")
        logger.info(f"Gateway URL: {gateway_config.base_url}")
        logger.info(f"Task-to-manager mapping: {task_uuid} -> {socket_path_str}")
        
        # Use string version for tracking (ensure consistency)
        BaseResourceActionPlugin._task_to_manager[task_uuid] = socket_path_str
        
        # Log all tasks using this manager
        tasks_using_this_manager = [
            tid for tid, sock in BaseResourceActionPlugin._task_to_manager.items()
            if str(sock) == socket_path_str  # Compare as strings
        ]
        logger.info(f"Total tasks using this manager: {len(tasks_using_this_manager)}")
        logger.info(f"Task IDs using this manager: {tasks_using_this_manager}")
        
        # Track this manager in playbook tracking (process-safe)
        play_id = self._get_play_id()
        tracking = self._read_tracking_file(play_id)
        if tracking:
            if 'socket_paths' not in tracking:
                tracking['socket_paths'] = set()
            if isinstance(tracking['socket_paths'], list):
                tracking['socket_paths'] = set(tracking['socket_paths'])
            tracking['socket_paths'].add(socket_path_str)  # Store as string
            self._write_tracking_file(play_id, tracking)
            logger.info(f"Updated playbook tracking: manager {socket_path_str} registered")
        
        logger.info("=" * 80)
        
        # Return client and facts to be set (facts will be set in run() method's result)
        # CRITICAL: Return string, not Path object (Fedora compatibility)
        return client, {
            'platform_manager_socket': socket_path_str,
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
