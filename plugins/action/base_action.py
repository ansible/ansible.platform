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
import importlib
import json
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Union

import yaml
from ansible.errors import AnsibleError
from ansible.module_utils.common.arg_spec import ArgumentSpecValidator
from ansible.plugins.action import ActionBase
from ansible.utils.display import Display

if TYPE_CHECKING:
    from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient
    from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient

# ---------------------------------------------------------------------------
# Logging strategy for action plugins
# ---------------------------------------------------------------------------
# Action plugins always use self._display (Ansible-native) instead of Python's
# logging module.  self._display writes to BOTH the terminal (at the right
# verbosity level) AND ANSIBLE_LOG_PATH unconditionally — so every vv/vvv/vvvv
# call always lands in the log file regardless of how ansible-playbook was run.
#
# Verbosity mapping used throughout this file:
#   self._display.vvvv(msg)    DEBUG   — visible at -vvvv, always in log file
#   self._display.vvv(msg)     INFO    — visible at -vvv,  always in log file
#   self._display.vv(msg)      INFO    — visible at -vv,   always in log file
#   self._display.warning(msg) WARNING — always visible, always in log file
#   self._display.error(msg)   ERROR   — always visible, always in log file
#
# plugin_utils/ modules (which have no self._display) keep using Python's
# logging.getLogger(__name__) — those run in the connection subprocess where
# Ansible correctly wires up the file handler.
# ---------------------------------------------------------------------------
display = Display()


