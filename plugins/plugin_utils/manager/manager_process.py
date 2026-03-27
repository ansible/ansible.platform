#!/usr/bin/env python
"""
Standalone script for the persistent manager process.

This is executed as a separate process via subprocess to avoid multiprocessing issues.
"""

import sys
import os
import json
import base64
import traceback
from pathlib import Path


def main():
    """Main entry point for the manager process."""
    # Write startup marker immediately
    try:
        marker = Path('/tmp/ansible_platform_manager_started.txt')
        with open(marker, 'a') as f:
            f.write(f"Script started with {len(sys.argv)} args\n")
            f.write(f"Args: {sys.argv}\n")
    except Exception:
        pass

    # Read configuration from command line args
    if len(sys.argv) < 10:
        print(f"ERROR: Expected 9 args, got {len(sys.argv) - 1}", file=sys.stderr)
        print(f"Args received: {sys.argv}", file=sys.stderr)
        sys.exit(1)

    # Log progress
    marker = Path('/tmp/ansible_platform_manager_started.txt')

    def log_marker(msg):
        try:
            with open(marker, 'a') as f:
                f.write(f"{msg}\n")
        except Exception:
            pass

    log_marker("Parsing arguments...")
    socket_path = sys.argv[1]
    socket_dir = sys.argv[2]
    inventory_hostname = sys.argv[3]
    gateway_url = sys.argv[4]
    gateway_username = sys.argv[5] or None
    gateway_password = sys.argv[6] or None
    gateway_token = sys.argv[7] or None
    gateway_validate_certs = sys.argv[8].lower() == 'true'
    gateway_request_timeout = float(sys.argv[9])
    log_marker("Arguments parsed successfully")

    # Read sys.path and authkey from environment
    log_marker("Reading environment variables...")
    sys_path_b64 = os.environ.get('ANSIBLE_PLATFORM_SYS_PATH', '')
    authkey_b64 = os.environ.get('ANSIBLE_PLATFORM_AUTHKEY', '')
    log_marker(f"Got sys_path_b64 length: {len(sys_path_b64)}")
    log_marker(f"Got authkey_b64 length: {len(authkey_b64)}")

    # Decode sys.path
    log_marker("Decoding sys.path...")
    try:
        sys_path_json = base64.b64decode(sys_path_b64).decode('utf-8')
        sys_path_list = json.loads(sys_path_json)
        log_marker(f"Decoded sys.path with {len(sys_path_list)} entries")
    except Exception as e:
        log_marker(f"FAILED to decode sys.path: {e}")
        sys.exit(1)

    # Redirect stderr to a file for debugging
    log_marker("Setting up logging...")
    stderr_log = Path(socket_dir) / f'manager_stderr_{inventory_hostname}.log'
    error_log = Path(socket_dir) / f'manager_error_{inventory_hostname}.log'

    try:
        sys.stderr = open(stderr_log, 'w', buffering=1)
        sys.stdout = open(stderr_log, 'a', buffering=1)
        log_marker("Logging redirected")
    except Exception as e:
        log_marker(f"Failed to redirect logging: {e}")
        pass  # Continue without redirecting

    try:
        log_marker("Restoring sys.path...")
        # Restore parent's sys.path in child process
        sys.path = sys_path_list
        log_marker(f"sys.path restored with entries: {sys_path_list}")

        # Ensure collections directory is on sys.path
        # The script is in: ansible_collections/ansible/platform/plugins/plugin_utils/manager/
        # To import ansible_collections.ansible.platform, we need the PARENT of ansible_collections/
        script_dir = Path(__file__).resolve().parent
        collections_dir = script_dir.parent.parent.parent.parent.parent  # ansible_collections/
        workspace_root = collections_dir.parent  # parent of ansible_collections/
        workspace_root_str = str(workspace_root)
        log_marker(f"Workspace root: {workspace_root_str}")
        log_marker(f"Collections dir: {collections_dir}")
        if workspace_root_str not in sys.path:
            sys.path.insert(0, workspace_root_str)
            log_marker("Added workspace root to sys.path")
        else:
            log_marker("Workspace root already in sys.path")

        # Decode authkey from base64
        log_marker("Decoding authkey...")
        authkey = base64.b64decode(authkey_b64)
        log_marker(f"Authkey decoded, length: {len(authkey)}")

        # Write to log immediately
        log_marker(f"Writing to error log: {error_log}")
        with open(error_log, 'w') as f:
            f.write(f"Process started, socket_path={socket_path}\n")
            f.write(f"sys.path has {len(sys_path_list)} entries\n")
            f.write(f"Manager starting at {socket_path}\n")
            f.write(f"About to create service with base_url={gateway_url}\n")
            f.flush()
        log_marker("Error log written successfully")

        log_marker("About to import platform_manager...")
        try:
            from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig
            from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import (
                PlatformManager,
                PlatformService
            )
            log_marker("Imports successful!")
        except Exception as import_err:
            log_marker(f"Import failed: {import_err}")
            log_marker(f"Import traceback: {traceback.format_exc()}")
            raise

        with open(error_log, 'a') as f:
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
            with open(error_log, 'a') as f:
                f.write("GatewayConfig created successfully\n")
                f.flush()
        except Exception as config_err:
            with open(error_log, 'a') as f:
                f.write(f"GatewayConfig creation failed: {config_err}\n")
                f.write(traceback.format_exc())
                f.flush()
            raise

        # Lazy-init: start the socket server first so the action plugin can connect
        # immediately, then initialize PlatformService in a background thread.
        import threading

        _service_container = {'service': None, 'error': None}
        _service_ready = threading.Event()

        def _init_service():
            """Initialize PlatformService in background thread."""
            try:
                with open(error_log, 'a') as f:
                    f.write("=" * 80 + "\n")
                    f.write("About to create PlatformService (background thread)...\n")
                    f.write("=" * 80 + "\n")
                    f.flush()
                svc = PlatformService(config)
                _service_container['service'] = svc
                with open(error_log, 'a') as f:
                    f.write("=" * 80 + "\n")
                    f.write("✅ Service created successfully\n")
                    f.write(f"   API Version: {svc.api_version}\n")
                    f.write(f"   Base URL: {config.base_url}\n")
                    f.write("=" * 80 + "\n")
                    f.flush()
            except Exception as service_err:
                _service_container['error'] = service_err
                with open(error_log, 'a') as f:
                    f.write(f"Service creation failed: {service_err}\n")
                    f.write(traceback.format_exc())
                    f.flush()
            finally:
                _service_ready.set()

        def _get_service():
            """Callable registered with manager — blocks until service is ready."""
            # Wait up to 60 s (covers two 10-s HTTP calls plus overhead)
            if not _service_ready.wait(timeout=60):
                raise RuntimeError("PlatformService initialization timed out (>60s)")
            svc_error = _service_container['error']
            if svc_error is not None:
                raise svc_error
            return _service_container['service']

        def _shutdown_service():
            """Callable registered with manager — blocks until service is ready, then shuts down."""
            _service_ready.wait(timeout=60)
            svc = _service_container.get('service')
            if svc is not None:
                svc.shutdown()

        # Register callables BEFORE creating the socket so they're available
        # as soon as the action plugin connects.
        PlatformManager.register(
            'get_platform_service',
            callable=_get_service
        )
        PlatformManager.register(
            'shutdown',
            callable=_shutdown_service
        )

        with open(error_log, 'a') as f:
            f.write("Lazy callables registered\n")
            f.flush()

        # Set up signal handlers for graceful shutdown
        import signal

        def signal_handler(signum, frame):
            """Handle shutdown signals gracefully."""
            with open(error_log, 'a') as f:
                f.write(f"Received signal {signum}, shutting down...\n")
                f.flush()
            try:
                _shutdown_service()
            except Exception as e:
                with open(error_log, 'a') as f:
                    f.write(f"Error during shutdown: {e}\n")
                    f.flush()
            sys.exit(0)

        # Register signal handlers
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        with open(error_log, 'a') as f:
            f.write("Signal handlers registered\n")
            f.flush()

        # Start manager server (creates socket file — action plugin can now connect)
        manager = PlatformManager(address=socket_path, authkey=authkey)

        with open(error_log, 'a') as f:
            f.write("Manager instance created\n")
            f.flush()

        server = manager.get_server()

        with open(error_log, 'a') as f:
            f.write("Server obtained, starting service init thread and serve_forever()\n")
            f.flush()

        # NOW start PlatformService init in background (socket already bound)
        _init_thread = threading.Thread(target=_init_service, daemon=True)
        _init_thread.start()

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            with open(error_log, 'a') as f:
                f.write("Keyboard interrupt received, shutting down...\n")
                f.flush()
            _shutdown_service()
            sys.exit(0)

    except Exception as e:
        # Log to a temp file for debugging
        with open(error_log, 'a') as f:
            f.write(f"\n\nManager startup failed: {e}\n")
            f.write(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
