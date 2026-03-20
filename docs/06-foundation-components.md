# Foundation Components

This document is the implementation reference for every core component in
`ansible.platform`. Read this before making changes to the framework layer.

---

## Architecture Overview

```
plugins/plugin_utils/
├── platform/
│   ├── registry.py          APIVersionRegistry
│   ├── loader.py            DynamicClassLoader
│   ├── base_transform.py    BaseTransformMixin (protocol)
│   ├── types.py             EndpointOperation, TransformContext
│   ├── config.py            GatewayConfig
│   ├── base_client.py       BaseAPIClient (abstract)
│   ├── direct_client.py     DirectHTTPClient
│   ├── credential_manager.py
│   └── exceptions.py
├── manager/
│   ├── platform_manager.py  PlatformService, PlatformManager
│   ├── rpc_client.py        ManagerRPCClient
│   ├── manager_process.py   subprocess entry point
│   └── process_manager.py   spawn/wait/cleanup helpers
└── ansible_models/          AnsibleFoo dataclasses
api/
└── v1/, v2/                 APIFoo_vN + FooTransformMixin_vN dataclasses
```

---

## 1. `EndpointOperation` and `TransformContext` — Shared Types

**File**: `plugins/plugin_utils/platform/types.py`

These types are shared across all components. `EndpointOperation` describes a single
API call. `TransformContext` carries runtime state into the transform mixin.

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
    operation: str                      # 'create', 'update', 'delete', 'find', 'enforced'
    api_version: str                    # e.g. '1'
    check_mode: bool = False
```

---

## 2. `APIVersionRegistry`

**File**: `plugins/plugin_utils/platform/registry.py`

Scans `plugins/plugin_utils/api/` on startup and builds the version index. No hardcoded
version lists anywhere.

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

### Unit tests

See `tests/unit/plugins/plugin_utils/platform/test_registry.py` for tests that use
a temporary fake filesystem to verify discovery logic in isolation.

---

## 3. `DynamicClassLoader`

**File**: `plugins/plugin_utils/platform/loader.py`

Uses `importlib` to load `(AnsibleClass, APIClass, MixinClass)` for a given module
name and API version. Results are cached.

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

## 4. `BaseTransformMixin`

**File**: `plugins/plugin_utils/platform/base_transform.py`

The protocol (interface) that all transform mixins must implement. Also provides
default implementations for common operations.

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
```

---

## 5. `GatewayConfig`

**File**: `plugins/plugin_utils/platform/config.py`

A simple dataclass holding connection parameters. Created by the action plugin from
Ansible inventory variables and passed to the manager.

```python
@dataclass
class GatewayConfig:
    base_url: str           # e.g. 'https://aap.example.com'
    username: str
    password: str
    verify_ssl: bool = True
    timeout: int = 30
```

---

## 6. `PlatformService`

**File**: `plugins/plugin_utils/manager/platform_manager.py`

The core of the manager process. Inherits `BaseAPIClient`. Holds the HTTP session
and executes all resource operations.

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
```

### Version detection

```python
@property
def api_version(self) -> str:
    if self._api_version is None:
        self._api_version = self._detect_api_version()
    return self._api_version

def _detect_api_version(self) -> str:
    response = self._session.get(f"{self.config.base_url}/ping")
    data = response.json()
    # e.g. {"current_version": "/api/gateway/v1/", "available_versions": {"v1": "..."}}
    raw_version = data['current_version'].strip('/').split('/')[-1]  # 'v1' → '1'
    version_num = raw_version.lstrip('v')
    best = self._registry.find_best_version(version_num, 'user')
    return best or self._registry.get_latest_version()
```

### `execute` method

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
        operation:  'create', 'update', 'delete', 'find', 'enforced'
        module_name: e.g. 'user', 'organization'
        ansible_data_dict: serialized AnsibleFoo fields

    Returns:
        dict with operation result, ready to be returned by action plugin
    """
    AnsibleClass, APIClass, MixinClass = self._loader.load_classes_for_module(
        module_name, self.api_version
    )
    mixin = MixinClass()
    context = TransformContext(
        manager=self,
        operation=operation,
        api_version=self.api_version,
    )

    ansible_instance = AnsibleClass(**ansible_data_dict)

    if operation == 'find':
        return self._find_resource(ansible_instance, mixin, context)
    elif operation == 'create':
        return self._create_resource(ansible_instance, mixin, context)
    elif operation == 'update':
        return self._update_resource(ansible_instance, mixin, context)
    elif operation == 'delete':
        return self._delete_resource(ansible_instance, mixin, context)
    elif operation == 'enforced':
        return self._enforced_resource(ansible_instance, mixin, context)
    else:
        raise ValueError(f"Unknown operation: {operation}")
```

### `lookup_resource_id` method

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
    # Build a minimal ansible instance for lookup
    lookup_field = mixin.get_lookup_field()
    ansible_instance = AnsibleClass(**{lookup_field: name_or_id})
    context = TransformContext(manager=self, operation='find', api_version=self.api_version)
    result = self._find_resource(ansible_instance, mixin, context)
    return result.get('id') if result else None
