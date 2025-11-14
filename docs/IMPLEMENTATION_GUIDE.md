# Implementation Guide - Ansible Platform Collection

## Overview

This guide provides step-by-step instructions for implementing the new architecture in the Ansible Platform Collection. It covers both the foundation components and adding new resources.

## Table of Contents

1. [Foundation Components](#foundation-components)
2. [Adding a New Resource](#adding-a-new-resource)
3. [Code Generation](#code-generation)
4. [Testing](#testing)
5. [Troubleshooting](#troubleshooting)

---

## Foundation Components

### Component Overview

The foundation consists of 8 core components:

1. **Shared Types** (`platform/types.py`) - EndpointOperation dataclass
2. **BaseTransformMixin** (`platform/base_transform.py`) - Universal transformation logic
3. **APIVersionRegistry** (`platform/registry.py`) - Version discovery
4. **DynamicClassLoader** (`platform/loader.py`) - Runtime class loading
5. **PlatformService** (`manager/platform_manager.py`) - Persistent service
6. **PlatformManager** (`manager/platform_manager.py`) - Multiprocessing manager
7. **ManagerRPCClient** (`manager/rpc_client.py`) - RPC client
8. **BaseResourceActionPlugin** (`action/base_action.py`) - Base action plugin

### Implementation Status

✅ **All foundation components are implemented** and located in:
- `plugins/plugin_utils/platform/`
- `plugins/plugin_utils/manager/`
- `plugins/action/`

### Component Details

#### 1. Shared Types

**File**: `plugins/plugin_utils/platform/types.py`

**Purpose**: Type definitions used across the framework.

**Key Class**: `EndpointOperation`

**Usage**:
```python
from ansible.platform.plugins.plugin_utils.platform.types import EndpointOperation

EndpointOperation(
    path='/api/gateway/v1/users/',
    method='POST',
    fields=['username', 'email'],
    order=1
)
```

#### 2. BaseTransformMixin

**File**: `plugins/plugin_utils/platform/base_transform.py`

**Purpose**: Universal transformation logic for bidirectional data transformation.

**Key Methods**:
- `to_api(context)` - Transform Ansible → API
- `to_ansible(context)` - Transform API → Ansible

**How Subclasses Use It**:
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
    }
```

#### 3. APIVersionRegistry

**File**: `plugins/plugin_utils/platform/registry.py`

**Purpose**: Discover available API versions by scanning filesystem.

**Key Methods**:
- `get_supported_versions()` - List all versions
- `get_versions_for_module(module_name)` - Versions for a module
- `find_best_version(requested, module)` - Find best match

**How It Works**:
1. Scans `api/` directory for `v1/`, `v2/`, etc.
2. Discovers `.py` files in each version directory
3. Builds version × module matrix
4. Provides fallback logic

**Example**:
```python
registry = APIVersionRegistry()
versions = registry.get_supported_versions()  # ['1', '2']
user_versions = registry.get_versions_for_module('user')  # ['1', '2']
best = registry.find_best_version('2.1', 'user')  # '2' (closest lower)
```

#### 4. DynamicClassLoader

**File**: `plugins/plugin_utils/platform/loader.py`

**Purpose**: Load version-appropriate classes at runtime.

**Key Method**: `load_classes_for_module(module_name, api_version)`

**Returns**: Tuple of (AnsibleClass, APIClass, MixinClass)

**How It Works**:
1. Uses registry to find best version match
2. Dynamically imports classes
3. Caches results for performance
4. Pattern matching for class discovery

**Example**:
```python
loader = DynamicClassLoader(registry)
AnsibleClass, APIClass, MixinClass = loader.load_classes_for_module('user', '1')
```

#### 5. PlatformService

**File**: `plugins/plugin_utils/manager/platform_manager.py`

**Purpose**: Persistent service that handles API communication and transformations.

**Key Method**: `execute(operation, module_name, ansible_data_dict)`

**How It Works**:
1. Maintains persistent `requests.Session`
2. Detects API version on startup
3. Loads version-specific classes
4. Performs forward transform
5. Executes API calls
6. Performs reverse transform
7. Returns Ansible-format data

**Authentication**:
- Basic Auth: `username` and `password`
- OAuth Token: `oauth_token`
- SSL Verification: `verify_ssl` (default: True)
- Timeout: `request_timeout` (default: 10.0)

**Example**:
```python
service = PlatformService(
    base_url='https://platform.example.com',
    username='admin',
    password='secret',
    verify_ssl=True
)
result = service.execute('create', 'user', user_dict)
```

#### 6. PlatformManager

**File**: `plugins/plugin_utils/manager/platform_manager.py`

**Purpose**: Multiprocessing Manager for sharing PlatformService.

**How It Works**:
1. Extends `BaseManager` with `ThreadingMixIn`
2. Registers `get_platform_service()` method
3. Uses Unix domain socket
4. Thread-safe for concurrent clients

**Example**:
```python
PlatformManager.register('get_platform_service')
manager = PlatformManager(address=socket_path, authkey=authkey)
manager.start()
```

#### 7. ManagerRPCClient

**File**: `plugins/plugin_utils/manager/rpc_client.py`

**Purpose**: Client-side interface for communicating with PlatformManager.

**Key Method**: `execute(operation, module_name, ansible_data)`

**Example**:
```python
client = ManagerRPCClient(base_url, socket_path, authkey)
result = client.execute('create', 'user', ansible_user)
```

#### 8. BaseResourceActionPlugin

**File**: `plugins/action/base_action.py`

**Purpose**: Base class for all resource action plugins.

**Key Methods**:
- `_get_or_spawn_manager(task_vars)` - Get or spawn manager
- `_build_argspec_from_docs(documentation)` - Parse DOCUMENTATION
- `_validate_data(data, argspec, direction)` - Validate input/output
- `_detect_operation(args)` - Detect operation type

**How Subclasses Use It**:
```python
class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = 'user'
    
    def run(self, tmp=None, task_vars=None):
        # Validate input
        argspec = self._build_argspec_from_docs(DOCUMENTATION)
        validated = self._validate_data(self._task.args, argspec, 'input')
        
        # Get manager
        manager = self._get_or_spawn_manager(task_vars)
        
        # Execute
        operation = self._detect_operation(self._task.args)
        result = manager.execute(operation, self.MODULE_NAME, validated)
        
        # Validate output
        validated_result = self._validate_data(result, argspec, 'output')
        
        return {'changed': True, 'failed': False, 'user': validated_result}
```

---

## Adding a New Resource

### Step-by-Step Process

#### Step 1: Write Documentation

**File**: `plugins/plugin_utils/docs/{resource}.py`

**Purpose**: Define user-facing interface.

**Example** (`user.py`):
```python
DOCUMENTATION = """
---
module: user
short_description: Manage platform users
options:
  username:
    description: Username for the user
    required: true
    type: str
  email:
    description: Email address
    type: str
  organizations:
    description: List of organization names
    type: list
    elements: str
  id:
    description: User ID (read-only)
    type: int
"""
```

**Key Principles**:
- User-facing (names, not IDs)
- Clear descriptions
- Mark read-only fields
- Specify required fields

#### Step 2: Generate Ansible Dataclass

**Tool**: `tools/generators/generate_ansible_dataclasses.py`

**Command**:
```bash
python tools/generators/generate_ansible_dataclasses.py \
    plugins/plugin_utils/docs/user.py
```

**Output**: `plugins/plugin_utils/ansible_models/user.py`

**Generated Code**:
```python
@dataclass
class AnsibleUser(BaseTransformMixin):
    username: str
    email: Optional[str] = None
    organizations: Optional[List[str]] = None
    id: Optional[int] = None
```

#### Step 3: Generate API Models

**Tool**: `tools/generators/generate_api_models.sh`

**Prerequisites**: OpenAPI spec in `tools/openapi_specs/gateway-v1.json`

**Command**:
```bash
bash tools/generators/generate_api_models.sh
```

**Output**: `plugins/plugin_utils/api/v1/generated/models.py`

**Contains**: All API dataclasses from OpenAPI spec

#### Step 4: Create Transform Mixin

**File**: `plugins/plugin_utils/api/v1/{resource}.py`

**Purpose**: Define field mappings and transformations.

**Example** (`user.py`):
```python
from dataclasses import dataclass
from ..platform.base_transform import BaseTransformMixin
from ..platform.types import EndpointOperation
from .generated.models import User as GeneratedAPIUser

class UserTransformMixin_v1(BaseTransformMixin):
    _field_mapping = {
        'username': 'username',
        'email': 'email',
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
            'create': EndpointOperation(
                path='/api/gateway/v1/users/',
                method='POST',
                fields=['username', 'email'],
                order=1
            ),
        }
    
    @classmethod
    def _get_api_class(cls):
        return APIUser_v1
    
    @classmethod
    def _get_ansible_class(cls):
        from ...ansible_models.user import AnsibleUser
        return AnsibleUser

@dataclass
class APIUser_v1(UserTransformMixin_v1, GeneratedAPIUser):
    pass
```

#### Step 5: Create Action Plugin

**File**: `plugins/action/{resource}.py`

**Purpose**: Thin wrapper that uses base action plugin.

**Example** (`user.py`):
```python
from ansible.plugins.action import ActionBase
from ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible.platform.plugins.plugin_utils.docs.user import DOCUMENTATION
from ansible.platform.plugins.plugin_utils.ansible_models.user import AnsibleUser

class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = 'user'
    
    def run(self, tmp=None, task_vars=None):
        super(ActionModule, self).run(tmp, task_vars)
        
        if task_vars is None:
            task_vars = {}
        
        args = self._task.args.copy()
        
        try:
            # 1. Validate input
            argspec = self._build_argspec_from_docs(DOCUMENTATION)
            validated_args = self._validate_data(args, argspec, 'input')
            
            # 2. Get manager
            manager = self._get_or_spawn_manager(task_vars)
            
            # 3. Create dataclass
            user_data = AnsibleUser(**validated_args)
            
            # 4. Execute
            operation = self._detect_operation(args)
            result_dict = manager.execute(operation, self.MODULE_NAME, user_data)
            
            # 5. Validate output
            validated_result = self._validate_data(result_dict, argspec, 'output')
            
            # 6. Return
            return {
                'failed': False,
                'changed': True,
                self.MODULE_NAME: validated_result
            }
        except Exception as e:
            return {'failed': True, 'msg': str(e)}
```

#### Step 6: Test

**File**: `tests/integration/test_{resource}.yml`

**Example**:
```yaml
---
- name: Test User Management
  hosts: localhost
  tasks:
    - name: Create user
      ansible.platform.user:
        username: jdoe
        email: jdoe@example.com
        organizations:
          - Engineering
      register: result
    
    - name: Verify creation
      assert:
        that:
          - result is not failed
          - result.changed
          - result.user.username == 'jdoe'
```

---

## Code Generation

### Ansible Dataclass Generator

**Tool**: `tools/generators/generate_ansible_dataclasses.py`

**Purpose**: Generate Python dataclasses from DOCUMENTATION strings.

**Usage**:
```bash
python tools/generators/generate_ansible_dataclasses.py \
    plugins/plugin_utils/docs/user.py \
    --output plugins/plugin_utils/ansible_models/user.py
```

**Input**: DOCUMENTATION string in YAML format

**Output**: Python dataclass with type hints

### API Model Generator

**Tool**: `tools/generators/generate_api_models.sh`

**Purpose**: Generate Python dataclasses from OpenAPI specifications.

**Prerequisites**:
- `datamodel-code-generator` installed
- OpenAPI spec in `tools/openapi_specs/gateway-v1.json`

**Usage**:
```bash
bash tools/generators/generate_api_models.sh
```

**Input**: OpenAPI JSON specification

**Output**: Python dataclasses in `plugins/plugin_utils/api/v1/generated/models.py`

---

## Testing

### Unit Tests

**Location**: `tests/unit/`

**Purpose**: Test individual components in isolation.

**Example**:
```python
def test_forward_transform():
    ansible_user = AnsibleUser(
        username='test',
        organizations=['Org1']
    )
    context = {'manager': MockManager()}
    api_user = ansible_user.to_api(context)
    assert api_user.organization_ids == [1]
```

### Integration Tests

**Location**: `tests/integration/`

**Purpose**: Test end-to-end functionality with real API.

**Example**: See Step 6 above.

---

## Troubleshooting

### Common Issues

#### Issue: Manager fails to start

**Symptoms**: `RuntimeError: Manager failed to start`

**Solutions**:
1. Check socket directory permissions
2. Verify no existing socket file blocking
3. Check authentication credentials
4. Review manager logs

#### Issue: Class loading fails

**Symptoms**: `ImportError: Failed to import...`

**Solutions**:
1. Verify module file exists in correct location
2. Check class naming conventions
3. Verify `__init__.py` files exist
4. Check Python path

#### Issue: Transformations fail

**Symptoms**: `ValueError` or `KeyError` during transform

**Solutions**:
1. Verify `_field_mapping` is correct
2. Check transform functions in `_transform_registry`
3. Verify context contains required keys
4. Check API response format

#### Issue: Version not found

**Symptoms**: `ValueError: No compatible API version found`

**Solutions**:
1. Verify version directory exists (`api/v1/`)
2. Check module file exists in version directory
3. Verify version string format
4. Check registry discovery logs

---

## Next Steps

1. Implement code generation tools
2. Migrate first resource (user module)
3. Add comprehensive tests
4. Create user documentation
5. Set up CI/CD

---

## Related Documentation

- `ARCHITECTURE.md` - System architecture overview
- `DEVELOPER_GUIDE.md` - Developer workflow
- `API_REFERENCE.md` - Component API reference


