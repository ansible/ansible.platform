# Foundation Components

This document is the implementation reference for every core component in `ansible.platform`. Read this before making changes to the framework layer.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Directory Structure](#directory-structure)
3. [Component 1 — EndpointOperation and TransformContext](#component-1--endpointoperation-and-transformcontext)
4. [Component 2 — APIVersionRegistry](#component-2--apiversionregistry)
5. [Component 3 — DynamicClassLoader](#component-3--dynamicclassloader)
6. [Component 4 — BaseTransformMixin](#component-4--basetransformmixin)
7. [Component 5 — GatewayConfig](#component-5--gatewayconfig)
8. [Component 6 — PlatformService](#component-6--platformservice)
9. [Component 7 — PlatformManager](#component-7--platformmanager)
10. [Component 8 — ManagerRPCClient](#component-8--managerrpcclient)
11. [Component 9 — BaseResourceActionPlugin](#component-9--baseresourceactionplugin)
12. [Component 10 — Manager Process Entry Point](#component-10--manager-process-entry-point)
13. [Component 11 — Connection Plugin (http.py)](#component-11--connection-plugin-httppy)
14. [Manager Lifecycle](#manager-lifecycle)
15. [Testing the Foundation](#testing-the-foundation)

---

## Architecture Overview

### High-Level Flow Diagram

```
PLAYBOOK TASK 1
    ↓
1. Action Plugin calls connection.get_client()
    ↓
2. Connection creates Manager (if persistent mode)
    ↓
3. Manager detects API version, loads registry
    ↓
4. Action Plugin validates input (ArgumentSpec)
    ↓
5. Creates Ansible dataclass, sends to Manager via RPC
    ↓
6. Manager transforms (Ansible → API)
    ↓
7. Manager calls Platform API
    ↓
8. Manager transforms (API → Ansible)
    ↓
9. Action Plugin validates output, returns

PLAYBOOK TASK 2+ reuse same Manager (persistent connection)
```

### Component Responsibility Table

| Component | Location | Responsibility |
|-----------|----------|-----------------|
| `EndpointOperation`, `TransformContext` | `plugins/plugin_utils/platform/types.py` | Shared operation and context types |
| `APIVersionRegistry` | `plugins/plugin_utils/platform/registry.py` | Dynamic version/module discovery |
| `DynamicClassLoader` | `plugins/plugin_utils/platform/loader.py` | Load versioned classes with caching |
| `BaseTransformMixin` | `plugins/plugin_utils/platform/base_transform.py` | Transformation protocol + defaults |
| `GatewayConfig` | `plugins/plugin_utils/platform/config.py` | Connection config dataclass |
| `PlatformService` | `plugins/plugin_utils/manager/platform_manager.py` | Core service: version detection, CRUD, HTTP |
| `PlatformManager` | `plugins/plugin_utils/manager/platform_manager.py` | RPC server (BaseManager subclass) |
| `ManagerRPCClient` | `plugins/plugin_utils/manager/rpc_client.py` | RPC client (thin proxy) |
| `BaseResourceActionPlugin` | `plugins/action/base_action.py` | Action plugin base class |
| Manager Process | `plugins/plugin_utils/manager/manager_process.py` | Subprocess entry point + idle monitoring |
| Connection Plugin | `plugins/connection/http.py` | Dispatcher between action plugins and manager |

---

## Directory Structure

```
plugins/plugin_utils/
├── platform/
│   ├── __init__.py
│   ├── types.py                 EndpointOperation, TransformContext
│   ├── registry.py              APIVersionRegistry
│   ├── loader.py                DynamicClassLoader
│   ├── base_transform.py        BaseTransformMixin (protocol)
│   ├── config.py                GatewayConfig, extract_gateway_config()
│   ├── base_client.py           BaseAPIClient (abstract)
│   ├── direct_client.py         DirectHTTPClient (ephemeral)
│   ├── credential_manager.py
│   ├── retry.py
│   ├── exceptions.py
│   └── utils.py
├── manager/
│   ├── __init__.py
│   ├── platform_manager.py      PlatformService, PlatformManager
│   ├── rpc_client.py            ManagerRPCClient
│   ├── manager_process.py       subprocess entry point
│   └── process_manager.py       spawn/wait/cleanup helpers
└── ansible_models/              AnsibleFoo dataclasses
api/
├── v1/
│   ├── __init__.py
│   └── user.py                  APIUser_v1, UserTransformMixin_v1
├── v2/
│   ├── __init__.py
│   └── user.py                  APIUser_v2, UserTransformMixin_v2
└── ...
plugins/action/
├── __init__.py
└── base_action.py               BaseResourceActionPlugin (FOUNDATION)
plugins/connection/
├── __init__.py
└── http.py                      Dispatcher, persistent mode support
```

---

## Component 1 — EndpointOperation and TransformContext

**File**: `plugins/plugin_utils/platform/types.py`

These types are shared across all components. `EndpointOperation` describes a single API call. `TransformContext` carries runtime state into the transform mixin.

```python
@dataclass
class EndpointOperation:
    method: str                         # 'GET', 'POST', 'PATCH', 'DELETE'
    path: str                           # e.g. '/api/gateway/v1/users/'
    operation_type: str = 'primary'     # 'primary' or 'secondary'
    depends_on: Optional[str] = None    # run after this operation name
    order: int = 1                      # execution order for secondary ops

@dataclass
class TransformContext:
    manager: Any                        # PlatformService instance
    session: Any                        # requests.Session
    cache: Dict[str, Any]              # Lookup cache
    operation: str                      # 'create', 'update', 'delete', 'find'
    api_version: str                    # e.g. '1'
    check_mode: bool = False
    include_nulls_for_update: bool = False  # Include null fields in PATCH (for enforced state)
```

---

## Component 2 — APIVersionRegistry

**File**: `plugins/plugin_utils/platform/registry.py`

Scans `plugins/plugin_utils/api/` on startup and builds the version index. No hardcoded version lists anywhere.

### What it does

On `__init__`, walks the `api/` directory:
```
api/v1/user.py        → version '1', module 'user'
api/v1/org.py         → version '1', module 'org'
api/v2/user.py        → version '2', module 'user'
```

Builds two indexes:
```python
self.versions = {
    '1': ['user', 'org', 'team', ...],
    '2': ['user', 'org'],
}
self.module_versions = {
    'user': ['1', '2'],
    'org':  ['1', '2'],
    'team': ['1'],
    ...
}
```

### Key method: `find_best_version`

```python
def find_best_version(self, requested_version: str, module_name: str) -> Optional[str]:
    available = self.module_versions.get(module_name, [])
    if not available:
        return None

    # 1. Exact match
    if requested_version in available:
        return requested_version

    # 2. Closest lower version (backward compatible)
    lower = [v for v in available if v < requested_version]
    if lower:
        return max(lower)

    # 3. Closest higher version (with warning)
    higher = [v for v in available if v > requested_version]
    if higher:
        best = min(higher)
        logger.warning(
            "Module '%s' has no version <= '%s'. Using closest higher version '%s'.",
            module_name, requested_version, best
        )
        return best

    return None
```

### Supporting methods

```python
def get_supported_versions(self) -> List[str]:
    """Return all discovered version numbers."""

def get_latest_version(self) -> str:
    """Return the highest discovered version number."""
```

---

## Component 3 — DynamicClassLoader

**File**: `plugins/plugin_utils/platform/loader.py`

Uses `importlib` to load `(AnsibleClass, APIClass, MixinClass)` for a given module name and API version. Results are cached.

```python
class DynamicClassLoader:
    def __init__(self, registry: APIVersionRegistry):
        self.registry = registry
        self._cache: Dict[str, tuple] = {}

    def load_classes_for_module(
        self, module_name: str, api_version: str
    ) -> Tuple[Type, Type, Type]:
        """Return (AnsibleClass, APIClass, MixinClass) for the given module and version."""

        best_version = self.registry.find_best_version(api_version, module_name)
        if best_version is None:
            raise ValueError(
                f"No compatible API version found for module '{module_name}'"
            )

        cache_key = f"{module_name}_{best_version}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        pascal = _to_pascal_case(module_name)

        # Load Ansible model: ansible_models/<module_name>.py
        ansible_mod = importlib.import_module(
            f"ansible_collections.ansible.platform.plugins.plugin_utils"
            f".ansible_models.{module_name}"
        )
        AnsibleClass = getattr(ansible_mod, f"Ansible{pascal}")

        # Load API model and mixin: api/v<N>/<module_name>.py
        api_mod = importlib.import_module(
            f"ansible_collections.ansible.platform.plugins.plugin_utils"
            f".api.v{best_version}.{module_name}"
        )
        APIClass = getattr(api_mod, f"API{pascal}_v{best_version}")
        MixinClass = getattr(api_mod, f"{pascal}TransformMixin_v{best_version}")

        result = (AnsibleClass, APIClass, MixinClass)
        self._cache[cache_key] = result
        return result
```

---

## Component 4 — BaseTransformMixin

**File**: `plugins/plugin_utils/platform/base_transform.py`

The protocol (interface) that all transform mixins must implement. Also provides default implementations for common operations.

```python
class BaseTransformMixin:
    """Protocol / base class for all versioned transform mixins."""

    def from_ansible_data(self, ansible_instance: Any, context: TransformContext) -> Any:
        """Forward: Ansible model instance → API model instance."""
        raise NotImplementedError

    def from_api(self, api_data: dict, context: TransformContext) -> Any:
        """Reverse: API response dict → Ansible model instance."""
        raise NotImplementedError

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Return the full CRUD endpoint map for this resource and API version."""
        raise NotImplementedError

    @classmethod
    def get_lookup_field(cls) -> str:
        """Return the field name used to identify a resource uniquely (e.g. 'username')."""
        raise NotImplementedError

    @classmethod
    def get_find_list_query_params(cls, ansible_instance: Any) -> Dict[str, Any]:
        """Return query params for the list endpoint when searching for a resource."""
        lookup_field = cls.get_lookup_field()
        return {lookup_field: getattr(ansible_instance, lookup_field)}

    @classmethod
    def get_fields_to_null_for_update(cls, api_instance: Any) -> Set[str]:
        """
        Return fields that must be sent as empty strings in a PATCH request
        to clear incompatible values when resource state changes (e.g., role
        when map_type changes from role to is_superuser).

        Only affects fields the user did NOT explicitly provide in the task.
        """
        return set()
```

---

## Component 5 — GatewayConfig

**File**: `plugins/plugin_utils/platform/config.py`

A dataclass holding connection parameters. Created by the action plugin from Ansible inventory variables and passed to the manager.

```python
@dataclass
class GatewayConfig:
    base_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    oauth_token: Optional[str] = None
    verify_ssl: bool = True
    request_timeout: float = 10.0
    connection_mode: str = "standard"  # "standard" or "experimental"
    idle_timeout: float = 3600.0       # Seconds before manager auto-exits (default 1 hour)

    def __post_init__(self):
        """Normalize URL after initialization."""
        # ... normalization logic ...
```

### `idle_timeout` Field

- **Default**: `3600.0` seconds (1 hour)
- **Configurable via**:
  - Task argument: `gateway_idle_timeout` (int/float in seconds)
  - Host variable: `ansible_platform_manager_idle_timeout` (int/float in seconds)
  - Task arg takes priority over host var
- **Behavior**:
  - When set to `0`, idle timeout is disabled (manager runs indefinitely)
  - When > 0, manager subprocess polls `should_exit_for_idle()` every `_compute_poll_interval()` seconds
  - If no API calls occur for `idle_timeout` seconds, the manager exits automatically
  - This prevents long-running managers from consuming resources between plays

### `extract_gateway_config()` Function

```python
def extract_gateway_config(
    task_args: Optional[Dict[str, Any]] = None,
    host_vars: Optional[Dict[str, Any]] = None,
    required: bool = True
) -> GatewayConfig:
    """
    Extract gateway configuration from task arguments and host variables.

    Args:
        task_args: Task/command arguments (higher priority)
        host_vars: Host/inventory variables (lower priority)
        required: Whether gateway_url is required (default: True)

    Returns:
        GatewayConfig object with normalized values

    Raises:
        ValueError: If required gateway_url is missing
    """
```

Extracts (in priority order):
1. `gateway_url` or `gateway_hostname` from task args
2. `gateway_url` or `gateway_hostname` from host vars
3. `gateway_username` from task args, then host vars (or `aap_username`)
4. `gateway_password` from task args, then host vars (or `aap_password`)
5. `gateway_token` from task args, host vars (or `aap_token` if no username/password)
6. `gateway_validate_certs` (default `True`)
7. `gateway_request_timeout` (default `10.0`)
8. `platform_connection_mode` (default `"standard"`)
9. `gateway_idle_timeout` (default `3600.0`)

---

## Component 6 — PlatformService

**File**: `plugins/plugin_utils/manager/platform_manager.py`

The core of the manager process. Inherits `BaseAPIClient`. Holds the HTTP session and executes all resource operations.

### Initialization

```python
class PlatformService(BaseAPIClient):
    def __init__(self, config: GatewayConfig):
        self.config = config
        self._session: Optional[requests.Session] = None
        self._api_version: Optional[str] = None
        self._registry = APIVersionRegistry()
        self._loader = DynamicClassLoader(self._registry)
        self._credential_manager = get_credential_manager(config)
        
        # Idle-tracking state (uses monotonic clock)
        self._activity_lock = threading.Lock()
        self._last_activity_monotonic = time.monotonic()
```

### Version Detection

```python
@property
def api_version(self) -> str:
    if self._api_version is None:
        self._api_version = self._detect_api_version()
    return self._api_version

def _detect_api_version(self) -> str:
    """
    Detect platform API version dynamically.

    Detection order:
      1. GET /api/gateway/v1/ping/ — read X-API-Version header
      2. GET /api/gateway/ — parse X-API-Version header or current_version field
      3. Default to '1' if all tiers fail

    Returns:
        Version string (e.g., '1', '2')
    """
```

### `execute` Method

The main entry point for all operations:

```python
def execute(
    self,
    operation: str,
    module_name: str,
    ansible_data_dict: dict
) -> dict:
    """
    Execute a resource operation.

    Args:
        operation:  'create', 'update', 'delete', 'find'
        module_name: e.g. 'user', 'organization'
        ansible_data_dict: serialized Ansible dataclass fields

    Returns:
        dict with operation result, ready to be returned by action plugin
    """
    AnsibleClass, APIClass, MixinClass = self._loader.load_classes_for_module(
        module_name, self.api_version
    )
    context = TransformContext(
        manager=self,
        session=self.session,
        cache=self.cache,
        operation=operation,
        api_version=self.api_version,
    )

    ansible_instance = AnsibleClass(**ansible_data_dict)

    if operation == 'find':
        return self._find_resource(ansible_instance, MixinClass, context)
    elif operation == 'create':
        return self._create_resource(ansible_instance, MixinClass, context)
    elif operation == 'update':
        return self._update_resource(ansible_instance, MixinClass, context)
    elif operation == 'delete':
        return self._delete_resource(ansible_instance, MixinClass, context)
    else:
        raise ValueError(f"Unknown operation: {operation}")
```

### `lookup_resource_id` Method

Used by transform mixins to resolve names to IDs without knowing the HTTP internals:

```python
def lookup_resource_id(
    self,
    resource_type: str,
    name_or_id: Union[str, int],
    **kwargs
) -> Optional[int]:
    """
    Resolve a resource name to its integer ID.
    If name_or_id is already an integer string, return it directly.
    Otherwise, list the resource and find by name.
    """
    if str(name_or_id).isdigit():
        return int(name_or_id)

    AnsibleClass, _, MixinClass = self._loader.load_classes_for_module(
        resource_type, self.api_version
    )
    mixin = MixinClass()
    lookup_field = mixin.get_lookup_field()
    ansible_instance = AnsibleClass(**{lookup_field: name_or_id})
    context = TransformContext(manager=self, operation='find', api_version=self.api_version)
    result = self._find_resource(ansible_instance, mixin, context)
    return result.get('id') if result else None
```

### `search_api` Method

Used by the `gateway_api` lookup plugin to perform API searches without forking HTTP connections:

```python
def search_api(
    self,
    endpoint: str,
    query_params: Optional[dict] = None,
    return_all: bool = False,
    max_objects: int = 1000
) -> dict:
    """
    Execute a raw GET request via the manager subprocess.

    Delegates to PlatformService so all HTTP/SSL work happens in
    the manager subprocess rather than in a forked Ansible worker process,
    avoiding the macOS + Python 3.12 fork-safety SIGABRT.

    Args:
        endpoint: API endpoint fragment (e.g. 'applications', 'settings/ui')
        query_params: Optional filter parameters
        return_all: Follow pagination links and collect all results
        max_objects: Safety cap on total returned objects (when return_all=True)

    Returns:
        Raw API response dict from the platform.
    """
    url = self._build_url(endpoint, query_params)
    response = self._make_request('get', url)
    if response.status_code != 200:
        raise RuntimeError(f"API request failed: {response.status_code}")
    return response.json()
```

### Idle-Tracking Methods

```python
def record_activity(self) -> None:
    """Reset the idle clock. Call whenever a real API call completes."""
    with self._activity_lock:
        self._last_activity_monotonic = time.monotonic()

def seconds_since_last_activity(self) -> float:
    """Return seconds elapsed since the last recorded activity."""
    with self._activity_lock:
        return time.monotonic() - self._last_activity_monotonic

def should_exit_for_idle(self, idle_timeout: float) -> bool:
    """Return True if idle_timeout seconds have passed with no API activity."""
    return self.seconds_since_last_activity() >= idle_timeout
```

### Update with `fields_to_null`

Before PATCH requests, the service calls `mixin.get_fields_to_null_for_update()` to determine which fields must be sent as empty strings to clear incompatible server-side values:

```python
def _update_resource(self, ansible_data: Any, mixin_class: type, context: dict) -> dict:
    # ... get current state ...
    
    # Call mixin to get fields that must be nulled
    fields_to_null: set = set()
    if hasattr(mixin_class, "get_fields_to_null_for_update"):
        candidate_fields = mixin_class.get_fields_to_null_for_update(api_data)
        for field in candidate_fields:
            if field in user_unset_fields:
                fields_to_null.add(field)
                setattr(api_data, field, None)

    api_result = self._execute_operations(
        operations, api_data, context,
        required_for="update",
        fields_to_null=fields_to_null
    )
```

---

## Component 7 — PlatformManager

**File**: `plugins/plugin_utils/manager/platform_manager.py`

A `multiprocessing.managers.BaseManager` subclass that exposes `PlatformService` over a Unix domain socket. This is the RPC transport layer.

```python
class PlatformManager(BaseManager):
    pass

# Service registration happens in manager_process.py:
# PlatformManager.register('get_platform_service', callable=_get_service)
```

### Usage (inside the subprocess)

```python
manager = PlatformManager(address=socket_path, authkey=authkey)
manager.start()
# Now manager exposes PlatformService methods over the socket
```

### Usage (from the action plugin via ManagerRPCClient)

```python
manager = PlatformManager(address=socket_path, authkey=authkey)
manager.connect()
service = manager.get_platform_service()
result = service.execute('create', 'user', data_dict)
```

---

## Component 8 — ManagerRPCClient

**File**: `plugins/plugin_utils/manager/rpc_client.py`

The thin client-side proxy that action plugins use. Serializes data to plain dicts before sending over the socket (no complex Python objects cross the process boundary).

```python
class ManagerRPCClient:
    def __init__(self, base_url: str, socket_path: str, authkey: bytes):
        self.base_url = base_url
        self.socket_path = f"{socket_path}"  # Force plain str, not _AnsibleTaggedStr
        self.authkey = authkey

        from .platform_manager import PlatformManager
        PlatformManager.register("get_platform_service")

        self.manager = PlatformManager(address=self.socket_path, authkey=authkey)
        self.manager.connect()
        self.service_proxy = self.manager.get_platform_service()

    def execute(
        self,
        operation: str,
        module_name: str,
        ansible_data: dict
    ) -> dict:
        """Send operation request to manager. Returns result dict."""
        return self.service_proxy.execute(operation, module_name, ansible_data)

    def lookup_resource_id(
        self,
        endpoint: str,
        lookup_field: str,
        lookup_value: str
    ) -> Optional[int]:
        """Resolve resource name to integer ID via manager."""
        return self.service_proxy.lookup_resource_id(endpoint, lookup_field, lookup_value)

    def search_api(
        self,
        endpoint: str,
        query_params: Optional[dict] = None,
        return_all: bool = False,
        max_objects: int = 1000
    ) -> dict:
        """Execute raw API GET via manager (avoids fork-safety issues on macOS)."""
        return self.service_proxy.search_api(endpoint, query_params or {}, return_all, max_objects)

    def shutdown_manager(self) -> dict:
        """Request manager to shutdown gracefully."""
        try:
            if hasattr(self, "service_proxy") and self.service_proxy:
                return self.service_proxy.shutdown()
        except Exception as e:
            logger.debug("Error calling shutdown: %s", e)
        return {"status": "not_connected"}
```

---

## Component 9 — BaseResourceActionPlugin

**File**: `plugins/action/base_action.py`

The shared base class for all resource action plugins. Provides argument spec generation, input/output validation, manager lifecycle management, and operation detection.

### Key Responsibilities

**1. Argument spec from DOCUMENTATION**

```python
def _build_argspec_from_docs(self, documentation: str) -> dict:
    """Parse YAML DOCUMENTATION string into ArgumentSpecValidator format."""
    doc = yaml.safe_load(documentation)
    options = doc.get('options', {})
    return self._normalize_argspec(options)
```

**2. Manager lifecycle**

```python
def _get_or_spawn_manager(self, task_vars: dict):
    """
    Get a manager client. Routes to direct or persistent based on connection plugin.
    Falls back to ephemeral direct manager for connection: local.
    """
    if hasattr(self._connection, 'get_client'):
        # ansible.platform.http connection plugin
        gateway_config = self._build_gateway_config(task_vars)
        client, facts = self._connection.get_client(task_vars, gateway_config)
        if facts:
            self._set_facts(task_vars, facts)
        return client
    else:
        # Fallback: ephemeral direct client (connection: local, testing)
        return self._spawn_ephemeral_manager(task_vars)
```

**3. Operation detection**

```python
def _detect_operation(self, args: dict) -> str:
    """Map state parameter to operation name."""
    state = args.get('state', 'present')
    return {
        'present':  'create_or_update',
        'absent':   'delete',
        'exists':   'find',
        'enforced': 'enforced',
    }[state]
```

**4. check_mode handling**

```python
def run(self, tmp=None, task_vars=None):
    ...
    if self._task.check_mode:
        return dict(
            changed=would_change,
            check_mode=True,
            msg="No changes made (check_mode)"
        )
    ...
```

**5. Cleanup**

`cleanup()` is called by Ansible after each task completes. Its behaviour depends on
which connection mode is active:

- **Ephemeral (direct mode)**: shuts down the manager immediately after the single
  task that spawned it.
- **Persistent mode**: does nothing. Persistent managers are shut down by the
  `platform_manager_cleanup` callback plugin when the play ends.

```python
def cleanup(self, force: bool = False):
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
        socket_path = getattr(self._client, "socket_path", None)
        if socket_path:
            self._shutdown_manager_process(socket_path, ProcessManager)
```

---

## Component 10 — Manager Process Entry Point

**File**: `plugins/plugin_utils/manager/manager_process.py`

The subprocess that runs the persistent manager. Handles lazy initialization, idle monitoring, and graceful shutdown.

### Subprocess Argument Layout

```
sys.argv[0] = script path
sys.argv[1] = socket_path (Unix domain socket path)
sys.argv[2] = socket_dir (directory containing socket)
sys.argv[3] = identifier (inventory hostname or unique ID)
sys.argv[4] = base_url (gateway URL)
sys.argv[5] = username (API username)
sys.argv[6] = password (API password)
sys.argv[7] = oauth_token (API token)
sys.argv[8] = verify_ssl (bool as string "true" / "false")
sys.argv[9] = request_timeout (float as string)
sys.argv[10] = idle_timeout (float as string, seconds)
```

### `_compute_poll_interval(idle_timeout: float) -> int`

Determines how often the idle monitor thread checks `should_exit_for_idle()`:

```python
def _compute_poll_interval(idle_timeout: float) -> int:
    """
    Compute the poll interval (in seconds) for the idle monitor.

    Environment variable `ANSIBLE_PLATFORM_IDLE_POLL_SECONDS` overrides
    the adaptive calculation (useful for testing).

    Adaptive formula: max(5, min(60, int(idle_timeout / 10)))
    - Minimum 5s (don't hammer the clock)
    - Maximum 60s (detect idle within a reasonable time)
    - Default: idle_timeout / 10 (e.g., 360s if idle_timeout = 3600s)

    Args:
        idle_timeout: Timeout in seconds from GatewayConfig

    Returns:
        Poll interval in seconds (int)
    """
    env_override = os.environ.get("ANSIBLE_PLATFORM_IDLE_POLL_SECONDS")
    if env_override:
        # Must use int(float(...)) to handle env strings like "2.5"
        return int(float(env_override))
    
    return max(5, min(60, int(idle_timeout / 10)))
```

### `_idle_monitor(service, idle_timeout)` Daemon Thread

Polls the service for idle state and exits the manager when timeout is reached:

```python
def _idle_monitor(service, idle_timeout):
    """
    Daemon thread that monitors idle time and exits when threshold is reached.

    Polls service.should_exit_for_idle() every _compute_poll_interval() seconds.
    When True, logs and calls os._exit(0) to terminate the entire process.

    This prevents long-running managers from consuming resources when not in use.

    Args:
        service: PlatformService instance
        idle_timeout: Timeout in seconds
    """
    import time
    poll_interval = _compute_poll_interval(idle_timeout)
    logger.info(
        "Idle monitor started: timeout=%ss, poll_interval=%ss",
        idle_timeout, poll_interval
    )

    while True:
        time.sleep(poll_interval)
        if service.should_exit_for_idle(idle_timeout):
            logger.info("Idle timeout reached, shutting down manager")
            os._exit(0)
```

### `_redact_argv()` Credential Masking

Masks sensitive positions in the startup marker file (but not sys.argv itself, which can still be inspected by privileged processes):

```python
def _safe_argv():
    """Return sys.argv with credential positions masked as '***'."""
    safe = list(sys.argv)
    for i in (6, 7):  # password at index 6, token at index 7
        if i < len(safe) and safe[i]:
            safe[i] = "***"
    return safe
```

### Environment Variables Passed to Subprocess

| Variable | Purpose |
|----------|---------|
| `ANSIBLE_PLATFORM_SYS_PATH` | Base64-encoded parent's sys.path (JSON list) |
| `ANSIBLE_PLATFORM_AUTHKEY` | Base64-encoded RPC authkey |
| `ANSIBLE_PLATFORM_OWNER_PID` | PID of parent ansible-playbook process (for watchdog) |

### Owner Watchdog

The subprocess includes a watchdog thread that monitors the parent ansible-playbook process. When the parent exits (or .survive flag is removed in Molecule mode), the manager self-terminates:

```python
# Production mode: watch owner PID
while True:
    time.sleep(3)
    try:
        os.kill(owner_pid, 0)  # signal 0 = liveness check, no side-effects
    except ProcessLookupError:
        logger.info("Owner PID %s gone, shutting down", owner_pid)
        break

# Molecule mode: watch .survive flag
while _survive_path.exists():
    time.sleep(2)
logger.info(".survive flag removed, shutting down")
```

---

## Component 11 — Connection Plugin (http.py)

**File**: `plugins/connection/http.py`

The connection plugin is the dispatcher between action plugins and the manager process. It exposes `get_client()` which action plugins call via `self._connection.get_client()`.

```
transport = 'ansible.platform.http'
```

### Connection Options

| Option | Default | Description |
|--------|---------|-------------|
| `persistent` | `false` | If true, reuse manager process across tasks |
| `host` | (inventory host) | Gateway hostname/IP |
| `port` | `443` | Gateway HTTPS port |
| `use_ssl` | `true` | Use HTTPS |
| `validate_certs` | `true` | Verify SSL certificate |
| `username` | — | Gateway API username |
| `password` | — | Gateway API password (no_log) |

### Error Recovery in Persistent Mode

When reusing a persistent manager, the socket may be stale (manager process died):

```python
def _get_persistent_client(self, task_vars, gateway_config):
    socket_path = task_vars.get('hostvars', {}).get(
        task_vars['inventory_hostname'], {}
    ).get('platform_manager_socket')

    if socket_path and Path(socket_path).exists():
        try:
            client = ManagerRPCClient(gateway_config.base_url, socket_path, authkey)
            return client, None   # reuse succeeded
        except (ConnectionError, OSError):
            pass   # fall through to re-spawn

    # Spawn new manager
    from ..plugin_utils.manager.process_manager import ProcessManager
    
    script_path = Path(__file__).parent.parent / "plugin_utils" / "manager" / "manager_process.py"
    conn_info = ProcessManager.generate_connection_info(
        identifier=task_vars['inventory_hostname'],
        socket_dir=Path(socket_dir),
        gateway_config=gateway_config
    )
    ProcessManager.spawn_manager_process(
        script_path=script_path,
        socket_path=conn_info.socket_path,
        socket_dir=str(socket_dir),
        identifier=task_vars['inventory_hostname'],
        gateway_config=gateway_config,
        authkey_b64=conn_info.authkey_b64,
        sys_path=list(sys.path),
        owner_pid=os.getpid()
    )
    ProcessManager.wait_for_process_startup(
        conn_info.socket_path,
        Path(socket_dir),
        task_vars['inventory_hostname'],
        process,
        max_wait=50
    )
    
    client = ManagerRPCClient(gateway_config.base_url, conn_info.socket_path, conn_info.authkey)
    facts = {
        'platform_manager_socket': conn_info.socket_path,
        'platform_manager_authkey': conn_info.authkey_b64,
    }
    return client, facts
```

---

## Manager Lifecycle

### Direct Mode (ephemeral, connection: local)

```
ACTION PLUGIN
    ↓
_spawn_ephemeral_manager()
    ↓
ProcessManager.spawn_manager_process()
    ↓
SUBPROCESS STARTED
    ├─ _init_service() — PlatformService init (background thread)
    ├─ _owner_watchdog() — monitor parent PID (daemon thread)
    └─ _idle_monitor() — monitor idle time (daemon thread)
    ↓
SERVER.serve_forever() — RPC socket ready
    ↓
ACTION calls client.execute('create', 'user', {...})
    ↓
RPC sends to subprocess, gets result
    ↓
ACTION completes task
    ↓
Ephemeral subprocess exits (no persistent state)
```

### Persistent Mode (connection: ansible.platform.http)

```
PLAY 1, TASK 1
    ↓
connection.get_client() — [SPAWN MANAGER]
    ├─ ProcessManager.generate_connection_info()
    ├─ ProcessManager.spawn_manager_process()
    ├─ ProcessManager.wait_for_process_startup()
    ├─ ManagerRPCClient.connect()
    └─ Set facts: platform_manager_socket, platform_manager_authkey
    ↓
ACTION uses manager for TASK 1

PLAY 1, TASK 2
    ↓
connection.get_client() — [REUSE MANAGER]
    ├─ Detect socket from hostvars['platform_manager_socket']
    ├─ Try ManagerRPCClient.connect() to existing socket
    └─ If success, reuse; if stale, respawn
    ↓
ACTION uses manager for TASK 2

... more tasks reuse the same manager ...

PLAY 1 ENDS
    ↓
_owner_watchdog() detects parent PID gone
    ↓
SUBPROCESS EXITS
    └─ Graceful shutdown (closes socket, flushes logs)
```

---

## Testing the Foundation

Unit tests for the foundation components live in `tests/unit/`. They run with plain `pytest` (no live AAP instance needed):

```bash
pytest tests/unit/ -v
```

| Test file | What it covers |
|-----------|----------------|
| `tests/unit/plugins/plugin_utils/platform/test_registry.py` | `APIVersionRegistry`, version fallback logic |
| `tests/unit/plugins/plugin_utils/platform/test_loader.py` | `DynamicClassLoader`, import caching |
| `tests/unit/plugins/connection/test_http.py` | Connection plugin routing, persistent mode recovery, stale socket detection |
| `tests/unit/plugins/manager/test_process_manager.py` | Process spawning, socket cleanup, waitfd logic |
| `tests/unit/plugins/manager/test_idle_timeout.py` | `_compute_poll_interval()`, idle monitor thread, should_exit_for_idle() |

### Key Test Patterns

**Registry Tests**: Fake filesystem with temporary `api/` directory structure
```python
# tests/unit/plugins/plugin_utils/platform/test_registry.py
with tmpdir.as_cwd():
    # Create api/v1/user.py, api/v2/user.py, etc.
    registry = APIVersionRegistry(api_dir=tmpdir / "api")
    assert registry.find_best_version("1", "user") == "1"
    assert registry.find_best_version("2", "user") == "2"
    assert registry.find_best_version("3", "user") == "2"  # fallback
```

**Idle Timeout Tests**: Mock PlatformService and time.monotonic()
```python
# tests/unit/plugins/manager/test_idle_timeout.py
service = PlatformService(config)
service.record_activity()

# Simulate passage of time
with patch('time.monotonic') as mock_mono:
    mock_mono.return_value = original_time + 3700  # 3700 seconds later
    assert service.should_exit_for_idle(3600)  # idle_timeout=3600s
```

See [08-testing-strategy.md](08-testing-strategy.md) for the full testing strategy.