```

---

## 7. `PlatformManager`

**File**: `plugins/plugin_utils/manager/platform_manager.py`

A `multiprocessing.managers.BaseManager` subclass that exposes `PlatformService`
over a Unix domain socket. This is the RPC transport layer.

```python
class PlatformManager(BaseManager):
    pass

PlatformManager.register('PlatformService', PlatformService)
```

Usage (inside the subprocess):
```python
manager = PlatformManager(address=socket_path, authkey=authkey)
manager.start()
# Now manager exposes PlatformService methods over the socket
```

Usage (from the action plugin via ManagerRPCClient):
```python
manager = PlatformManager(address=socket_path, authkey=authkey)
manager.connect()
service = manager.PlatformService()
result = service.execute('create', 'user', data_dict)
```

---

## 8. `ManagerRPCClient`

**File**: `plugins/plugin_utils/manager/rpc_client.py`

The thin client-side proxy that action plugins use. Serializes data to plain dicts
before sending over the socket (no complex Python objects cross the process boundary).

```python
class ManagerRPCClient:
    def __init__(self, socket_path: str, authkey: bytes):
        self._manager = PlatformManager(address=socket_path, authkey=authkey)
        self._manager.connect()
        self.service_proxy = self._manager.PlatformService()

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
        resource_type: str,
        name_or_id: Union[str, int],
        **kwargs
    ) -> Optional[int]:
        """Resolve resource name to integer ID via manager."""
        return self.service_proxy.lookup_resource_id(resource_type, name_or_id, **kwargs)
```

---

## 9. `BaseResourceActionPlugin`

**File**: `plugins/action/base_action.py`

The shared base class for all 22 action plugins. Provides argument spec generation,
input/output validation, manager lifecycle management, and operation detection.

### Key Responsibilities

**1. Argument spec from DOCUMENTATION**

```python
def _build_argspec_from_docs(self, documentation: str) -> dict:
    """Parse YAML DOCUMENTATION string into ArgumentSpecValidator format."""
    doc = yaml.safe_load(documentation)
    options = doc.get('options', {})
    # Also load fragments (e.g. 'extends_documentation_fragment')
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
        'merged':   'update',
    }[state]
```

**4. check_mode**

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

```python
def cleanup(self, force: bool = False):
    """
    Remove task tracking file. Shut down manager process when last task completes.
    Uses file-based lock to prevent race conditions between concurrent tasks.
    """
    tracking_dir = Path(f"/tmp/ansible_platform_tracking/{self._play_id}/")
    task_file = tracking_dir / self._task_id
    task_file.unlink(missing_ok=True)

    if not list(tracking_dir.iterdir()):
        # No more tasks in this play — shut down the manager
        self._shutdown_manager()
```

---

## 10. Connection Plugin (`http.py`)

**File**: `plugins/connection/http.py`

```
transport = 'ansible.platform.http'
```

The connection plugin is the dispatcher between action plugins and the manager process.
It exposes `get_client()` which action plugins call via `self._connection.get_client()`.

### Connection options

| Option | Default | Description |
|--------|---------|-------------|
| `persistent` | `false` | If true, reuse manager process across tasks |
| `host` | (inventory host) | Gateway hostname/IP |
| `port` | `443` | Gateway HTTPS port |
| `use_ssl` | `true` | Use HTTPS |
| `validate_certs` | `true` | Verify SSL certificate |
| `username` | — | Gateway API username |
| `password` | — | Gateway API password (no_log) |

### Error recovery in persistent mode

When reusing a persistent manager, the socket may be stale (manager process died):

```python
def _get_persistent_client(self, task_vars, gateway_config):
    socket_path = task_vars.get('hostvars', {}).get(
        task_vars['inventory_hostname'], {}
    ).get('platform_manager_socket')

    if socket_path and Path(socket_path).exists():
        try:
            client = ManagerRPCClient(socket_path, authkey)
            return client, None   # reuse succeeded
        except (ConnectionError, OSError):
            pass   # fall through to re-spawn

    # Spawn new manager
    conn_info = ProcessManager.generate_connection_info()
    ProcessManager.spawn_manager_process(gateway_config, conn_info)
    ProcessManager.wait_for_process_startup(conn_info.socket_path)
    client = ManagerRPCClient(conn_info.socket_path, conn_info.authkey)
    facts = {
        'platform_manager_socket': conn_info.socket_path,
        'platform_manager_authkey': conn_info.authkey_b64,
    }
    return client, facts
```

---

## Testing the Foundation

Unit tests for the foundation components live in `tests/unit/`. They run with plain
`pytest` (no live AAP instance needed):

```bash
pytest tests/unit/ -v
```

| Test file | What it covers |
|-----------|----------------|
| `tests/unit/modules/test_registry.py` | `APIVersionRegistry`, `DynamicClassLoader`, `PlatformService` version fallback |
| `tests/unit/plugins/connection/test_http.py` | Connection plugin routing, persistent mode recovery |
| `tests/unit/plugins/plugin_utils/platform/test_registry.py` | Registry filesystem scan with a fake `api/` directory |

See [08-testing-strategy.md](08-testing-strategy.md) for the full testing strategy.
