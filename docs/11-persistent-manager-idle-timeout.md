# Persistent Manager Idle Timeout

The persistent manager subprocess auto-terminates after a configurable period of
inactivity to prevent orphaned processes from consuming resources indefinitely.

This document consolidates idle timeout configuration, semantics, edge cases, and
testing guidance in one place. For the broader manager architecture, see
[03-sdk-architecture.md](03-sdk-architecture.md). For implementation details, see
[06-foundation-components.md](06-foundation-components.md) (Components 8–10).

---

## Table of Contents

1. [Why Idle Timeout Exists](#why-idle-timeout-exists)
2. [Configuration](#configuration)
3. [How It Works](#how-it-works)
4. [Polling Behavior](#polling-behavior)
5. [Disabling Auto-Shutdown](#disabling-auto-shutdown)
6. [Edge Cases](#edge-cases)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

---

## Why Idle Timeout Exists

The persistent manager subprocess (`PlatformManager`) owns the HTTP session to the
AAP Gateway and stays alive across multiple tasks in a play. Without idle timeout,
several scenarios can leave orphaned manager processes:

- Playbook fails mid-run (Ansible exits but the manager subprocess continues)
- User cancels a playbook with Ctrl+C (SIGINT may not propagate to the subprocess)
- Ansible worker process crashes or is killed by the OS

The idle timeout acts as a safety net: if no RPC calls arrive within the configured
window, the manager shuts itself down, closes its HTTP session, and removes its
Unix domain socket file.

---

## Configuration

The idle timeout is configured via one of three methods, resolved in this order:

### 1. Task variable (highest priority)

```yaml
- name: Task with custom idle timeout
  ansible.platform.user:
    username: alice
    state: present
  vars:
    ansible_platform_manager_idle_timeout: 7200  # 2 hours
```

### 2. Gateway variable

```yaml
vars:
  gateway_idle_timeout: 1800  # 30 minutes
```

### 3. Default

**3600 seconds (1 hour)** if neither variable is set.

The value is passed to the manager subprocess as `sys.argv[10]` (float as string)
during spawn. Once the manager starts, the timeout is fixed for its lifetime — changing
the variable on a later task does not affect an already-running manager.

---

## How It Works

### Activity Tracking

Every RPC call to the manager triggers `PlatformService.record_activity()`, which
updates `self._last_activity` to the current timestamp:

```python
def record_activity(self) -> None:
    """Record that the service was just used (reset idle clock)."""
    self._last_activity = time.time()
```

This is called automatically by `PlatformService.execute()`, `lookup_resource_id()`,
`search_api()`, and other RPC-exposed methods.

### Idle Check

The idle monitor daemon thread periodically calls `should_exit_for_idle()`:

```python
def should_exit_for_idle(self, idle_timeout: float) -> bool:
    """Return True if idle_timeout seconds have passed since last activity."""
    if idle_timeout <= 0:
        return False  # Disabled
    return (time.time() - self._last_activity) >= idle_timeout
```

When this returns `True`, the monitor calls `os._exit(0)` to terminate the
entire manager process immediately.

### Shutdown Sequence

When the idle timeout fires:

```
Idle monitor detects should_exit_for_idle() == True
  │
  ├── Log: "Idle timeout reached, shutting down manager"
  ├── os._exit(0) — immediate process termination
  │
  └── On next RPC attempt from an action plugin:
      ├── Connection to Unix socket fails (ECONNREFUSED)
      ├── Connection plugin detects stale socket
      └── Spawns a new manager subprocess automatically
```

The `os._exit(0)` call bypasses normal Python cleanup (atexit handlers, finally
blocks). This is intentional — the manager's socket file and HTTP session are
cleaned up by the OS when the process exits. The socket file is unlinked by the
owner-PID watchdog or by `cleanup_old_socket()` on the next spawn.

---

## Polling Behavior

The idle monitor does not sleep for the full timeout duration. Instead, it uses
an adaptive polling interval:

```python
def _compute_poll_interval(idle_timeout: float) -> int:
    return max(5, min(60, int(idle_timeout / 10)))
```

| idle_timeout | Poll interval | Rationale |
|-------------|---------------|-----------|
| 3600s (1hr) | 360s (6min) | Large timeout, no need to poll frequently |
| 600s (10min) | 60s (1min) | Capped at maximum |
| 60s (1min) | 5s | Floored at minimum |
| 30s | 5s | Minimum floor applies |
| 0 | N/A | Disabled — monitor never starts |

### Environment Variable Override

For testing, set `ANSIBLE_PLATFORM_IDLE_POLL_SECONDS` to override the adaptive
calculation:

```bash
export ANSIBLE_PLATFORM_IDLE_POLL_SECONDS=2  # Poll every 2 seconds (testing only)
```

---

## Disabling Auto-Shutdown

Set the timeout to `0` to disable auto-shutdown entirely:

```yaml
- name: Long-running play with persistent manager
  hosts: gateway
  vars:
    ansible_platform_manager_idle_timeout: 0  # Never auto-shutdown
  tasks:
    - ansible.platform.user:
        username: alice
        state: present
    # ... many tasks over hours ...
```

When disabled:
- The idle monitor thread is not started
- The manager stays alive until the parent Ansible process exits (detected by
  the owner-PID watchdog, which polls every 3 seconds)
- If the parent process crashes without the watchdog detecting it, the manager
  process becomes orphaned and must be killed manually

For most use cases, the default 1-hour timeout is appropriate. Only disable it
for very long-running plays where you're certain cleanup will happen.

---

## Edge Cases

### Manager spawned with different timeout than current task

The timeout is set at spawn time. If task 1 spawns the manager with
`idle_timeout: 3600` and task 5 sets `idle_timeout: 300`, the manager still
uses `3600`. To change the timeout, the manager must be restarted (stop the
current play, or the idle timeout must fire naturally).

### Race between idle timeout and next task

If the idle timeout fires between tasks (e.g., a play has a long `pause` between
tasks), the next task's action plugin detects the dead socket and spawns a fresh
manager. This adds one-time latency (~1-2 seconds) for the first task after
respawn but is otherwise transparent.

### Multiple plays in the same playbook

Each play gets its own manager subprocess (keyed by connection credentials). The
idle timeout applies independently to each manager. When a play ends, if the
next play uses the same credentials, it reuses the existing manager (if still
alive) or spawns a new one.

### Owner-PID watchdog vs idle timeout

Two independent shutdown mechanisms run concurrently:
- **Owner-PID watchdog**: polls parent PID every 3 seconds, exits when parent dies
- **Idle timeout monitor**: polls activity timestamp, exits after idle period

Whichever triggers first wins. The watchdog catches crashes; the idle timeout
catches forgotten processes after clean Ansible exits where the manager was not
explicitly shut down.

---

## Testing

### Unit Tests

Location: `tests/unit/plugins/manager/test_idle_timeout.py`

Covers:
- `_compute_poll_interval()` — boundary values (5s floor, 60s ceiling, linear range)
- `should_exit_for_idle()` — returns False when active, True when expired, False when disabled (0)
- `record_activity()` — resets the idle clock

### Quick Manual Test

```bash
# Set a very short idle timeout and watch the manager exit
export ANSIBLE_PLATFORM_IDLE_POLL_SECONDS=2

ansible-playbook -e "ansible_platform_manager_idle_timeout=10" test_play.yml

# After the play completes, the manager should exit within ~10 seconds
# Check: no leftover processes
ps aux | grep manager_process
# Check: socket file cleaned up
ls /tmp/ansible_platform/*.sock
```

---

## Troubleshooting

### "Manager process not responding" after long pause

The idle timeout likely fired during the pause. The next task will auto-spawn a
new manager. If you need the manager to survive long pauses, increase
`ansible_platform_manager_idle_timeout` or set it to `0`.

### Orphaned manager processes

If `ps aux | grep manager_process` shows leftover processes after playbook
completion, the idle timeout and owner-PID watchdog both failed to clean up.
This can happen if:
- `idle_timeout` was set to `0` and the parent process was killed with `SIGKILL`
- The system clock jumped forward during the idle check

Kill manually: `pkill -f manager_process`

### Manager keeps restarting

If you see repeated "Spawning manager process" log messages, the idle timeout
is too short for the gap between tasks. Increase it:

```yaml
vars:
  ansible_platform_manager_idle_timeout: 7200  # 2 hours
```
