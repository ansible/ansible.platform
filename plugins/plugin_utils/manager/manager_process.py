#!/usr/bin/env python
"""
Standalone script for the persistent manager process.

This is executed as a separate process via subprocess to avoid multiprocessing issues.
"""

import base64
import json
import os
import sys
import traceback
from pathlib import Path


def _compute_poll_interval(idle_timeout: float) -> int:
    """Return the idle-monitor sleep interval derived from the configured timeout.

    The interval is set to 10 % of ``idle_timeout`` so the manager checks
    roughly 10 times per timeout window, giving a worst-case overshoot of
    one poll interval (10 % of the timeout) instead of a fixed 60 s.

    Bounds:
      - Floor: 5 s  — avoids busy-looping for very short timeouts.
      - Cap:  60 s  — avoids infrequent checks for very long timeouts.
      - ``idle_timeout <= 0`` (disabled): returns 60 s (interval is irrelevant).
    """
    if idle_timeout <= 0:
        return 60
    return max(5, min(60, int(idle_timeout / 10)))


_SENSITIVE_ARGV_POSITIONS = {5, 6, 7}


def _redact_argv(argv=None):
    """Return a copy of argv with credential positions replaced by '<redacted>'.

    Always safe to log — sensitive positions (username, password, token) are
    replaced even when the value is an empty string, so length cannot be inferred.
    """
    if argv is None:
        argv = sys.argv
    redacted = list(argv)
    for i in _SENSITIVE_ARGV_POSITIONS:
        if i < len(redacted) and redacted[i]:
            redacted[i] = "<redacted>"
    return redacted


