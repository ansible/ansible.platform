# API Reference - Ansible Platform Collection

## Overview

This document provides detailed API reference for all components in the Ansible Platform Collection architecture.

## Table of Contents

1. [Platform Components](#platform-components)
2. [Manager Components](#manager-components)
3. [Action Plugin Components](#action-plugin-components)
4. [Data Models](#data-models)

---

## Platform Components

### BaseTransformMixin

**Location**: `plugins/plugin_utils/platform/base_transform.py`

**Base Class**: `ABC`

**Purpose**: Universal transformation logic for bidirectional data transformation.

#### Class Variables

```python
_field_mapping: Optional[Dict] = None
_transform_registry: Optional[Dict] = None
```

#### Methods

##### `to_api(context: Optional[Dict] = None) -> Any`

Transform from Ansible format to API format.

**Parameters**:
- `context` (Optional[Dict]): Context dict containing:
  - `manager`: PlatformManager instance
  - `session`: HTTP session
  - `cache`: Lookup cache
  - `api_version`: Current API version

**Returns**: API dataclass instance

**Example**:
```python
context = {'manager': manager, 'session': session, 'cache': {}}
api_user = ansible_user.to_api(context)
```

##### `to_ansible(context: Optional[Dict] = None) -> Any`

Transform from API format to Ansible format.

**Parameters**:
- `context` (Optional[Dict]): Same as `to_api()`

**Returns**: Ansible dataclass instance

**Example**:
```python
ansible_user = api_user.to_ansible(context)
```

##### `_get_api_class() -> Type`

Get the API dataclass type for this resource.

**Must be overridden by subclasses**.

**Returns**: API dataclass type

**Raises**: `NotImplementedError` if not overridden

##### `_get_ansible_class() -> Type`

Get the Ansible dataclass type for this resource.

**Must be overridden by subclasses**.

**Returns**: Ansible dataclass type

**Raises**: `NotImplementedError` if not overridden

---

### APIVersionRegistry

**Location**: `plugins/plugin_utils/platform/registry.py`

**Purpose**: Discover and manage API version information.

#### Constructor

```python
def __init__(
    self,
    api_base_path: Optional[str] = None,
    ansible_models_path: Optional[str] = None
)
```

**Parameters**:
- `api_base_path` (Optional[str]): Path to api/ directory (auto-detected if None)
- `ansible_models_path` (Optional[str]): Path to ansible_models/ (auto-detected if None)

#### Methods

##### `get_supported_versions() -> List[str]`

Get all discovered API versions, sorted.

**Returns**: List of version strings (e.g., `['1', '2', '2.1']`)

##### `get_latest_version() -> Optional[str]`

Get the latest available API version.

**Returns**: Latest version string, or `None` if no versions found

##### `get_modules_for_version(api_version: str) -> List[str]`

Get list of modules available for a specific API version.

**Parameters**:
- `api_version` (str): Version string (e.g., '1', '2.1')

**Returns**: List of module names

##### `get_versions_for_module(module_name: str) -> List[str]`

Get list of API versions that implement a module.

**Parameters**:
- `module_name` (str): Module name (e.g., 'user', 'organization')

**Returns**: List of version strings

##### `find_best_version(requested_version: str, module_name: str) -> Optional[str]`

Find the best available version for a module.

**Strategy**:
1. Try exact match
2. Try closest lower version (backward compatible)
3. Try closest higher version (forward compatible, with warning)

**Parameters**:
- `requested_version` (str): Desired API version
- `module_name` (str): Module name

**Returns**: Best matching version string, or `None` if not found

---

### DynamicClassLoader

**Location**: `plugins/plugin_utils/platform/loader.py`

**Purpose**: Load version-specific classes at runtime.

#### Constructor

```python
def __init__(self, registry: APIVersionRegistry)
```

**Parameters**:
- `registry` (APIVersionRegistry): Version registry for discovering available versions

#### Methods

##### `load_classes_for_module(module_name: str, api_version: str) -> Tuple[Type, Type, Type]`

Load classes for a module and API version.

**Parameters**:
- `module_name` (str): Module name (e.g., 'user', 'organization')
- `api_version` (str): API version (e.g., '1', '2.1')

**Returns**: Tuple of `(AnsibleClass, APIClass, MixinClass)`

**Raises**: `ValueError` if classes cannot be loaded

**Example**:
```python
loader = DynamicClassLoader(registry)
AnsibleUser, APIUser_v1, UserTransformMixin_v1 = loader.load_classes_for_module('user', '1')
```

---

### EndpointOperation

**Location**: `plugins/plugin_utils/platform/types.py`

**Purpose**: Configuration for a single API endpoint operation.

#### Constructor

```python
@dataclass
class EndpointOperation:
    path: str
    method: str
    fields: List[str]
    path_params: Optional[List[str]] = None
    required_for: Optional[str] = None
    depends_on: Optional[str] = None
    order: int = 0
```

**Parameters**:
- `path` (str): API endpoint path (e.g., '/api/gateway/v1/users/')
- `method` (str): HTTP method ('GET', 'POST', 'PATCH', 'DELETE')
- `fields` (List[str]): List of dataclass field names to include in request
- `path_params` (Optional[List[str]]): Path parameter names (e.g., ['id'])
- `required_for` (Optional[str]): Operation type this is required for ('create', 'update', 'delete', or None)
- `depends_on` (Optional[str]): Name of operation this depends on
- `order` (int): Execution order (lower runs first)

**Example**:
```python
EndpointOperation(
    path='/api/gateway/v1/users/{id}/organizations/',
    method='POST',
    fields=['organizations'],
    path_params=['id'],
    depends_on='create',
    order=2
)
```

---

## Manager Components

### PlatformService

**Location**: `plugins/plugin_utils/manager/platform_manager.py`

**Purpose**: Persistent service that handles API communication and transformations.

#### Constructor

```python
def __init__(
    self,
    base_url: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    oauth_token: Optional[str] = None,
    verify_ssl: bool = True,
    request_timeout: float = 10.0
)
```

**Parameters**:
- `base_url` (str): Platform base URL (e.g., 'https://platform.example.com')
- `username` (Optional[str]): Username for basic auth
- `password` (Optional[str]): Password for basic auth
- `oauth_token` (Optional[str]): OAuth token for bearer auth
- `verify_ssl` (bool): Whether to verify SSL certificates (default: True)
- `request_timeout` (float): Request timeout in seconds (default: 10.0)

#### Methods

##### `execute(operation: str, module_name: str, ansible_data_dict: dict) -> dict`

Execute a generic operation on any resource.

**Parameters**:
- `operation` (str): Operation type ('create', 'update', 'delete', 'find')
- `module_name` (str): Module name (e.g., 'user', 'organization')
- `ansible_data_dict` (dict): Ansible dataclass as dict

**Returns**: Result as dict (Ansible format)

**Raises**: `ValueError` if operation is unknown or execution fails

**Example**:
```python
service = PlatformService(base_url='https://platform.example.com', username='admin', password='secret')
result = service.execute('create', 'user', {'username': 'jdoe', 'email': 'jdoe@example.com'})
```

##### `lookup_org_ids(org_names: list) -> list`

Convert organization names to IDs.

**Parameters**:
- `org_names` (list): List of organization names

**Returns**: List of organization IDs

**Raises**: `ValueError` if organization not found

##### `lookup_org_names(org_ids: list) -> list`

Convert organization IDs to names.

**Parameters**:
- `org_ids` (list): List of organization IDs

**Returns**: List of organization names

---

### ManagerRPCClient

**Location**: `plugins/plugin_utils/manager/rpc_client.py`

**Purpose**: Client-side interface for communicating with PlatformManager.

#### Constructor

```python
def __init__(
    self,
    base_url: str,
    socket_path: str,
    authkey: bytes
)
```

**Parameters**:
- `base_url` (str): Platform base URL
- `socket_path` (str): Path to Unix socket
- `authkey` (bytes): Authentication key

#### Methods

##### `execute(operation: str, module_name: str, ansible_data: Any) -> Any`

Execute operation via manager.

**Parameters**:
- `operation` (str): Operation type
- `module_name` (str): Module name
- `ansible_data` (Any): Ansible dataclass instance

**Returns**: Result dict (Ansible format)

**Example**:
```python
client = ManagerRPCClient(base_url, socket_path, authkey)
result = client.execute('create', 'user', ansible_user)
```

##### `close() -> None`

Close connection to manager.

---

## Action Plugin Components

### BaseResourceActionPlugin

**Location**: `plugins/action/base_action.py`

**Base Class**: `ActionBase`

**Purpose**: Base class for all resource action plugins.

#### Class Variables

```python
MODULE_NAME = None  # Subclass must override
```

#### Methods

##### `_get_or_spawn_manager(task_vars: dict) -> ManagerRPCClient`

Get existing manager or spawn new one.

**Parameters**:
- `task_vars` (dict): Task variables from Ansible

**Returns**: `ManagerRPCClient` instance

**Raises**: `RuntimeError` if manager fails to start

**Behavior**:
1. Checks hostvars for existing manager
2. If found, connects to existing manager
3. If not found, spawns new manager process
4. Stores manager info in facts for reuse

##### `_build_argspec_from_docs(documentation: str) -> dict`

Build argument spec from DOCUMENTATION string.

**Parameters**:
- `documentation` (str): DOCUMENTATION string from module

**Returns**: ArgumentSpec dict suitable for ArgumentSpecValidator

**Raises**: `ValueError` if documentation cannot be parsed

##### `_validate_data(data: dict, argspec: dict, direction: str) -> dict`

Validate data against argument spec.

**Parameters**:
- `data` (dict): Data dict to validate
- `argspec` (dict): Argument specification
- `direction` (str): 'input' or 'output' (for error messages)

**Returns**: Validated and normalized data dict

**Raises**: `AnsibleError` if validation fails

##### `_detect_operation(args: dict) -> str`

Detect operation type from arguments.

**Parameters**:
- `args` (dict): Module arguments

**Returns**: Operation name ('create', 'update', 'delete', 'find')

**Logic**:
- `state: absent` → 'delete'
- `state: present` + `id` present → 'update'
- `state: present` + no `id` → 'create'
- `state: find` → 'find'

---

## Data Models

### Ansible Dataclasses

**Location**: `plugins/plugin_utils/ansible_models/`

**Purpose**: User-facing data models (stable interface).

**Base Class**: `BaseTransformMixin`

**Example**:
```python
@dataclass
class AnsibleUser(BaseTransformMixin):
    username: str
    email: Optional[str] = None
    organizations: Optional[List[str]] = None
    id: Optional[int] = None
```

### API Dataclasses

**Location**: `plugins/plugin_utils/api/v1/generated/models.py`

**Purpose**: API data models (generated from OpenAPI).

**Example**:
```python
@dataclass
class User:
    id: Optional[int] = None
    username: str = ''
    email: Optional[str] = None
    organization_ids: Optional[List[int]] = None
```

### Transform Mixins

**Location**: `plugins/plugin_utils/api/v1/{resource}.py`

**Purpose**: Bridge between Ansible and API dataclasses.

**Base Class**: `BaseTransformMixin`

**Example**:
```python
class UserTransformMixin_v1(BaseTransformMixin):
    _field_mapping = {
        'username': 'username',
        'organizations': {
            'api_field': 'organization_ids',
            'forward_transform': 'names_to_ids',
            'reverse_transform': 'ids_to_names',
        }
    }
    
    _transform_registry = {
        'names_to_ids': lambda names, ctx: ctx['manager'].lookup_org_ids(names),
        'ids_to_names': lambda ids, ctx: ctx['manager'].lookup_org_names(ids),
    }
    
    @classmethod
    def get_endpoint_operations(cls):
        return {
            'create': EndpointOperation(...),
        }
```

---

## Usage Examples

### Complete Example: Creating a User

```python
# 1. Action Plugin
class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = 'user'
    
    def run(self, tmp=None, task_vars=None):
        # Validate input
        argspec = self._build_argspec_from_docs(DOCUMENTATION)
        validated = self._validate_data(self._task.args, argspec, 'input')
        
        # Get manager
        manager = self._get_or_spawn_manager(task_vars)
        
        # Create dataclass
        user_data = AnsibleUser(**validated)
        
        # Execute
        operation = self._detect_operation(self._task.args)
        result = manager.execute(operation, self.MODULE_NAME, user_data)
        
        # Validate output
        validated_result = self._validate_data(result, argspec, 'output')
        
        return {'changed': True, 'failed': False, 'user': validated_result}
```

### Transform Example

```python
# Forward transform (Ansible → API)
ansible_user = AnsibleUser(
    username='jdoe',
    organizations=['Engineering', 'DevOps']
)

context = {
    'manager': platform_service,
    'session': session,
    'cache': {},
    'api_version': '1'
}

api_user = ansible_user.to_api(context)
# api_user.organization_ids = [1, 2]  # Names converted to IDs

# Reverse transform (API → Ansible)
ansible_result = api_user.to_ansible(context)
# ansible_result.organizations = ['Engineering', 'DevOps']  # IDs converted back to names
```

---

## Error Handling

### Common Exceptions

#### `ValueError`
- Invalid operation type
- Missing required fields
- Transformation failures

#### `ImportError`
- Class loading failures
- Module import errors

#### `RuntimeError`
- Manager startup failures
- Connection errors

#### `AnsibleError`
- Validation failures
- Configuration errors

---

## Related Documentation

- `ARCHITECTURE.md` - System architecture overview
- `IMPLEMENTATION_GUIDE.md` - Implementation details
- `DEVELOPER_GUIDE.md` - Developer workflow


