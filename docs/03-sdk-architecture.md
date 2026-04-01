# SDK Architecture

## The Core Insight

An `ansible.platform` action plugin is a function that:
1. Accepts a desired resource state as input.
2. Converges the Gateway API to that state.
3. Returns the resulting resource state.

This is structurally identical to a function call. The HTTP interaction, data
transformation, and version routing are implementation details. They live in a shared
library (the SDK) that the action plugin calls — the action plugin itself contains no
HTTP code.

This separation matters because it allows the same business logic to serve Ansible
without being coupled to the Ansible framework.

## Architecture Layers

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
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  AAP Gateway API  (https://<host>/api/gateway/v1/...)           │
└─────────────────────────────────────────────────────────────────┘
```

## The Two Connection Modes

The connection plugin (`plugins/connection/http.py`) is the traffic cop between the
action plugin layer and the manager process layer. It supports two modes that differ
only in **how long the manager process lives**:

### Direct Mode (default)

```
Task 1 → spawn manager → execute → teardown manager
Task 2 → spawn manager → execute → teardown manager
Task N → spawn manager → execute → teardown manager
```

Each task gets a fresh manager process with a new HTTP session. Clean, isolated, no
state leaks between tasks. This is the default because it works with any Ansible
connection (including `connection: local`).

Activated by: `persistent: false` (default), or no connection option set.

### Persistent Mode

```
Task 1 → spawn manager → execute ─────────────────────────────┐
Task 2 → reuse manager ────── execute                          │
Task N → reuse manager ────── execute → teardown manager       │
                              ↑                                │
                              └── same process, same HTTP session
```

The manager process is spawned on the first task and reused for all subsequent tasks
in the same play. The process socket path and auth key are stored in Ansible host facts
so the connection plugin can find and reuse it.

Activated by: `persistent: true` connection option, or
`ansible_platform_use_persistent_connection: true` in inventory/vars.

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

## The Manager Process

### What It Is

`PlatformService` is a Python class that:
- Holds a `requests.Session` (persistent HTTP connection to the Gateway)
- Detects the Gateway API version by calling `/ping`
- Caches the version detection result
- Executes resource operations using the transform mixin for the detected version
- Manages credential storage via `CredentialManager`

`PlatformService` runs inside a `PlatformManager` — a `multiprocessing.managers.BaseManager`
subclass that exposes `PlatformService` methods over a Unix domain socket. This is what
makes the RPC pattern work.

### Why a Separate Process

This architecture was designed to solve a specific class of failures observed in earlier
implementations:

**The worker crash problem**: When Ansible forks worker processes, objects like
`multiprocessing.managers.SyncManager` proxies become invalid in the child process.
Any code that holds HTTP session objects or manager proxy references in the main Ansible
process will fail after the fork.

By running the manager in a **separate subprocess** (not a thread, not a forked
Ansible worker), the manager's HTTP session lives entirely outside the Ansible fork
tree. Action plugins communicate with it only through a clean RPC interface (socket +
serialized dicts). No proxy objects are shared across fork boundaries.

### Manager Lifecycle

#### Direct mode lifecycle

```
action plugin.run()
  ├── _get_or_spawn_manager()
  │     └── spawn PlatformService subprocess
  │           └── socket: /tmp/ansible_platform/<uuid>.sock
  ├── manager.execute('find', 'user', {...})
  ├── manager.execute('create', 'user', {...})
  └── cleanup()
        └── shutdown PlatformService subprocess
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
  │     └── store socket path + authkey in ansible_facts
  ├── manager.execute(...)
  │
  Task 2..N
  ├── _get_or_spawn_manager()
  │     ├── check facts for platform_manager_socket ← found
  │     ├── verify socket file still exists
  │     ├── try ManagerRPCClient(socket, authkey)
  │     └── on failure → re-spawn (dead manager recovery)
  └── manager.execute(...)
  │
  Play ends
  └── cleanup() on last task
        └── shutdown subprocess
```

### Process-Safe Task Tracking

Multiple tasks run concurrently in Ansible. To safely shut down the manager only after
all tasks in a play have completed (not after the first task finishes), the framework
uses a **file-based reference counter**:

- Directory: `/tmp/ansible_platform_tracking/`
- One file per in-flight task (named by task UUID)
- `cleanup()` removes the task's file and shuts down the manager only when the
  directory is empty (no other tasks running)
- File locking prevents race conditions between concurrent workers

## The RPC Interface

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
```

This proxy serializes Python objects to plain dicts before sending them over the socket
(no complex objects cross the process boundary). The manager deserializes them,
executes the operation, serializes the result, and returns.

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

## Directory Structure

```
ansible_collections/ansible/platform/
│
├── plugins/
│   ├── action/
│   │   ├── base_action.py          ← BaseResourceActionPlugin
│   │   ├── user.py                 ← ActionModule(BaseResourceActionPlugin)
│   │   └── ... (21 more)
│   │
│   ├── connection/
│   │   └── http.py                 ← Connection (direct/persistent dispatcher)
│   │
│   ├── modules/
│   │   ├── user.py                 ← DOCUMENTATION + EXAMPLES stub
│   │   └── ... (21 more)
│   │
│   └── plugin_utils/
│       ├── ansible_models/
│       │   ├── user.py             ← AnsibleUser dataclass (stable interface)
│       │   └── ... (21 more)
│       │
│       ├── api/
│       │   ├── v1/
│       │   │   ├── user.py         ← APIUser_v1 + UserTransformMixin_v1
│       │   │   └── ... (21 more)
│       │   └── v2/
│       │       ├── user.py         ← APIUser_v2 + UserTransformMixin_v2
│       │       └── organization.py
│       │
│       ├── manager/
│       │   ├── platform_manager.py ← PlatformService, PlatformManager
│       │   ├── rpc_client.py       ← ManagerRPCClient
│       │   ├── manager_process.py  ← subprocess entry point
│       │   └── process_manager.py  ← spawn/wait/cleanup helpers
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
│   └── integration/targets/        ← ansible-test integration
│
└── extensions/molecule/            ← mock-based idempotency tests
    ├── users_mock/
    ├── organization_mock/
    └── ... (22 scenarios)
```

## Why Not a Single Process?

It might seem simpler to run everything in the action plugin's process (no RPC, no
subprocess). This was the original implementation. It was abandoned because:

1. **Fork safety**: Ansible forks worker processes. Any objects created before the fork
   (HTTP sessions, file descriptors, manager proxies) are in an inconsistent state in
   the child. The only reliable solution is to never share such objects across a fork.

2. **Connection reuse**: A long-lived HTTP session requires a process that outlives a
   single task. Action plugin processes are task-scoped. A separate manager process
   can span an entire play.

3. **Credential isolation**: The manager process holds credentials in memory. Keeping
   credentials isolated to a separate process (not shared with every Ansible worker
   forked from the controller) is better security hygiene.

The separate-process architecture is the right solution and is stable in production.
The `test_http.py` unit tests verify the error recovery paths (stale socket, dead
manager, re-spawn) to ensure the complexity does not become a reliability risk.
