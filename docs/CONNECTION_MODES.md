# Connection modes (standard vs persistent manager)

The `ansible.platform.http` connection plugin can run in **direct (standard)** mode or **persistent (experimental)** mode. Persistent mode spawns a separate **manager process** that keeps an HTTP session and shared caches across tasks.

## Idle timeout (`idle_timeout`)

Manager processes would otherwise stay alive until the Ansible owner process exits or the socket is cleaned up. To reduce orphaned managers and memory use, the manager tracks **last activity** (RPC calls such as `execute` and `lookup_resource_id`, and HTTP requests made through the service) and shuts down automatically when nothing has run for longer than the configured **idle timeout**.

| Behavior | Detail |
|----------|--------|
| Default | **3600** seconds (1 hour) |
| Disable | Set to **0** (manager only exits via owner PID watchdog, signals, or explicit shutdown — not recommended for production) |
| Poll interval | A background thread checks idle state every **60** seconds |
| On timeout | The manager calls `PlatformService.shutdown()`, stops the RPC server, removes the Unix socket (and `.meta` if present), and exits |

### Configuration

Set the timeout in seconds using either:

- **`gateway_idle_timeout`** in task arguments or inventory/host variables, or  
- **`ansible_platform_manager_idle_timeout`** in inventory/host variables (alias).

Example (inventory):

```yaml
gateway_idle_timeout: 1800
```

Values are passed through `GatewayConfig` into the manager subprocess when the connection plugin spawns the process.

### Test-only: poll interval

For automated tests, the check interval can be overridden with the environment variable **`ANSIBLE_PLATFORM_IDLE_POLL_SECONDS`** (default `60`). Production deployments should rely on the default 60-second polling.

## Related components

- **`GatewayConfig`** (`plugins/plugin_utils/platform/config.py`) — holds `idle_timeout` and other gateway settings.
- **`PlatformService`** (`plugins/plugin_utils/manager/platform_manager.py`) — records activity and implements `should_exit_for_idle()`.
- **`manager_process.py`** — standalone entry point: starts the idle monitor thread and performs socket cleanup on exit.