def main():
    """Main entry point for the manager process."""

    # Write startup marker immediately — credentials at argv[6] and argv[7] are masked
    def _safe_argv():
        """Return sys.argv with credential positions (password, token) replaced by '***'."""
        safe = list(sys.argv)
        for i in (6, 7):
            if i < len(safe) and safe[i]:
                safe[i] = "***"
        return safe

    try:
        marker = Path("/tmp/ansible_platform_manager_started.txt")
        with open(marker, "a") as f:
            f.write(f"Script started with {len(sys.argv)} args\n")
            f.write(f"Args: {_redact_argv()}\n")
    except Exception:
        pass

    if len(sys.argv) < 10:
        print(f"ERROR: Expected at least 9 args (optional 10th: idle_timeout), got {len(sys.argv) - 1}", file=sys.stderr)
        print(f"Args received: {_redact_argv()}", file=sys.stderr)
        sys.exit(1)

    marker = Path("/tmp/ansible_platform_manager_started.txt")

    def log_marker(msg):
        try:
            with open(marker, "a") as f:
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
    gateway_validate_certs = sys.argv[8].lower() == "true"
    gateway_request_timeout = float(sys.argv[9])
    pm_idle_timeout_arg = float(sys.argv[10]) if len(sys.argv) > 10 else 3600.0
    log_marker("Arguments parsed successfully")

    log_marker("Reading environment variables...")
    sys_path_b64 = os.environ.get("ANSIBLE_PLATFORM_SYS_PATH", "")
    authkey_b64 = os.environ.get("ANSIBLE_PLATFORM_AUTHKEY", "")
    owner_pid_str = os.environ.get("ANSIBLE_PLATFORM_OWNER_PID", "")
    log_marker(f"Got sys_path_b64 length: {len(sys_path_b64)}")
    log_marker(f"Got authkey_b64 length: {len(authkey_b64)}")
    log_marker(f"Got owner_pid: {owner_pid_str}")

    log_marker("Decoding sys.path...")
    try:
        sys_path_json = base64.b64decode(sys_path_b64).decode("utf-8")
        sys_path_list = json.loads(sys_path_json)
        log_marker(f"Decoded sys.path with {len(sys_path_list)} entries")
    except Exception as e:
        log_marker(f"FAILED to decode sys.path: {e}")
        sys.exit(1)

    log_marker("Setting up logging...")
    stderr_log = Path(socket_dir) / f"manager_stderr_{inventory_hostname}.log"
    error_log = Path(socket_dir) / f"manager_error_{inventory_hostname}.log"

    try:
        sys.stderr = open(stderr_log, "w", buffering=1)
        sys.stdout = open(stderr_log, "a", buffering=1)
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

        log_marker("Decoding authkey...")
        authkey = base64.b64decode(authkey_b64)
        log_marker(f"Authkey decoded, length: {len(authkey)}")

        log_marker(f"Writing to error log: {error_log}")
        with open(error_log, "w") as f:
            f.write(f"Process started, socket_path={socket_path}\n")
            f.write(f"sys.path has {len(sys_path_list)} entries\n")
            f.write(f"Manager starting at {socket_path}\n")
            f.write(f"About to create service with base_url={gateway_url}\n")
            f.flush()
        log_marker("Error log written successfully")

        log_marker("About to import platform_manager...")
        try:
            from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformManager, PlatformService
            from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig

            log_marker("Imports successful!")
        except Exception as import_err:
            log_marker(f"Import failed: {import_err}")
            log_marker(f"Import traceback: {traceback.format_exc()}")
            raise

        with open(error_log, "a") as f:
            f.write("Imports successful\n")
            f.flush()

        try:
            config = GatewayConfig(
                base_url=gateway_url,
                username=gateway_username,
                password=gateway_password,
                oauth_token=gateway_token,
                verify_ssl=gateway_validate_certs,
                request_timeout=gateway_request_timeout,
                connection_mode="experimental",  # Persistent manager is always experimental mode
                idle_timeout=pm_idle_timeout_arg,
            )
            with open(error_log, "a") as f:
                f.write("GatewayConfig created successfully\n")
                f.flush()
        except Exception as config_err:
            with open(error_log, "a") as f:
                f.write(f"GatewayConfig creation failed: {config_err}\n")
                f.write(traceback.format_exc())
                f.flush()
            raise

        # Lazy-init: start the socket server first so the action plugin can connect
        # immediately, then initialize PlatformService in a background thread.
        import threading

        _service_container = {"service": None, "error": None}
        _service_ready = threading.Event()

        def _init_service():
            """Initialize PlatformService in background thread."""
            try:
                with open(error_log, "a") as f:
                    f.write("=" * 80 + "\n")
                    f.write("About to create PlatformService (background thread)...\n")
                    f.write("=" * 80 + "\n")
                    f.flush()
                svc = PlatformService(config)
                _service_container["service"] = svc
                with open(error_log, "a") as f:
                    f.write("=" * 80 + "\n")
                    f.write("✅ Service created successfully\n")
                    f.write(f"   API Version: {svc.api_version}\n")
                    f.write(f"   Base URL: {config.base_url}\n")
                    f.write("=" * 80 + "\n")
                    f.flush()
            except Exception as service_err:
                _service_container["error"] = service_err
                with open(error_log, "a") as f:
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
            svc_error = _service_container["error"]
            if svc_error is not None:
                raise svc_error
            return _service_container["service"]

        def _shutdown_service():
            """Callable registered with manager — blocks until service is ready, then shuts down."""
            _service_ready.wait(timeout=60)
            svc = _service_container.get("service")
            if svc is not None:
                svc.shutdown()

        # Register callables BEFORE creating the socket so they're available
        # as soon as the action plugin connects.
        PlatformManager.register("get_platform_service", callable=_get_service)
        PlatformManager.register("shutdown", callable=_shutdown_service)

        with open(error_log, "a") as f:
            f.write("Lazy callables registered\n")
            f.flush()

        import signal

        def signal_handler(signum, frame):
            with open(error_log, "a") as f:
                f.write(f"Received signal {signum}, shutting down...\n")
                f.flush()
            try:
                _shutdown_service()
            except Exception as e:
                with open(error_log, "a") as f:
                    f.write(f"Error during shutdown: {e}\n")
                    f.flush()
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        with open(error_log, "a") as f:
            f.write("Signal handlers registered\n")
            f.flush()

        # ------------------------------------------------------------------ #
        # Owner-process watchdog                                              #
        # ------------------------------------------------------------------ #
        # When ansible-playbook exits the manager should also exit — with no
        # Ansible callback config required.  We watch the main ansible-playbook
        # process PID (passed via ANSIBLE_PLATFORM_OWNER_PID) and shut down
        # automatically once that process is gone.
        _owner_pid = None
        if owner_pid_str:
            try:
                _owner_pid = int(owner_pid_str)
            except ValueError:
                pass

        _survive_path = Path(socket_dir) / ".survive"
        _survive_mode = _survive_path.exists()

        with open(error_log, "a") as f:
            if _survive_mode:
                f.write(f"Molecule .survive flag detected at {_survive_path} — using survive watchdog\n")
            elif _owner_pid:
                f.write(f"Starting owner watchdog for PID {_owner_pid}\n")
            else:
                f.write("No owner PID and no .survive flag — manager will run until killed\n")
            f.flush()

        if _survive_mode or _owner_pid:

            def _owner_watchdog():
                import time as _time

                if _survive_mode:
                    # Molecule mode: keep running as long as the .survive file exists.
                    while _survive_path.exists():
                        _time.sleep(2)
                    with open(error_log, "a") as _f:
                        _f.write(f".survive flag removed at {_survive_path}, shutting down manager\n")
                        _f.flush()
                else:
                    # Production mode: keep running as long as the owner PID is alive.
                    while True:
                        _time.sleep(3)
                        try:
                            os.kill(_owner_pid, 0)  # signal 0 = liveness check, no side-effects
                        except ProcessLookupError:
                            # Owner (ansible-playbook) has exited — clean shutdown.
                            with open(error_log, "a") as _f:
                                _f.write(f"Owner PID {_owner_pid} gone, shutting down manager\n")
                                _f.flush()
                            break
                        except PermissionError:
                            pass  # Process exists but owned by another user — keep running
                try:
                    _shutdown_service()
                except Exception:
                    pass
                os._exit(0)

            _watchdog_thread = threading.Thread(target=_owner_watchdog, daemon=True, name="owner-watchdog")
            _watchdog_thread.start()
            with open(error_log, "a") as f:
                mode = "survive" if _survive_mode else "owner-pid"
                f.write(f"Watchdog thread started (mode={mode})\n")
                f.flush()

        # Start manager server (creates socket file — action plugin can now connect)
        manager = PlatformManager(address=socket_path, authkey=authkey)

        with open(error_log, "a") as f:
            f.write("Manager instance created\n")
            f.flush()

        server = manager.get_server()

        with open(error_log, "a") as f:
            f.write("Server obtained, starting service init thread and serve_forever()\n")
            f.flush()

        # NOW start PlatformService init in background (socket already bound)
        _init_thread = threading.Thread(target=_init_service, daemon=True)
        _init_thread.start()

        idle_poll_interval = _compute_poll_interval(config.idle_timeout)

        if float(config.idle_timeout) > 0:

            def _idle_monitor():
                import time as _time

                from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import ProcessManager

                while True:
                    _time.sleep(idle_poll_interval)
                    if not _service_ready.is_set():
                        continue
                    svc = _service_container.get("service")
                    if svc is None:
                        continue
                    if not svc.should_exit_for_idle():
                        continue
                    try:
                        with open(error_log, "a") as _f:
                            _f.write("Idle timeout exceeded, shutting down manager\n")
                            _f.flush()
                    except Exception:
                        pass
                    try:
                        _shutdown_service()
                    except Exception as _e:
                        try:
                            with open(error_log, "a") as _f:
                                _f.write(f"Idle shutdown (service): {_e}\n")
                                _f.flush()
                        except Exception:
                            pass
                    try:
                        server.shutdown()
                    except Exception as _e:
                        try:
                            with open(error_log, "a") as _f:
                                _f.write(f"Idle shutdown (server): {_e}\n")
                                _f.flush()
                        except Exception:
                            pass
                    try:
                        ProcessManager.cleanup_old_socket(socket_path)
                    except Exception as _e:
                        print(f"Idle shutdown (socket cleanup failed): {_e}", file=sys.stderr)
                    finally:
                        os._exit(0)

            _idle_thread = threading.Thread(target=_idle_monitor, daemon=True, name="idle-timeout")
            _idle_thread.start()
            with open(error_log, "a") as f:
                f.write(f"Idle timeout monitor started (interval={idle_poll_interval}s, idle_timeout={config.idle_timeout}s)\n")
                f.flush()

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            with open(error_log, "a") as f:
                f.write("Keyboard interrupt received, shutting down...\n")
                f.flush()
            _shutdown_service()
            sys.exit(0)

    except Exception as e:
        # Log to a temp file for debugging
        with open(error_log, "a") as f:
            f.write(f"\n\nManager startup failed: {e}\n")
            f.write(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