def _manager_process_entry(
    socket_path,
    socket_dir,
    inventory_hostname,
    gateway_url,
    gateway_username,
    gateway_password,
    gateway_token,
    gateway_validate_certs,
    gateway_request_timeout,
    authkey_b64,
    sys_path,
):
    """
    Entry point for the manager process.

    This is a module-level function so it can be pickled for multiprocessing.spawn.
    Uses the same pattern as python-multiproc repository.
    """
    import base64
    import sys
    import traceback
    from pathlib import Path

    # Redirect stderr to a file for debugging
    error_log_path = Path(socket_dir) / f"manager_error_{inventory_hostname}.log"
    stderr_log = Path(socket_dir) / f"manager_stderr_{inventory_hostname}.log"

    try:
        sys.stderr = open(stderr_log, "w", buffering=1)
        sys.stdout = open(stderr_log, "a", buffering=1)
    except Exception:
        pass  # Continue without redirecting

    try:
        # Restore parent's sys.path in child process (spawn starts fresh)
        sys.path = sys_path

        # Decode authkey from base64 string
        authkey = base64.b64decode(authkey_b64.encode("utf-8"))

        # Write to log immediately to capture any early failures
        with open(error_log_path, "w") as f:
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
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformManager, PlatformService
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig

        with open(error_log_path, "a") as f:
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
                connection_mode="experimental",  # Persistent manager is always experimental mode
            )
            with open(error_log_path, "a") as f:
                f.write("GatewayConfig created successfully\n")
                f.flush()
        except Exception as config_err:
            with open(error_log_path, "a") as f:
                f.write(f"GatewayConfig creation failed: {config_err}\n")
                f.write(traceback.format_exc())
                f.flush()
            raise

        # Create service
        try:
            service = PlatformService(config)
            with open(error_log_path, "a") as f:
                f.write("Service created successfully\n")
                f.flush()
        except Exception as service_err:
            with open(error_log_path, "a") as f:
                f.write(f"Service creation failed: {service_err}\n")
                f.write(traceback.format_exc())
                f.flush()
            raise

        with open(error_log_path, "a") as f:
            f.write("Service created\n")
            f.flush()

        # Register with manager (must happen before creating manager instance)
        # Store service in a closure to avoid pickling issues
        _service_ref = [service]

        def _get_service():
            return _service_ref[0]

        PlatformManager.register("get_platform_service", callable=_get_service)

        with open(error_log_path, "a") as f:
            f.write("Service registered\n")
            f.flush()

        # Create manager instance (like python-multiproc pattern)
        manager = PlatformManager(address=socket_path, authkey=authkey)

        with open(error_log_path, "a") as f:
            f.write("Manager instance created\n")
            f.flush()

        # Start manager server
        # Note: We use get_server().serve_forever() instead of manager.start()
        # because manager.start() internally uses multiprocessing which causes issues
        # when we're already in a subprocess
        server = manager.get_server()

        with open(error_log_path, "a") as f:
            f.write("Server obtained, starting serve_forever()\n")
            f.flush()

        server.serve_forever()

    except Exception as e:
        # Log to a temp file for debugging
        with open(error_log_path, "a") as f:
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

    # Action plugins in ansible.platform always target localhost (Gateway is
    # an HTTP API, connection is always local).  Ansible's fork-based async
    # mechanism writes job-status files on the managed node; because the
    # managed node IS the controller here, async_status can poll those files
    # correctly.  Setting this to True restores the async: / poll: 0 behaviour
    # that infra.aap_configuration gateway roles depend on.
    _supports_async = True

    # -----------------------------------------------------------------
    # Declarative class variables: set these in a subclass to get a
    # fully-working action plugin without overriding run().
    #
    #   MODEL_CLASS   – the AnsibleXxx dataclass for this resource
    #   LOOKUP_FIELD  – field used for existence checks (default 'name')
    #
    # Example:
    #   class ActionModule(BaseResourceActionPlugin):
    #       MODULE_NAME  = 'service'
    #       MODEL_CLASS  = AnsibleService
    #       LOOKUP_FIELD = 'name'   # optional; 'name' is the default
    # -----------------------------------------------------------------
    MODEL_CLASS = None  # type: Optional[type]
    LOOKUP_FIELD = "name"

    # Shared constants used by the standard run() and concrete subclasses
    # Fields that are sent TO the API as operation directives but never returned
    # by GET/LIST responses.  Including them in idempotency comparisons always
    # produces false positives because find_result will have None for them while
    # the task may supply a concrete value (e.g. mark_previous_inactive=False).
    # Subclasses should override this with module-specific write-only fields.
    _WRITE_ONLY_FIELDS: frozenset = frozenset()

    # API-generated fields returned flat only (not in nested dict, not round-trip safe as input).
    # Subclasses override with module-specific fields.
    _EXTRA_RETURN_FIELDS: frozenset = frozenset()

    # Fields the API stores as space-separated strings but argument_spec declares as list.
    # Conversion is applied in the output layer only so the internal update path is unaffected.
    # Subclasses override with module-specific fields.
    _SPACE_SEPARATED_LIST_FIELDS: frozenset = frozenset()

    # Deprecated argspec fields: {field_name: (warning_message, version_removed)}.
    # Populated from validated_params, warned, and stripped before MODEL_CLASS is built.
    _DEPRECATED_FIELDS: dict = {}

    # FK fields whose values CAN change via an update operation.  For these
    # fields the case-3 skip in _should_update() (non-digit name string vs
    # digit string from from_api()) is suppressed so that a name change like
    # service_cluster='eda' vs current '3' actually triggers the update path.
    # Without this, the skip would mask genuine FK changes.
    # Subclasses override this to list mutable FK fields for their resource.
    _MUTABLE_FK_FIELDS: frozenset = frozenset()

    _AUTH_PARAMS = frozenset(
        {
            "gateway_hostname",
            "gateway_username",
            "gateway_password",
            "gateway_token",
            "gateway_validate_certs",
            "gateway_request_timeout",
            "aap_hostname",
            "aap_username",
            "aap_password",
            "aap_token",
            "aap_validate_certs",
            "aap_request_timeout",
        }
    )
    _ANSIBLE_DIRECTIVES = frozenset({"state", "new_name"})
    _READ_ONLY_FIELDS = frozenset({"id", "created", "modified", "url"})

    # Class-level tracking of spawned manager processes
    # Key: socket_path, Value: (process, socket_path, authkey_b64)
    _spawned_processes = {}  # type: dict

    # Playbook task tracking: track total tasks and completed tasks per play
    # NOTE: Using file-based tracking for process-safety (works across forks)
    # Class-level dict would not work with Ansible's fork/worker processes

    # Track which manager each task uses
    # Key: task_uuid, Value: socket_path
    _task_to_manager = {}  # type: dict

    # ------------------------------------------------------------------
    # Subclass extension hooks
    # Override these in a subclass to customise run() behaviour without
    # duplicating the full pipeline.
    # ------------------------------------------------------------------

    def _resolve_lookup(self, resource: Any, resource_data: dict, validated_params: dict) -> None:
        """Called after MODEL_CLASS is instantiated.

        Override to mutate *resource* and *resource_data* in place —
        for example, to treat a numeric lookup-field value as an ID.
        Default: no-op.

        Args:
            resource: The MODEL_CLASS instance just built.
            resource_data: The filtered dict used to build *resource*.
            validated_params: Full validated input parameters.
        """

    def _build_ansible_data(self, resource: Any, validated_params: dict, operation: str) -> dict:
        """Build the ansible_data dict that is sent to manager.execute().

        The default uses ``asdict(resource)`` which includes every dataclass
        field.  Override when only the explicitly-provided task fields should
        be forwarded (e.g. to avoid sending dataclass defaults that overwrite
        server-side values).

        Args:
            resource: The MODEL_CLASS instance.
            validated_params: Full validated input parameters.
            operation: The resolved operation string (create/update/delete/find).

        Returns:
            dict: Data to pass as ``ansible_data`` to manager.execute().
        """
        from dataclasses import asdict

        return asdict(resource)

    def _pre_execute_hook(self, ansible_data: dict, write_only_data: dict, validated_params: dict, operation: str) -> None:
        """Called immediately before the final manager.execute() call.

        Override to mutate *ansible_data* in place — for example, to
        conditionally strip write-only fields based on other parameters.
        Default: no-op.

        Args:
            ansible_data: The dict about to be sent to manager.execute().
            write_only_data: Fields that were popped from resource_data
                because they are in _WRITE_ONLY_FIELDS (not part of MODEL_CLASS).
            validated_params: Full validated input parameters.
            operation: The resolved operation string.
        """

    def _get_or_spawn_manager(self, task_vars: dict) -> Tuple[Union["DirectHTTPClient", "ManagerRPCClient"], Optional[Dict[str, Any]]]:
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
            Tuple[Union[DirectHTTPClient, ManagerRPCClient], Optional[Dict[str, Any]]]:
            (client, facts_dict) where client is ManagerRPCClient (persistent or
            ephemeral) and facts_dict contains facts to set for persistent mode
            (None for direct mode).

        Raises:
            AnsibleError: If gateway URL is missing or connection plugin doesn't support get_client()
            RuntimeError: If manager fails to start
        """
        # Import platform SDK modules
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import extract_gateway_config

        # Extract gateway configuration
        gateway_config = extract_gateway_config(task_args=self._task.args, host_vars=task_vars, required=True)

        # Collect task-level environment vars (e.g. SSL_CERT_FILE, REQUESTS_CA_BUNDLE, proxy
        # settings) BEFORE dispatching so they can be forwarded to the manager subprocess
        # regardless of which connection mode is in use (local, http-direct, http-persistent).
        task_env: dict = {}
        for _env_block in self._task.environment or []:
            if isinstance(_env_block, dict):
                try:
                    _resolved = self._templar.template(_env_block)
                    if isinstance(_resolved, dict):
                        task_env.update(_resolved)
                except Exception as _env_err:
                    self._display.vvvv(f"Could not resolve task environment block: {_env_err}")
        if task_env:
            self._display.vvvv(f"Forwarding {len(task_env)} task-level env var(s) to manager: {list(task_env.keys())}")

        # DISPATCHER: Delegate to connection plugin's get_client() when available;
        # otherwise support connection: local by spawning an ephemeral manager.
        try:
            if hasattr(self._connection, "get_client"):
                self._display.vvvv(f"Dispatching to connection plugin get_client() (type={type(self._connection).__name__})")

                client, facts_to_set = self._connection.get_client(task_vars, gateway_config, task_env=task_env or None)
                self._display.vvvv(f"Got client from connection plugin: {type(client).__name__}")
                return client, facts_to_set
            else:
                # Fallback: connection is local (or other) — spawn ephemeral manager so tasks still work
                self._display.vv(
                    f"Connection '{self._connection.transport}' has no get_client(); using ephemeral manager. "
                    "Set 'connection: ansible.platform.http' for persistent mode."
                )
                from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import spawn_ephemeral_client

                client, facts_to_set = spawn_ephemeral_client(task_vars, gateway_config, task_env=task_env or None)
                return client, facts_to_set
        except Exception as e:
            import traceback

            tb = traceback.format_exc()
            self._display.error(f"Failed in _get_or_spawn_manager dispatcher: {type(e).__name__}: {e}")
            self._display.error(f"Traceback: {tb}")

            # Write full traceback to file for debugging
            try:
                with open("/tmp/ansible_platform_error.log", "w") as f:
                    f.write(f"Error: {type(e).__name__}: {e}\n\n")
                    f.write(f"Full Traceback:\n{tb}\n")
            except OSError:
                pass

            raise

    # NOTE: _get_direct_client() method removed - now handled by connection plugin's get_client()

    def _get_or_spawn_persistent_manager(self, task_vars: dict, gateway_config: Any) -> Tuple["ManagerRPCClient", Optional[Dict[str, Any]]]:
        """
        Get existing persistent manager or spawn new one (experimental mode).

        This is the original persistent manager logic, now only used when
        connection_mode is 'experimental'.

        Args:
            task_vars: Task variables from Ansible
            gateway_config: Gateway configuration

        Returns:
            Tuple[ManagerRPCClient, Optional[Dict[str, Any]]]:
            (client, facts_dict) where client is the ManagerRPCClient instance and
            facts_dict contains socket/authkey/gateway_url facts if a new manager
            was spawned, or None if reusing an existing manager.
        """
        import sys

        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import ProcessManager
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient

        self._display.vvvv("Using experimental connection mode (Persistent Manager)")

        inventory_hostname = task_vars.get("inventory_hostname", "localhost")

        self._display.vvvv(f"Checking for existing persistent manager for host: {inventory_hostname}")

        # Determine the expected socket path for the current credentials.
        # The socket filename encodes a credential hash, so a credential
        # change automatically causes a new manager to be spawned.
        import tempfile

        socket_dir = Path(tempfile.gettempdir()) / "ansible_platform"
        expected_conn_info = ProcessManager.generate_connection_info(identifier=inventory_hostname, socket_dir=socket_dir, gateway_config=gateway_config)
        expected_socket_path = expected_conn_info.socket_path
        meta_path = expected_socket_path + ".meta"

        self._display.vvvv(f"Expected socket path: {expected_socket_path}")

        # Discover an existing manager via its companion .meta file.
        # This replaces the old hostvars/ansible_facts approach so that
        # secrets are never surfaced in the task result.
        manager_found = False
        actual_authkey_b64 = None

        if Path(expected_socket_path).exists() and Path(meta_path).exists():
            try:
                with open(meta_path, "r") as _mf:
                    _meta = json.load(_mf)
                candidate_authkey = _meta.get("authkey_b64")
                if candidate_authkey and Path(expected_socket_path).is_socket():
                    manager_found = True
                    actual_authkey_b64 = candidate_authkey
                    self._display.vvvv(f"Found existing manager via meta file: {expected_socket_path}")
                else:
                    self._display.vvvv("Meta file present but socket invalid — will re-spawn")
            except Exception as _e:
                self._display.vvvv(f"Could not read meta file {meta_path}: {_e} — will spawn new manager")

        # Reuse existing manager if found.
        if manager_found and actual_authkey_b64:
            self._display.vv(f"Reusing existing persistent manager (host={inventory_hostname}, gateway={gateway_config.base_url})")
            try:
                authkey = base64.b64decode(actual_authkey_b64)
                client = ManagerRPCClient(gateway_config.base_url, str(expected_socket_path), authkey)
                self._display.vvvv(f"Connected to existing persistent manager: {expected_socket_path}")
                # Return None for facts — nothing secret goes into the result
                return client, None
            except Exception as e:
                self._display.warning(f"Failed to connect to existing manager: {e} — spawning new one")

        # Spawn new manager — reuse the connection info already generated above
        self._display.vv(f"Spawning new persistent manager (host={inventory_hostname}, gateway={gateway_config.base_url})")

        socket_path = expected_conn_info.socket_path
        authkey = expected_conn_info.authkey
        authkey_b64 = expected_conn_info.authkey_b64

        self._display.vvvv(f"Generated socket path: {socket_path}")

        # Clean up old socket if exists
        ProcessManager.cleanup_old_socket(socket_path)

        # Capture sys.path from parent to ensure child has same imports
        parent_sys_path = list(sys.path)

        # Get path to manager process script
        script_path = Path(__file__).parent.parent / "plugin_utils" / "manager" / "manager_process.py"

        # Spawn process.
        # Pass os.getppid() as owner_pid — action plugins run in forked workers,
        # so os.getppid() is the main ansible-playbook process PID.  The manager's
        # watchdog thread watches that PID and self-terminates when it exits.
        import os as _os_spawn

        # Resolve and forward task-level env vars to the persistent manager subprocess.
        _persistent_task_env: dict = {}
        for _env_block in self._task.environment or []:
            if isinstance(_env_block, dict):
                try:
                    _resolved = self._templar.template(_env_block)
                    if isinstance(_resolved, dict):
                        _persistent_task_env.update(_resolved)
                except Exception as _env_err:
                    self._display.vvvv(f"Could not resolve task environment block: {_env_err}")

        process = ProcessManager.spawn_manager_process(
            script_path=script_path,
            socket_path=socket_path,
            socket_dir=str(socket_dir),
            identifier=inventory_hostname,
            gateway_config=gateway_config,
            authkey_b64=authkey_b64,
            sys_path=parent_sys_path,
            owner_pid=_os_spawn.getppid(),
            task_env=_persistent_task_env or None,
        )

        self._display.vv(f"Manager process spawned (pid={process.pid}, socket={socket_path})")
        self._display.vvvv(
            f"Manager logs: "
            f"error_log={socket_dir / f'manager_error_{inventory_hostname}.log'} "
            f"stderr_log={socket_dir / f'manager_stderr_{inventory_hostname}.log'}"
        )

        # Wait for process startup
        ProcessManager.wait_for_process_startup(socket_path=socket_path, socket_dir=socket_dir, identifier=inventory_hostname, process=process)

        # Verify socket file was created
        socket_file = Path(socket_path)
        if not socket_file.exists():
            raise RuntimeError(f"Manager process started but socket file not found: {socket_path}")

        # CRITICAL: Ensure socket_path is a string (Fedora/Path object compatibility)
        socket_path_str = str(socket_path)

        # Connect to newly spawned manager
        client = ManagerRPCClient(gateway_config.base_url, socket_path_str, authkey)

        # Track this task's manager
        self._display.vv(f"Connected to new persistent manager (socket={socket_path_str}, pid={process.pid})")

        # Write a companion .meta file so the callback plugin (and any other
        # process that didn't spawn the manager) can shut it down cleanly.
        # Secrets never flow through ansible_facts — the meta file is the
        # single source of truth for the authkey and PID.
        meta_path = socket_path_str + ".meta"
        try:
            with open(meta_path, "w") as _mf:
                json.dump({"pid": process.pid, "authkey_b64": authkey_b64, "gateway_url": gateway_config.base_url}, _mf)
            self._display.vvvv(f"Wrote manager meta file: {meta_path}")
        except Exception as _e:
            self._display.vvvv(f"Could not write manager meta file {meta_path}: {_e}")

        # Return None for facts — nothing secret goes into the task result
        return client, None

    def _get_documentation(self) -> str:
        """Auto-discover DOCUMENTATION from the sibling modules/ package.

        Uses MODULE_NAME to import plugins.modules.<MODULE_NAME> and return
        its DOCUMENTATION attribute. Same approach as cisco.meraki_rm.
        """
        if not self.MODULE_NAME:
            return ""
        parent_pkg = type(self).__module__.rsplit(".", 2)[0]  # ...plugins
        for candidate in (
            f"{parent_pkg}.modules.{self.MODULE_NAME}",
            f"ansible_collections.ansible.platform.plugins.modules.{self.MODULE_NAME}",
        ):
            try:
                mod = importlib.import_module(candidate)
                doc = getattr(mod, "DOCUMENTATION", None)
                if doc:
                    return doc
            except (ImportError, ModuleNotFoundError):
                continue
        return ""

    def _build_argspec_from_docs(self, documentation: str) -> dict:
        """
        Build argument spec from DOCUMENTATION string.

        Parses the YAML documentation and merges documentation fragments
        (e.g., ansible.platform.auth) before converting to ArgumentSpec format.

        Args:
            documentation: DOCUMENTATION string from module

        Returns:
            dict: ArgumentSpec dict suitable for ArgumentSpecValidator

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
        extends_fragments = doc_data.get("extends_documentation_fragment", [])
        if not isinstance(extends_fragments, list):
            extends_fragments = [extends_fragments]
        for fragment_name in extends_fragments:
            fragment_options = self._load_documentation_fragment(fragment_name)
            if fragment_options:
                options.update(fragment_options)
        options.update(doc_data.get("options", {}))

        # Build argspec in Ansible format
        # ArgumentSpecValidator expects 'argument_spec' key, not 'options'
        argspec = {
            "argument_spec": options,
            "mutually_exclusive": doc_data.get("mutually_exclusive", []),
            "required_together": doc_data.get("required_together", []),
            "required_one_of": doc_data.get("required_one_of", []),
            "required_if": doc_data.get("required_if", []),
        }

        return argspec

    def _load_documentation_fragment(self, fragment_name: str) -> dict:
        """
        Load documentation fragment options.

        Args:
            fragment_name: Fragment name (e.g., 'ansible.platform.auth')

        Returns:
            dict: Options from fragment, or empty dict if not found
        """
        try:
            # Fragment name format: 'ansible.platform.auth' or 'auth'
            if "." in fragment_name:
                # Full collection path: 'ansible.platform.auth'
                parts = fragment_name.split(".")
                if len(parts) >= 3:
                    _collection = ".".join(parts[:-1])  # 'ansible.platform'
                    fragment = parts[-1]  # 'auth'
                else:
                    fragment = fragment_name
            else:
                # Just fragment name: 'auth'
                fragment = fragment_name

            # Try to load fragment from doc_fragments
            fragment_path = Path(__file__).parent.parent / "doc_fragments" / f"{fragment}.py"

            if fragment_path.exists():
                import importlib.util

                spec = importlib.util.spec_from_file_location(f"doc_fragment_{fragment}", fragment_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Get DOCUMENTATION from ModuleDocFragment class
                    if hasattr(module, "ModuleDocFragment"):
                        fragment_class = module.ModuleDocFragment
                        fragment_doc = getattr(fragment_class, "DOCUMENTATION", "")

                        if fragment_doc:
                            fragment_data = yaml.safe_load(fragment_doc)
                            return fragment_data.get("options", {})

            self._display.vvvv(f"Documentation fragment '{fragment_name}' not found, skipping")
            return {}

        except Exception as e:
            self._display.warning(f"Failed to load documentation fragment '{fragment_name}': {e}")
            return {}

    def _validate_data(self, data: dict, argspec: dict, direction: str) -> Any:
        """
        Validate data against argument spec.

        Uses Ansible's built-in ArgumentSpecValidator to validate
        both input (from playbook) and output (from manager).

        Args:
            data: Data dict to validate
            argspec: Argument specification
            direction: 'input' or 'output' (for error messages)

        Returns:
            Any: ValidationResult with validated_parameters and error_messages

        Raises:
            AnsibleError: If validation fails
        """
        arg_spec_dict = argspec.get("argument_spec", {})
        _numeric_types = {"float", "int"}
        for _param, _spec in arg_spec_dict.items():
            if _spec.get("type") in _numeric_types:
                if data.get(_param) == "":
                    data.pop(_param, None)
                for _alias in _spec.get("aliases", []):
                    if data.get(_alias) == "":
                        data.pop(_alias, None)

        self._display.vvvv(f"Creating ArgumentSpecValidator with argspec keys: {list(argspec.keys())}")

        # Create validator - pass all parameters as kwargs
        validator = ArgumentSpecValidator(
            argument_spec=argspec.get("argument_spec", {}),
            mutually_exclusive=argspec.get("mutually_exclusive"),
            required_together=argspec.get("required_together"),
            required_one_of=argspec.get("required_one_of"),
            required_if=argspec.get("required_if"),
            required_by=argspec.get("required_by"),
        )

        self._display.vvvv(f"Validating {direction} data with keys: {list(data.keys())}")

        # Validate
        result = validator.validate(data)

        # Check for errors
        if result.error_messages:
            error_msg = f"{direction.title()} validation failed: " + ", ".join(result.error_messages)
            raise AnsibleError(error_msg)

        self._display.vvvv(f"Validation successful for {direction}")
        return result

    def _get_play_id(self):
        """
        Get unique identifier for current play.

        Uses play name and hosts to create a unique ID.
        """
        task = self._task
        play = getattr(task, "_play", None)
        if play:
            play_name = getattr(play, "name", None) or "unknown"
            hosts = getattr(play, "hosts", [])
            hosts_str = ",".join(str(h) for h in hosts[:3])  # First 3 hosts for uniqueness
            play_id = f"{play_name}::{hosts_str}"
        else:
            play_id = "unknown_play"
        return play_id

    def _get_task_uuid(self, task_vars):
        """
        Get unique identifier for current task.

        Uses play name, task name, and hostname to create a unique ID.
        """
        task = self._task
        play = getattr(task, "_play", None)
        play_name = getattr(play, "name", None) or "unknown"
        task_name = getattr(task, "name", None) or getattr(task, "_uuid", None) or "unnamed"
        hostname = task_vars.get("inventory_hostname", "localhost")
        # Use task's internal UUID if available, otherwise construct one
        task_uuid = getattr(task, "_uuid", None) or f"{play_name}::{task_name}::{hostname}"
        return str(task_uuid)

    def cleanup(self, force: bool = False) -> None:
        """
        Called by Ansible after each task completes.

        Persistent managers are shut down by the platform_manager_cleanup
        callback plugin which fires v2_playbook_on_play_end in the main
        process — no task counting or file locking needed here.

        This method only handles ephemeral managers (direct mode), which
        must be torn down immediately after the single task that used them.
        """
        super().cleanup(force)

        # Ephemeral managers (direct / non-persistent mode): shut down now.
        if hasattr(self, "_client") and getattr(self._client, "_ephemeral", False):
            self._display.vv("Shutting down ephemeral manager (direct mode)")
            try:
                from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import ProcessManager

                socket_path = getattr(self._client, "socket_path", None)
                if socket_path:
                    self._shutdown_manager_process(socket_path, ProcessManager)
            except Exception as e:
                self._display.warning(f"Failed to shutdown ephemeral manager: {e}")

    def _shutdown_manager_process(self, socket_path: str, ProcessManager: Any) -> None:
        """
        Shutdown a specific manager process.

        Args:
            socket_path: Socket path of the manager to shutdown
            ProcessManager: ProcessManager class for cleanup utilities
        """
        process_info = BaseResourceActionPlugin._spawned_processes.get(socket_path)

        # If not found in in-memory dict (e.g. this process didn't spawn the manager),
        # fall back to the companion .meta file written at spawn time.
        if not process_info:
            meta_path = str(socket_path) + ".meta"
            try:
                with open(meta_path, "r") as _mf:
                    meta = json.load(_mf)
                self._display.vvvv(f"Loaded manager meta from {meta_path}: pid={meta.get('pid')}")
                # Build a minimal process_info so the shutdown logic below can proceed.
                # We don't have the Popen object, so we wrap the raw PID instead.
                import os as _os

                pid = meta.get("pid")
                if pid:

                    class _PidProxy:
                        """Thin proxy so process.poll/terminate/kill/wait work on a bare PID."""

                        def __init__(self, p):
                            self._pid = p

                        def poll(self):
                            try:
                                _os.kill(self._pid, 0)
                                return None  # still running
                            except ProcessLookupError:
                                return 0
                            except PermissionError:
                                return None

                        def terminate(self):
                            try:
                                _os.kill(self._pid, 15)  # SIGTERM
                            except ProcessLookupError:
                                pass

                        def kill(self):
                            try:
                                _os.kill(self._pid, 9)  # SIGKILL
                            except ProcessLookupError:
                                pass

                        def wait(self, timeout=None):
                            import time as _t

                            deadline = _t.monotonic() + (timeout or 30)
                            while _t.monotonic() < deadline:
                                if self.poll() is not None:
                                    return 0
                                _t.sleep(0.1)
                            raise subprocess.TimeoutExpired([], timeout)

                    process_info = {"process": _PidProxy(pid), "authkey_b64": meta.get("authkey_b64")}
                else:
                    self._display.vvvv(f"Meta file {meta_path} has no pid, cannot shut down manager")
                    return
            except FileNotFoundError:
                self._display.vvvv(f"Manager {socket_path} not in spawned processes and no meta file found — already gone")
                return
            except Exception as _e:
                self._display.vvvv(f"Could not read manager meta file {meta_path}: {_e}")
                return

        process = process_info["process"]
        authkey_b64 = process_info.get("authkey_b64")

        # Check if process is still running
        if process.poll() is None:
            self._display.vvvv(f"Manager process still running at {socket_path}, shutting down...")

            try:
                # Try graceful shutdown via RPC
                if authkey_b64 and Path(socket_path).exists():
                    try:
                        authkey = base64.b64decode(authkey_b64)
                        from .plugin_utils.manager.rpc_client import ManagerRPCClient

                        # CRITICAL: Ensure socket_path is a string (Fedora/Path object compatibility)
                        socket_path_str = str(socket_path)
                        client = ManagerRPCClient(process_info.get("gateway_url", ""), socket_path_str, authkey)
                        # Call shutdown method
                        try:
                            shutdown_result = client.shutdown_manager()
                            self._display.vvvv(f"Sent shutdown signal to manager at {socket_path}: {shutdown_result}")
                        except Exception as e:
                            self._display.vvvv(f"Shutdown RPC failed (manager may have already shut down): {e}")
                        finally:
                            client.close()
                    except Exception as e:
                        self._display.vvvv(f"Could not connect for graceful shutdown: {e}")

                # Wait for graceful shutdown (max 5 seconds)
                try:
                    process.wait(timeout=5)
                    self._display.vvvv(f"Manager process at {socket_path} shut down gracefully")
                except subprocess.TimeoutExpired:
                    self._display.warning(f"Manager process at {socket_path} did not shut down gracefully, forcing termination")
                    process.terminate()
                    time.sleep(1)
                    if process.poll() is None:
                        process.kill()
                        process.wait()
            except Exception as e:
                self._display.warning(f"Error shutting down manager at {socket_path}: {e}")
                # Force kill as fallback
                try:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                except Exception:
                    pass

        # Clean up socket file and companion meta file
        try:
            ProcessManager.cleanup_old_socket(socket_path)
            self._display.vvvv(f"Cleaned up socket file: {socket_path}")
        except Exception as e:
            self._display.vvvv(f"Could not clean up socket file {socket_path}: {e}")
        try:
            meta_path = str(socket_path) + ".meta"
            if Path(meta_path).exists():
                Path(meta_path).unlink()
                self._display.vvvv(f"Cleaned up manager meta file: {meta_path}")
        except Exception as e:
            self._display.vvvv(f"Could not clean up meta file: {e}")

        # Remove from tracking
        BaseResourceActionPlugin._spawned_processes.pop(socket_path, None)

    def _should_update(self, desired_data, current_data):
        """
        Return True if any explicitly-provided writable field differs between
        the desired task args and the current API state.

        Comparison rules:
        - Only fields that are present in BOTH desired_data and current_data
          are compared (fields missing from the API response are ignored).
        - Auth params, Ansible directives (state, new_name), and read-only
          fields (id, created, …) are excluded.
        - FK fields: when desired is a str but current is an int (i.e. the
          task supplied a name that the API stored as a resolved integer id),
          the comparison is skipped to avoid false positives.  The reverse
          (int desired, str current) is also skipped.  Additionally, when
          desired is a non-numeric str (a name) and current is a digit str
          (an int FK that from_api converted to str), the comparison is
          skipped — e.g. authenticator='my-auth' vs '3100'.
        - new_name: always triggers an update (it's a rename operation).
        - Dict/list fields are compared via equality; type mismatches skip.
        """
        if desired_data.get("new_name"):
            return True

        skip_keys = self._AUTH_PARAMS | self._ANSIBLE_DIRECTIVES | self._READ_ONLY_FIELDS | self._WRITE_ONLY_FIELDS

        for key, desired_val in desired_data.items():
            if key in skip_keys or desired_val is None:
                continue
            if key not in current_data:
                # Field not returned by API — cannot compare, assume no change
                continue
            current_val = current_data[key]
            if (
                key not in self._MUTABLE_FK_FIELDS
                and isinstance(desired_val, str)
                and isinstance(current_val, str)
                and not desired_val.isdigit()
                and current_val.isdigit()
            ):
                continue
            # Same type: direct equality
            if type(desired_val) is type(current_val):
                if desired_val != current_val:
                    return True
            else:
                # Coerce to string for cross-type scalars (e.g. int vs float)
                if str(desired_val) != str(current_val):
                    return True

        return False

    def run(self, tmp: object = None, task_vars: Optional[dict] = None) -> dict:
        """
        Standard run() for resource action plugins.

        Subclasses that set MODEL_CLASS (and optionally LOOKUP_FIELD) get
        full CRUD idempotency for free — no need to override this method.

        State machine:
          present -> find by LOOKUP_FIELD; update if found, create if not
          absent -> find by LOOKUP_FIELD; delete if found, no-op if not
          exists -> find; return exists=True/False without changes
          enforced -> find; merge declared fields; update or create
          check_mode is honoured for create / update / delete

        Args:
            tmp: Temporary directory (deprecated, unused)
            task_vars: Task variables from Ansible

        Returns:
            dict: Ansible result dictionary
        """
        if task_vars is None:
            task_vars = {}
        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        if self.MODEL_CLASS is None:
            raise AnsibleError("%s must set MODEL_CLASS or override run()" % type(self).__name__)

        try:
            # ---- argspec & input validation --------------------------------
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError("Could not load DOCUMENTATION for %s module" % self.MODULE_NAME)
            validated_input = self._validate_data(self._task.args.copy(), argspec, "input")

            # ---- manager connection ----------------------------------------
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager
            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            # ---- build resource object -------------------------------------
            validated_params = validated_input.validated_parameters
            resource_data = {k: v for k, v in validated_params.items() if v is not None and k not in self._AUTH_PARAMS}

            # Warn about and strip deprecated argspec fields.
            for field, (msg, version) in self._DEPRECATED_FIELDS.items():
                if resource_data.pop(field, None) is not None:
                    result.setdefault("deprecations", []).append({"msg": msg, "version": version, "collection_name": "ansible.platform"})

            # Pop write-only fields (not present in MODEL_CLASS) before instantiation;
            # they are passed to _pre_execute_hook for use just before manager.execute().
            _write_only_data = {f: resource_data.pop(f) for f in self._WRITE_ONLY_FIELDS if f in resource_data}

            resource = self.MODEL_CLASS(**resource_data)

            # Allow subclasses to resolve lookup-by-id or other mutations.
            self._resolve_lookup(resource, resource_data, validated_params)

            operation = self._detect_operation(validated_params)
            state = validated_params.get("state", "present")
            lookup_val = getattr(resource, self.LOOKUP_FIELD, None)

            # ---- state: exists (read-only) ----------------------------------
            if state == "exists":
                try:
                    find_result = manager.execute(
                        operation="find",
                        module_name=self.MODULE_NAME,
                        ansible_data=resource_data,
                    )
                    exists = bool(find_result and find_result.get("id"))
                except Exception:
                    find_result, exists = {}, False
                result.update(
                    {
                        "changed": False,
                        "failed": False,
                        "exists": exists,
                        self.MODULE_NAME: find_result if exists else {},
                        "id": find_result.get("id") if exists else None,
                    }
                )
                return result

            # ---- present: idempotent create (find -> compare ->  update only if changed) -----
            if operation == "create" and state == "present":
                try:
                    find_result = manager.execute(
                        operation="find",
                        module_name=self.MODULE_NAME,
                        ansible_data=resource_data,
                    )
                    if find_result and find_result.get("id"):
                        if not self._should_update(resource_data, find_result):
                            # Nothing changed — return current state without touching API
                            result.update(
                                {
                                    "changed": False,
                                    "failed": False,
                                    self.MODULE_NAME: find_result,
                                }
                            )
                            return result
                        operation = "update"
                        resource.id = find_result["id"]
                except Exception:
                    pass

            # ---- absent: find by lookup field to get id --------------------
            if operation == "delete" and not getattr(resource, "id", None):
                try:
                    find_result = manager.execute(
                        operation="find",
                        module_name=self.MODULE_NAME,
                        ansible_data=resource_data,
                    )
                    if find_result and find_result.get("id"):
                        resource.id = find_result["id"]
                    else:
                        result.update(
                            {
                                "changed": False,
                                "failed": False,
                                self.MODULE_NAME: {"state": "absent"},
                                "msg": "%s '%s' does not exist (already absent)" % (self.MODULE_NAME, lookup_val),
                            }
                        )
                        return result
                except Exception:
                    result.update(
                        {
                            "changed": False,
                            "failed": False,
                            self.MODULE_NAME: {"state": "absent"},
                            "msg": "%s '%s' does not exist (already absent)" % (self.MODULE_NAME, lookup_val),
                        }
                    )
                    return result

            # ---- enforced: find -> merge declared fields -> update/create ----
            if operation == "enforced":
                argspec_fields = set(argspec.get("argument_spec", {}).keys())
                try:
                    find_result = manager.execute(
                        operation="find",
                        module_name=self.MODULE_NAME,
                        ansible_data=resource_data,
                    )
                except ValueError:
                    find_result = None
                if find_result and find_result.get("id"):
                    merged = {}
                    for k in argspec_fields:
                        if k in self._AUTH_PARAMS:
                            continue
                        if k in validated_params:
                            merged[k] = validated_params[k]
                        elif k == self.LOOKUP_FIELD:
                            merged[k] = find_result.get(k) or lookup_val
                        else:
                            merged[k] = None
                    for ro in self._READ_ONLY_FIELDS:
                        if ro in find_result:
                            merged[ro] = find_result[ro]
                    merged.setdefault(self.LOOKUP_FIELD, lookup_val)
                    # Short-circuit if the merged desired state matches current
                    if not self._should_update(merged, find_result):
                        result.update(
                            {
                                "changed": False,
                                "failed": False,
                                self.MODULE_NAME: find_result,
                            }
                        )
                        return result
                    resource = self.MODEL_CLASS(**{k: v for k, v in merged.items() if hasattr(self.MODEL_CLASS, k)})
                    operation = "update"
                else:
                    operation = "create"

            # ---- check mode ------------------------------------------------
            ansible_data = self._build_ansible_data(resource, validated_params, operation)
            if operation == "update" and state == "enforced":
                ansible_data["_platform_enforced"] = True

            if self._task.check_mode and operation in ("create", "update", "delete"):
                if operation == "delete":
                    result.update(
                        {
                            "changed": bool(getattr(resource, "id", None)),
                            "failed": False,
                            self.MODULE_NAME: {"state": "absent"},
                        }
                    )
                else:
                    result.update(
                        {
                            "changed": True,
                            "failed": False,
                            self.MODULE_NAME: {
                                self.LOOKUP_FIELD: lookup_val,
                                "id": getattr(resource, "id", None),
                            },
                        }
                    )
                return result

            # ---- execute ---------------------------------------------------
            self._pre_execute_hook(ansible_data, _write_only_data, validated_params, operation)
            try:
                manager_result = manager.execute(
                    operation=operation,
                    module_name=self.MODULE_NAME,
                    ansible_data=ansible_data,
                )
            except ValueError as exc:
                if operation == "find" and ("not found" in str(exc).lower() or "resource with" in str(exc).lower()):
                    result.update(
                        {
                            "changed": False,
                            "failed": False,
                            self.MODULE_NAME: {},
                            "exists": False,
                            "msg": "%s '%s' does not exist" % (self.MODULE_NAME, lookup_val),
                        }
                    )
                    return result
                raise

            # ---- build clean result ----------------------------------------
            # Keys that must NEVER appear in the nested resource dict
            # (ANSTRAT-1640): Ansible directives, read-only API metadata, and
            # internal debug keys.
            _strip_from_resource = (
                self._ANSIBLE_DIRECTIVES
                | (self._READ_ONLY_FIELDS - {"id"})  # keep id, strip created/modified/url
                | {"changed"}
            )

            argspec_fields = set(argspec.get("argument_spec", {}).keys())
            argspec_resource_fields = (argspec_fields - self._ANSIBLE_DIRECTIVES) | {"id"}
            filtered = {k: v for k, v in manager_result.items() if k in argspec_resource_fields}
            try:
                validated_output = self._validate_data(
                    {k: v for k, v in filtered.items() if k in argspec_fields and k not in self._ANSIBLE_DIRECTIVES},
                    argspec,
                    "output",
                )
                if "id" in filtered:
                    validated_output["id"] = filtered["id"]
            except Exception:
                validated_output = {k: v for k, v in manager_result.items() if k not in _strip_from_resource}
                if "id" in manager_result:
                    validated_output["id"] = manager_result["id"]

            # Final pass: strip any banned keys that slipped through argspec
            # validation (e.g. read-only fields declared in module DOCUMENTATION
            # but not writable by the user).
            # Also strip:
            #   - 'new_*' fields (rename/move directives, e.g. new_organization)
            #   - '*_id' fields that are internal resolved FK integers
            #     (e.g. organization_id) — the resolved FK is not a user-visible
            #     return value; the user sees the original name field instead.
            validated_output = {
                k: v
                for k, v in validated_output.items()
                if k not in _strip_from_resource and not k.startswith("new_") and not (k.endswith("_id") and k != "id")
            }

            # Output-layer type conversion: space-separated API strings - lists.
            for _field in self._SPACE_SEPARATED_LIST_FIELDS:
                if _field in validated_output:
                    _raw = validated_output[_field]
                    if isinstance(_raw, str):
                        validated_output[_field] = _raw.split() if _raw.strip() else None

            # Extra non-argspec fields (e.g. client_id for application).
            # These are returned flat only — never nested — because they are not
            # valid module inputs and would break round-trip if included in
            # the MODULE_NAME dict.
            extra_flat = {k: manager_result[k] for k in self._EXTRA_RETURN_FIELDS if k in manager_result and manager_result[k] is not None}

            result.update(
                {
                    "changed": manager_result.get("changed", False),
                    "failed": False,
                    # ----------------------------------------------------------------
                    # Nested resource dict — argspec fields only, round-trip safe.
                    # Use result.<module_name>.<field> in new playbooks.
                    # ----------------------------------------------------------------
                    self.MODULE_NAME: validated_output,
                    # Flat top-level keys kept for backward compatibility with
                    # playbooks written against <=2.6.
                    **validated_output,
                    **extra_flat,
                }
            )

            if operation == "find":
                result["exists"] = bool(validated_output.get("id"))

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result

    def _detect_operation(self, args: dict) -> str:
        """
        Detect operation type from arguments (CRUD-aligned state).

        Args:
            args: Module arguments

        Returns:
            str: Operation name ('create', 'update', 'delete', 'find', 'enforced').
            'enforced' is handled by the action plugin (find then merge and create/update).
        """
        state = args.get("state", "present")

        if state in ("absent", "deleted"):
            return "delete"
        elif state == "present":
            if args.get("id"):
                return "update"
            return "create"
        elif state in ("exists", "find", "gathered"):
            return "find"
        elif state in ("enforced", "merged"):
            return "enforced"
        else:
            raise AnsibleError(f"Unknown state: {state}")
