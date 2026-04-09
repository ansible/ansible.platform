# SDK Architecture

## Table of Contents

1. [The Core Insight](#section-1-the-core-insight)
2. [Architecture Layers](#section-2-architecture-layers)
3. [The Two Connection Modes](#section-3-the-two-connection-modes)
4. [The Manager Process](#section-4-the-manager-process)
5. [Manager Auto-Shutdown and Idle Timeout](#section-5-manager-auto-shutdown-and-idle-timeout)
6. [The RPC Interface](#section-6-the-rpc-interface)
7. [Directory Structure](#section-7-directory-structure)
8. [Why a Separate Process](#section-8-why-a-separate-process)

---

## SECTION 1: The Core Insight

An `ansible.platform` action plugin is a function that:
1. Accepts a desired resource state as input.
2. Converges the Gateway API to that state.
3. Returns the resulting resource state.

This is structurally identical to a function call. The HTTP interaction, data
transformation, and version routing are implementation details. They live in a shared
library (the SDK) that the action plugin calls — the action plugin itself contains no
HTTP code.

This separation matters because it allows the same business logic to serve Ansible
without being coupled to the Ansible framework. It enables reusability: Ansible
action plugins, MCP tools, CLI utilities, and future consumers all call the same SDK.

---

## SECTION 2: Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│  Playbook (YAML tasks)                                          │
│     state: present / absent / exists / enforced                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │ task args
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Action Plugins  (plugins/action/)                     │
│                                                                 │
│  22 concrete plugins, all extending BaseResourceActionPlugin.   │
│  Responsibility: validate input, detect operation, call manager,│
│  validate output, format result dict.                           │
│  No HTTP code. No API-version logic. No data transformation.    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ manager.execute(operation, module, data)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Connection Plugin  (plugins/connection/http.py)       │
│                                                                 │
│  Dispatcher: routes to direct or persistent client.             │
│  Holds manager socket path in Ansible facts for session reuse.  │
│  Supports both persistent and direct connection modes.          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Unix domain socket RPC
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: Manager Process  (plugins/plugin_utils/manager/)      │
│                                                                 │
│  PlatformService — runs in a separate subprocess.               │
│  Holds the requests.Session (persistent HTTP connection).       │
│  Loads correct (AnsibleClass, APIClass, MixinClass) via registry│
│  Executes transform: Ansible dict → APIModel → HTTP → AnsibleDict│
│  Manages idle timeout and auto-shutdown.                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  AAP Gateway API  (https://<host>/api/gateway/v1/...)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## SECTION 3: The Two Connection Modes

The connection plugin (`plugins/connection/http.py`) is the traffic cop between the
action plugin layer and the manager process layer. It supports two modes that differ
only in **how long the manager process lives**:

### Direct Mode (default)

```
Task 1
  ├── spawn manager subprocess
  ├── RPC: execute operation 1
  └── shutdown manager + cleanup socket

Task 2
  ├── spawn manager subprocess (new)
  ├── RPC: execute operation 2
  └── shutdown manager + cleanup socket

Task N
  ├── spawn manager subprocess (new)
  ├── RPC: execute operation N
  └── shutdown manager + cleanup socket
```

Each task gets a fresh manager process with a new HTTP session. Clean, isolated, no
state leaks between tasks. This is the default because it works with any Ansible
connection (including `connection: local`).

Activated by: `persistent: false` (default), or no connection option set.

**Sequence diagram for direct mode:**

```
Action Plugin        Connection Plugin    Manager Process      Gateway API
     │                     │                    │                    │
     ├─ execute()──────────┤                    │                    │
     │                     ├─ spawn────────────>│                    │
     │                     │                    │                    │
     │                     │ RPC: execute       │                    │
     │                     ├───────────────────>│                    │
     │                     │                    ├─ HTTP POST/PATCH──>│
     │                     │                    │ /api/gateway/v1/..│
     │                     │                    │<──────────────────┤
     │                     │<───────────────────┤ return result      │
     │                     │ result dict        │                    │
     │                     ├─ shutdown─────────>│                    │
     │<────────────────────┤ (cleanup socket)   │                    │
     │  result             │                    │                    │
```

### Persistent Mode

```
Task 1
  ├── spawn manager subprocess
  ├── store socket path in ansible_facts
  ├── RPC: execute operation 1
  ├── leave manager running
  └── (manager stays alive for subsequent tasks)

Task 2
  ├── find manager via ansible_facts
  ├── verify socket exists
  ├── RPC: execute operation 2
  └── (manager continues running)

Task N
  ├── find manager via ansible_facts
  ├── verify socket exists
  ├── RPC: execute operation N
  └── (manager continues running)

Play ends
  └── shutdown manager (final cleanup)
```

The manager process is spawned on the first task and reused for all subsequent tasks
in the same play. The process socket path and auth key are stored in Ansible host facts
so the connection plugin can find and reuse it.

Activated by: `persistent: true` connection option, or
`ansible_platform_use_persistent_connection: true` in inventory/vars.

**Sequence diagram for persistent mode:**

```
Action Plugin 1      Connection Plugin    Manager Process      Gateway API
     │                     │                    │                    │
     ├─ execute()──────────┤                    │                    │
     │                     ├─ spawn────────────>│                    │
     │                     │<──────────────────┤ socket + authkey    │
     │                     │                    ├─ HTTP POST────────>│
     │                     │ RPC: execute       │ /api/gateway/v1/..│
     │                     ├───────────────────>│<──────────────────┤
     │                     │<───────────────────┤ return result      │
     │                     │ result dict        │                    │
     │<────────────────────┤ (manager still running)                │

Action Plugin 2
     │                     │                    │                    │
     ├─ execute()──────────┤                    │                    │
     │                     ├─ RPC: execute     │                    │
     │                     ├───────────────────>│                    │
     │                     │                    ├─ HTTP PATCH──────>│
     │                     │                    │ /api/gateway/v1/..│
     │                     │                    │<──────────────────┤
     │                     │<───────────────────┤ return result      │
     │<────────────────────┤                    │                    │
     │  result             │ (manager persists) │                    │

[Play ends]
     │                     │                    │                    │
     │                     ├─ shutdown─────────>│                    │
     │                     │                    │ cleanup + exit     │
     │                     │<──────────────────┤ (socket deleted)   │
```

**Performance benefit**: Eliminates per-task authentication round-trips. For plays
with 20+ tasks, this is a 50–75% reduction in total playbook time.

### Mode Decision Logic

```python
# Connection plugin: get_client() dispatcher
def get_client(self, task_vars, gateway_config):
    use_persistent = self._resolve_persistent_flag(task_vars)
    if use_persistent:
        return self._get_persistent_client(task_vars, gateway_config)
    else:
        return self._get_direct_client(task_vars, gateway_config)
```

Resolution order for the `persistent` flag:
1. Connection plugin option `persistent` (set in inventory `[group:vars]` or task)
2. Task var `ansible_platform_use_persistent_connection`
3. Task var `ansible_platform_persistent`
4. Hostvar `ansible_platform_use_persistent_connection` (per-host)
5. Default: `false` (direct mode)

---

## SECTION 4: The Manager Process

### What It Is

`PlatformService` is a Python class that:
- Holds a `requests.Session` (persistent HTTP connection to the Gateway)
- Detects the Gateway API version by calling `/api/gateway/v1/ping`
- Caches the version detection result
- Executes resource operations using the transform mixin for the detected version
- Manages credential storage via `CredentialManager`
- Monitors idle time and auto-terminates after timeout

`PlatformService` runs inside a `PlatformManager` — a `multiprocessing.managers.BaseManager`
subclass that exposes `PlatformService` methods over a Unix domain socket. This is what
makes the RPC pattern work.

### Manager Lifecycle

#### Direct mode lifecycle

```
action plugin.run()
  ├── _get_or_spawn_manager()
  │     └── spawn PlatformService subprocess
  │           ├── socket: /tmp/ansible_platform/<uuid>.sock
  │           └── _idle_monitor thread starts
  ├── manager.execute('find', 'user', {...})
  ├── manager.execute('create', 'user', {...})
  └── cleanup()
        └── shutdown PlatformService subprocess
              ├── kill _idle_monitor thread
              └── delete socket file
```

#### Persistent mode lifecycle

```
Play starts
  │
  Task 1
  ├── _get_or_spawn_manager()
  │     ├── check facts for platform_manager_socket
  │     ├── not found → spawn new PlatformService subprocess
  │     │             → _idle_monitor thread starts
  │     └── store socket path + authkey in ansible_facts
  ├── manager.execute(...)
  │
  Task 2..N
  ├── _get_or_spawn_manager()
  │     ├── check facts for platform_manager_socket ← found
  │     ├── verify socket file still exists
  │     ├── try ManagerRPCClient(socket, authkey)
  │     └── on failure → re-spawn (dead manager recovery)
  │           └── _idle_monitor thread starts on new process
  └── manager.execute(...)
  │
  Play ends
  └── cleanup() on last task
        ├── shutdown subprocess
        ├── kill _idle_monitor thread
        └── delete socket file
```

### Persistent Manager Shutdown — Callback Plugin

Persistent managers are shut down by the `platform_manager_cleanup` callback plugin
(`plugins/callback/platform_manager_cleanup.py`), which Ansible auto-loads from the
collection with zero configuration (`CALLBACK_NEEDS_ENABLED = False`).

The callback fires two hooks in the Ansible main process:

- `v2_playbook_on_play_end` — fires when each play finishes
- `v2_playbook_on_stats` — fires at the very end of the playbook (belt-and-suspenders,
  covers plays that were skipped and never triggered `play_end`)

On each hook it scans `/tmp/ansible_platform/` for `.meta` JSON files written next to
each socket at spawn time. For each live manager found it:

1. Attempts a graceful RPC shutdown (`client.shutdown_manager()`)
2. Waits up to 5 seconds for the process to exit cleanly
3. Escalates to `SIGTERM` if still running
4. Escalates to `SIGKILL` if still running after 1 more second
5. Removes the `.meta` and socket files

Because the callback runs in the **main Ansible process** (not a forked worker), it
always fires at the right moment regardless of how many worker forks were used.

`cleanup()` in the action plugin only handles **ephemeral (direct mode)** managers —
those are torn down immediately after the single task that spawned them. Persistent
managers are left entirely to the callback plugin.

---

## SECTION 5: Manager Auto-Shutdown and Idle Timeout

The manager process supports an **idle timeout** setting that prevents orphaned processes
from accumulating across long playbook runs or multiple invocations.

### How It Works

The manager process includes a daemon thread (`_idle_monitor`) that tracks the time
since the last RPC call. If the manager receives no requests for longer than the
configured timeout, it automatically shuts itself down and removes its socket file.

```
Manager spawned at 14:00:00
  │
  ├─ _idle_monitor starts, listening for activity
  │
  ├─ 14:00:01: Task 1 executes → resets idle timer to 0
  ├─ 14:00:05: Task 2 executes → resets idle timer to 0
  │
  ├─ No more tasks...
  │
  ├─ 14:00:50: Idle timer reaches 50 seconds (< 3600s timeout)
  │ ... continue waiting ...
  │
  ├─ 15:01:00: Idle timer reaches 3600 seconds (>= timeout)
  │
  └─ Auto-shutdown triggered:
      ├── Log: "Idle timeout reached, shutting down"
      ├── Close HTTP session
      ├── Remove socket file: /tmp/ansible_platform/<uuid>.sock
      └── Process exits
```

### Configuration

The idle timeout is configured via one of three methods (in resolution order):

1. **Task variable**: `ansible_platform_manager_idle_timeout` (seconds)
   ```yaml
   - name: Task with custom idle timeout
     ansible.platform.user:
       username: alice
       state: present
     vars:
       ansible_platform_manager_idle_timeout: 7200  # 2 hours
   ```

2. **Gateway variable**: `gateway_idle_timeout` (seconds)
   ```yaml
   vars:
     gateway_idle_timeout: 1800  # 30 minutes
   ```

3. **Default**: 3600 seconds (1 hour)

### Idle Monitor Polling

The `_idle_monitor` daemon thread does not sleep for the full timeout. Instead, it polls
adaptively:

- **Polling interval** = 10% of `idle_timeout`, bounded to [5 seconds, 60 seconds]
- Example: If `idle_timeout: 3600`, polling interval = 360 seconds
- Example: If `idle_timeout: 60`, polling interval = 5 seconds (minimum)

This balances responsiveness (small timeouts trigger quickly) with CPU efficiency (large
timeouts do not wake the thread excessively).

### Disabling Auto-Shutdown

Set the timeout to 0 to disable auto-shutdown:

```yaml
- name: Long-running play with persistent manager
  hosts: gateway
  vars:
    ansible_platform_manager_idle_timeout: 0  # Never auto-shutdown
  tasks:
    - name: Task 1
      ansible.platform.user:
        username: alice
        state: present

    # ... many tasks ...

    - name: Task N
      ansible.platform.organization:
        name: "Engineering"
        state: present

    - name: Manual cleanup (if idle_timeout: 0)
      connection: ansible.platform.http
      gather_facts: no
      tasks:
        - platform_manager_cleanup:  # Custom cleanup task
```

### Motivation: Preventing Orphaned Processes

Without idle timeout, the following scenario could occur:

1. Long-running Ansible playbook (multi-site deployment)
2. Plays 1-10 complete, manager spawned on play 1, persisted through play 10
3. Play 11 scheduled to run in 2 hours
4. Manager remains in memory, holding HTTP session, credentials, file descriptor for socket
5. If the socket is on NFS or slow storage, this consumes resources

The idle timeout prevents this:

1. Play 10 completes at 14:00
2. Manager detects no activity for 3600s
3. Auto-shutdown at 15:00
4. Play 11 at 16:00 → new manager spawned (clean state)

This is especially important in GitOps pipelines where playbooks run on tight schedules.

### Implementation Details

The idle monitor thread:
- Is a daemon thread (does not block process exit)
- Runs in the manager subprocess (not in Ansible)
- Tracks `last_rpc_time` in a thread-safe manner (lock around RPC handler)
- Periodically checks: `time.time() - last_rpc_time >= idle_timeout`
- On timeout, logs a message and calls `os._exit(0)` (immediate, no cleanup)

The socket file is cleaned up by the next task that detects it is stale, or by the
connection plugin's periodic socket validation.

---

## SECTION 6: The RPC Interface

Action plugins never import or call `PlatformService` directly. They go through
`ManagerRPCClient`, a thin proxy object:

```python
class ManagerRPCClient:
    def execute(self, operation, module_name, ansible_data):
        """Serialize ansible_data to dict, send via RPC, return result dict."""
        ...

    def lookup_resource_id(self, resource_type, name, **kwargs):
        """Resolve a resource name to its integer ID."""
        ...

    def search_api(self, query, resource_type):
        """Search the Gateway API using a search query."""
        ...
```

This proxy serializes Python objects to plain dicts before sending them over the socket
(no complex objects cross the process boundary). The manager deserializes them,
executes the operation, serializes the result, and returns.

### The execute() Flow

The full `execute()` flow inside the manager:

```
manager.execute('create', 'user', {'username': 'alice', ...})
  │
  ├── 1. registry.find_best_version(api_version, 'user')
  ├── 2. loader.load_classes('user', best_version)
  │         → (AnsibleUser, APIUser_v1, UserTransformMixin_v1)
  ├── 3. AnsibleUser(**ansible_data) → ansible_instance
  ├── 4. mixin.from_ansible_data(ansible_instance, context)
  │         → APIUser_v1(username='alice', ...)
  ├── 5. mixin.get_endpoint_operations()['create']
  │         → POST /api/gateway/v1/users/
  ├── 6. HTTP POST → response
  ├── 7. mixin.from_api(response, context)
  │         → AnsibleUser(id=42, username='alice', ...)
  └── 8. return dataclasses.asdict(ansible_instance)
```

### The search_api() Method

The `search_api()` method enables lookups via the manager subprocess without triggering
SSL fork crashes (see "Why a Separate Process" section below). This method is used by
the `gateway_api` lookup plugin.

```python
def search_api(self, query, resource_type):
    """
    Search the Gateway API using a search query.
    
    Args:
        query (str): Search query (e.g., 'username:alice')
        resource_type (str): Resource type (e.g., 'user')
    
    Returns:
        list[dict]: List of matching resources in user-model format
    """
    # Implementation in manager (safe from SSL fork issues)
    # 1. Build API search request
    # 2. Execute HTTP GET with search params
    # 3. Transform response to user-model format
    # 4. Return results
```

**Example usage in a lookup plugin:**

```python
# plugins/lookup/gateway_api.py
class LookupModule(LookupBase):
    def run(self, terms, **kwargs):
        rpc_client = get_rpc_client()
        results = rpc_client.search_api(
            query=terms[0],
            resource_type=kwargs.get('resource_type', 'user')
        )
        return [r['id'] for r in results]
```

This allows dynamic lookups (e.g., "find all users whose username contains 'admin'")
without spawning additional processes or triggering SSL fork safety issues.

---

## SECTION 7: Directory Structure

```
ansible_collections/ansible/platform/
│
├── plugins/
│   ├── action/
│   │   ├── base_action.py          ← BaseResourceActionPlugin
│   │   ├── user.py                 ← ActionModule(BaseResourceActionPlugin)
│   │   ├── organization.py
│   │   ├── http_port.py
│   │   └── ... (19 more)
│   │
│   ├── connection/
│   │   └── http.py                 ← Connection (direct/persistent dispatcher)
│   │
│   ├── modules/
│   │   ├── user.py                 ← DOCUMENTATION + EXAMPLES stub
│   │   ├── organization.py
│   │   └── ... (20 more)
│   │
│   ├── lookup/
│   │   ├── gateway_api.py           ← API search via search_api() RPC method
│   │   └── ...
│   │
│   └── plugin_utils/
│       ├── ansible_models/
│       │   ├── user.py             ← AnsibleUser dataclass (stable interface)
│       │   ├── organization.py
│       │   └── ... (20 more)
│       │
│       ├── api/
│       │   ├── v1/
│       │   │   ├── user.py         ← APIUser_v1 + UserTransformMixin_v1
│       │   │   ├── organization.py
│       │   │   └── ... (20 more)
│       │   ├── v2/
│       │   │   ├── user.py         ← APIUser_v2 + UserTransformMixin_v2
│       │   │   └── ... (subset of v1 entities)
│       │   └── v3/
│       │       ├── user.py         ← APIUser_v3 with RBAC changes
│       │       └── ... (subset with new model)
│       │
│       ├── manager/
│       │   ├── platform_manager.py ← PlatformService, PlatformManager
│       │   ├── rpc_client.py       ← ManagerRPCClient
│       │   ├── manager_process.py  ← subprocess entry point
│       │   ├── process_manager.py  ← spawn/wait/cleanup helpers
│       │   └── idle_monitor.py     ← idle timeout thread logic
│       │
│       └── platform/
│           ├── registry.py         ← APIVersionRegistry
│           ├── loader.py           ← DynamicClassLoader
│           ├── base_transform.py   ← BaseTransformMixin (protocol)
│           ├── types.py            ← EndpointOperation, TransformContext
│           ├── config.py           ← GatewayConfig
│           ├── base_client.py      ← BaseAPIClient (abstract)
│           ├── direct_client.py    ← DirectHTTPClient
│           ├── credential_manager.py
│           └── exceptions.py
│
├── tests/
│   ├── unit/                       ← pytest, no network
│   │   ├── test_http.py            ← Connection plugin, manager lifecycle
│   │   ├── test_manager.py         ← Manager process, RPC, idle timeout
│   │   ├── test_transforms.py      ← Version-specific transforms
│   │   └── ...
│   └── integration/targets/        ← ansible-test integration
│
└── extensions/molecule/            ← mock-based idempotency tests
    ├── users_mock/
    ├── organizations_mock/
    ├── service_clusters_mock/
    └── ... (22 scenarios)
```

---

## SECTION 8: Why a Separate Process

This architecture was designed to solve a specific class of failures observed in earlier
implementations:

### The Worker Crash Problem

**When Ansible forks worker processes**, objects like `multiprocessing.managers.SyncManager`
proxies become invalid in the child process. Any code that holds HTTP session objects or
manager proxy references in the main Ansible process will fail after the fork.

Example of the problem:

```python
# In action plugin (runs in Ansible worker process)
self.manager_proxy = connect_to_manager()  # ← Proxy valid here

# Ansible forks a new worker
# ... worker process continues ...

# In forked worker, the proxy is stale (bad file descriptor, broken connection)
self.manager_proxy.execute(...)  # ← Crashes!
```

By running the manager in a **separate subprocess** (not a thread, not a forked
Ansible worker), the manager's HTTP session lives entirely outside the Ansible fork
tree. Action plugins communicate with it only through a clean RPC interface (socket +
serialized dicts). No proxy objects are shared across fork boundaries.

### The macOS + Python 3.12 SSL Fork-Safety Issue

**On macOS with Python 3.12+**, SSL initialization in a forked process triggers `SIGABRT`.

The issue: Python's SSL module initializes OpenSSL state when first imported. When a
process forks after SSL initialization, the child inherits OpenSSL state that is not
thread-safe. Attempting to use SSL in the child (e.g., `requests.Session.post()`)
triggers OpenSSL's fork-safety checks, which call `abort()`.

```python
# In action plugin (parent process)
import requests
self.session = requests.Session()  # ← SSL initialized here

# Ansible forks a worker
# ... in child process ...

response = self.session.post(...)  # ← SIGABRT (macOS Python 3.12+)
```

The manager subprocess approach solves this by running all SSL/HTTP in a process that
is **never forked**. The manager is spawned via `multiprocessing.Process` (which does
not invoke `fork()` on systems that support `spawn` or `forkserver`). All SSL
initialization happens inside the manager, in a safe context.

```python
# Action plugin: no SSL here
socket_path = spawn_manager()  # ← Fork happens before SSL init

# Manager subprocess: safe to use SSL
import requests
self.session = requests.Session()  # ← SSL init safe here (not forked)
```

### Why Fork Safety Matters

Ansible commonly forks workers in these scenarios:

- **Parallel task execution** with `forks: N` (default: 5)
- **Delegation** — tasks run on different hosts in forked workers
- **Blocks** — task blocks may run in child workers
- **Retries** — failed tasks may be retried in a new worker

Without the separate process, any of these would trigger the crash.

### Connection Reuse

A long-lived HTTP session requires a process that outlives a single task. Action plugin
processes are task-scoped. A separate manager process can span an entire play (in
persistent mode), reusing the HTTP session and connection pool across 10s or 100s of
tasks.

This is why persistent mode achieves 50–75% speedup: the manager reuses the connection,
eliminating per-task TLS handshakes and authentication.

### Credential Isolation

The manager process holds credentials in memory. Keeping credentials isolated to a
separate process (not shared with every Ansible worker forked from the controller) is
better security hygiene:

- Credentials are not copied into each forked child
- Credentials are not persisted in Ansible's worker memory
- Only the manager subprocess, running as a single process, holds the credential

The RPC boundary (Unix domain socket) does not transmit credentials — they remain in
the manager's memory.

---

## Summary: Direct vs. Persistent Mode

| Aspect | Direct Mode | Persistent Mode |
|--------|-------------|-----------------|
| **Manager lifetime** | Per task | Per play |
| **HTTP session reuse** | No (new each task) | Yes (shared across tasks) |
| **Performance** | Baseline | 50-75% faster (20+ tasks) |
| **Idle timeout** | Not applicable | Configurable (default 3600s) |
| **Isolation** | Complete per task | Shared across play |
| **Default behavior** | Yes | Opt-in via `persistent: true` |
| **Supported connections** | All (local, ssh, etc.) | Requires persistent connection |

The separate process architecture is the right solution and is stable in production.
The unit tests in `test_http.py` and `test_manager.py` verify the error recovery
paths (stale socket, dead manager, re-spawn, idle timeout) to ensure the complexity
does not become a reliability risk.
