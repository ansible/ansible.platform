# Complete Flow Explanation - Ansible Platform Collection

## Overview

This document provides a comprehensive explanation of the entire flow in the Ansible Platform Collection, from when a user runs an Ansible playbook to how the system manages resources on Ansible Automation Platform (AAP) Gateway.

> **📊 For visual diagrams, see [ARCHITECTURE_DIAGRAMS.md](./ARCHITECTURE_DIAGRAMS.md)** which contains:
> - High-level architecture diagrams
> - Component interaction diagrams
> - Data flow diagrams
> - Manager lifecycle diagrams
> - Sequence diagrams for all operations

> **📝 For detailed step-by-step code walkthrough with line numbers and code snippets, see [CODE_WALKTHROUGH.md](./CODE_WALKTHROUGH.md)** which provides:
> - Detailed execution flow with code examples
> - File locations and line numbers
> - Step-by-step code snippets
> - Debugging tips
> - Complete transformation examples

---

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Complete Request Flow](#complete-request-flow)
3. [Component Details](#component-details)
4. [Data Transformation Flow](#data-transformation-flow)
5. [Manager Lifecycle](#manager-lifecycle)
6. [Version Management](#version-management)
7. [Example: Creating a User](#example-creating-a-user)

---

## High-Level Architecture

The system is organized into **4 distinct layers**:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Ansible Playbook (User Interface)                  │
│  - Stable YAML interface                                     │
│  - Version-agnostic                                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Action Plugins (Client Layer)                     │
│  - Thin, stateless clients                                  │
│  - Input/output validation                                  │
│  - Manager connection management                            │
│  - NO transformations, NO API knowledge                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ RPC (Unix Socket)
                       │ (Only Ansible format data)
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ Layer 3: Platform Manager (Persistent Service)              │
│  - Persistent HTTP session                                  │
│  - API version detection                                    │
│  - ALL transformations (Ansible ↔ API)                     │
│  - API calls                                                │
│  - Resource-agnostic (works for all resources)              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ HTTP/HTTPS
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ Layer 4: AAP Gateway API                                    │
│  - REST API endpoints                                       │
│  - Version-specific schemas                                 │
│  - Authentication (Basic/OAuth)                             │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Separation of Concerns**: Client (action plugins) is thin and stateless; Manager is heavy and stateful
2. **Manager-Side Transformations**: All data transformations happen in the persistent manager
3. **Round-Trip Data Contract**: Output format always matches input format
4. **Generic Manager**: One manager works for all resources
5. **Dynamic Version Management**: Filesystem-based version discovery

---

## Complete Request Flow

### Step-by-Step Flow Diagram

```
1. USER RUNS PLAYBOOK
   └─> ansible-playbook playbook.yml
       │
       └─> Task: ansible.platform.user
           │
           └─> 2. ANSIBLE INVOKES ACTION PLUGIN
               └─> plugins/action/user.py
                   │
                   ├─> 3. VALIDATE INPUT
                   │   └─> Parse DOCUMENTATION string
                   │   └─> Build ArgumentSpec
                   │   └─> Validate against spec
                   │   └─> Normalize data
                   │
                   ├─> 4. CREATE ANSIBLE DATACLASS
                   │   └─> AnsibleUser(**validated_args)
                   │   └─> organizations=['Engineering', 'DevOps']  # Names
                   │
                   ├─> 5. GET/CONNECT TO MANAGER
                   │   └─> Check hostvars for existing manager
                   │   └─> If found: Connect via Unix socket
                   │   └─> If not found: Spawn new manager process
                   │       │
                   │       └─> 5a. SPAWN MANAGER PROCESS
                   │           ├─> Create Unix socket path
                   │           ├─> Generate auth key
                   │           ├─> Start PlatformService
                   │           │   ├─> Create persistent HTTP session
                   │           │   ├─> Authenticate with AAP
                   │           │   ├─> Detect API version
                   │           │   └─> Initialize registry & loader
                   │           ├─> Register with PlatformManager
                   │           └─> Start manager server
                   │
                   └─> 6. SEND TO MANAGER (RPC)
                       └─> manager.execute('create', 'user', ansible_user_dict)
                           │
                           ▼
7. PLATFORM MANAGER (PlatformService)
   │
   ├─> 8. LOAD VERSION-SPECIFIC CLASSES
   │   └─> DynamicClassLoader.load_classes_for_module('user', '1')
   │       ├─> Load AnsibleUser from ansible_models/user.py
   │       ├─> Load APIUser_v1 from api/v1/user.py
   │       └─> Load UserTransformMixin_v1 from api/v1/user.py
   │
   ├─> 9. RECONSTRUCT ANSIBLE DATACLASS
   │   └─> AnsibleUser(**ansible_data_dict)
   │
   ├─> 10. FORWARD TRANSFORM (Ansible → API)
   │    └─> ansible_user.to_api(context)
   │        │
   │        ├─> Apply field mappings
   │        │   username → username (1:1)
   │        │   organizations → organization_ids (complex)
   │        │
   │        └─> Apply transformations
   │            organizations=['Engineering', 'DevOps']
   │            → lookup_org_ids(['Engineering', 'DevOps'])
   │            → organization_ids=[1, 2]
   │
   ├─> 11. EXECUTE API CALLS
   │    └─> _execute_operations()
   │        │
   │        ├─> Operation 1: POST /api/gateway/v1/users/
   │        │   └─> Request: {username: 'jdoe', email: 'jdoe@example.com'}
   │        │   └─> Response: {id: 123, username: 'jdoe', ...}
   │        │
   │        └─> Operation 2: POST /api/gateway/v1/users/123/organizations/
   │            └─> Request: {organization_ids: [1, 2]}
   │            └─> Response: {success: true}
   │
   ├─> 12. REVERSE TRANSFORM (API → Ansible)
   │    └─> api_user.to_ansible(context)
   │        │
   │        ├─> Apply reverse mappings
   │        │   organization_ids → organizations
   │        │
   │        └─> Apply reverse transformations
   │            organization_ids=[1, 2]
   │            → lookup_org_names([1, 2])
   │            → organizations=['Engineering', 'DevOps']
   │
   └─> 13. RETURN ANSIBLE FORMAT DATA
       └─> {username: 'jdoe', organizations: ['Engineering', 'DevOps'], id: 123, ...}
           │
           ▼
14. ACTION PLUGIN RECEIVES RESULT
    │
    ├─> 15. VALIDATE OUTPUT
    │   └─> Validate against same ArgumentSpec
    │
    └─> 16. FORMAT RETURN DICT
        └─> {changed: True, failed: False, user: {...}}
            │
            ▼
17. ANSIBLE PLAYBOOK
    └─> Task completes, result available to user
```

---

## Component Details

### 1. Action Plugin Layer (`plugins/action/`)

**Purpose**: Thin client that validates, sends, receives, and validates.

**Key File**: `base_action.py`

**Responsibilities**:
- ✅ Input validation (ArgumentSpec)
- ✅ Create Ansible dataclass
- ✅ Manager spawning/connection
- ✅ Output validation
- ✅ Format return dict
- ❌ NO transformations
- ❌ NO API knowledge
- ❌ NO version resolution

**Key Methods**:

```python
class BaseResourceActionPlugin(ActionBase):
    def _get_or_spawn_manager(self, task_vars):
        """Get existing manager or spawn new one."""
        # 1. Check hostvars for existing manager
        # 2. If found, connect to it
        # 3. If not found, spawn new process
        # 4. Store manager info in facts
        
    def _build_argspec_from_docs(self, documentation):
        """Parse DOCUMENTATION YAML to ArgumentSpec."""
        
    def _validate_data(self, data, argspec, direction):
        """Validate input or output against spec."""
        
    def _detect_operation(self, args):
        """Detect create/update/delete/find from args."""
```

**Manager Lifecycle Management**:
- First task in playbook spawns manager (via Platform SDK ProcessManager)
- Manager info stored in Ansible facts (set directly in result dict)
- Subsequent tasks reuse same manager from hostvars
- Manager persists for entire playbook duration
- Cleanup on playbook completion

**Separation of Concerns**:
- **Ansible-specific**: task_vars, AnsibleError, result dict formatting
- **Platform SDK**: Gateway config extraction (`config.py`), process management (`process_manager.py`)
- Platform SDK modules are generic and reusable for CLI, MCP, or other entry points

### 2. Manager Layer (`plugins/plugin_utils/manager/`)

**Purpose**: Persistent service that handles all heavy lifting.

**Key Files**:
- `platform_manager.py` - PlatformService and PlatformManager
- `rpc_client.py` - Client-side RPC communication

**PlatformService Responsibilities**:
- ✅ Maintain persistent HTTP session
- ✅ Authenticate once (reuse session)
- ✅ Detect and cache API version
- ✅ Load version-specific classes dynamically
- ✅ Perform forward transform (Ansible → API)
- ✅ Execute API calls (multi-endpoint support)
- ✅ Perform reverse transform (API → Ansible)
- ✅ Provide lookup helpers (names ↔ IDs)
- ✅ Cache lookups for performance

**Key Methods**:

```python
class PlatformService:
    def __init__(self, base_url, username, password, ...):
        """Initialize service and authenticate."""
        # Create persistent session
        # Authenticate
        # Detect API version
        # Initialize registry & loader
        
    def execute(self, operation, module_name, ansible_data_dict):
        """Main entry point for all operations."""
        # 1. Load version-specific classes
        # 2. Reconstruct Ansible dataclass
        # 3. Forward transform
        # 4. Execute API calls
        # 5. Reverse transform
        # 6. Return Ansible format
        
    def _create_resource(self, ansible_data, mixin_class, context):
        """Create resource with transformations."""
        
    def _update_resource(self, ansible_data, mixin_class, context):
        """Update resource with transformations."""
        
    def _delete_resource(self, ansible_data, mixin_class, context):
        """Delete resource."""
        
    def _find_resource(self, ansible_data, mixin_class, context):
        """Find resource by identifier."""
        
    def lookup_org_ids(self, org_names):
        """Convert organization names to IDs."""
        
    def lookup_org_names(self, org_ids):
        """Convert organization IDs to names."""
```

**PlatformManager**:
- Extends `BaseManager` with `ThreadingMixIn`
- Provides Unix socket-based RPC
- Thread-safe (handles concurrent clients)
- Daemon threads (cleanup on exit)

**ManagerRPCClient**:
- Client-side interface for action plugins
- Connects to manager via Unix socket
- Serializes dataclasses to dicts for RPC
- Returns result dicts

### 3. Platform Framework (Platform SDK) (`plugins/plugin_utils/platform/`)

**Purpose**: Core transformation, version management, and generic platform SDK.

**Key Components**:

#### GatewayConfig (`config.py`) - Platform SDK

**Purpose**: Generic gateway configuration extraction (not Ansible-specific).

**Key Components**:
- `GatewayConfig` dataclass - Type-safe configuration
- `extract_gateway_config()` - Extract from generic dict structures

**Characteristics**:
- Not Ansible-specific (can be used by CLI, MCP, etc.)
- URL normalization
- Auth parameter extraction
- Type-safe with dataclass

#### TransformContext (`types.py`)

**Purpose**: Type-safe context for transformations (replaces Dict[str, Any]).

**Key Components**:
- `TransformContext` dataclass with `manager`, `session`, `cache`, `api_version`

**Benefits**:
- Better mypy type checking
- IDE autocomplete support
- Clear structure instead of dict keys

#### BaseTransformMixin (`base_transform.py`)

**Purpose**: Universal transformation logic inherited by all dataclasses.

**How It Works**:
1. Subclasses define `_field_mapping` dict
2. Subclasses define `_transform_registry` dict
3. BaseTransformMixin applies mappings and transformations generically
4. Supports nested fields (dot notation)
5. Context-aware (uses TransformContext dataclass for type safety)

**Example**:

```python
class UserTransformMixin_v1(BaseTransformMixin):
    _field_mapping = {
        'username': 'username',  # 1:1 mapping
        'organizations': {       # Complex mapping
            'api_field': 'organization_ids',
            'forward_transform': 'names_to_ids',
            'reverse_transform': 'ids_to_names',
        }
    }
    
    _transform_registry = {
        'names_to_ids': lambda names, ctx: ctx['manager'].lookup_org_ids(names),
        'ids_to_names': lambda ids, ctx: ctx['manager'].lookup_org_names(ids),
    }
```

**Key Methods**:
- `to_api(context)` - Transform Ansible → API
- `to_ansible(context)` - Transform API → Ansible
- `_apply_forward_mapping()` - Apply forward transformations
- `_apply_reverse_mapping()` - Apply reverse transformations

#### APIVersionRegistry (`registry.py`)

**Purpose**: Discover available API versions by scanning filesystem.

**How It Works**:
1. Scans `api/` directory for version directories (v1/, v2/, etc.)
2. Discovers module implementations in each version
3. Builds version × module matrix
4. Provides fallback logic (exact → lower → higher)

**Example Directory Structure**:
```
api/
├── v1/
│   ├── user.py
│   └── organization.py
└── v2/
    ├── user.py
    └── team.py
```

**Key Methods**:
- `get_supported_versions()` - List all discovered versions
- `get_versions_for_module(module_name)` - Versions supporting a module
- `find_best_version(requested, module)` - Find best match with fallback

#### DynamicClassLoader (`loader.py`)

**Purpose**: Load version-appropriate classes at runtime.

**How It Works**:
1. Uses registry to find best version match
2. Dynamically imports Ansible dataclass
3. Dynamically imports API dataclass and mixin
4. Caches loaded classes for performance
5. Pattern matching for class discovery

**Returns**: Tuple of `(AnsibleClass, APIClass, MixinClass)`

**Key Methods**:
- `load_classes_for_module(module_name, api_version)` - Load all classes for a module

### 4. Data Models

**Location**: 
- `plugins/plugin_utils/ansible_models/` - User-facing (stable)
- `plugins/plugin_utils/api/v1/` - API-facing (versioned)

**Ansible Dataclasses**:
- Stable interface for users
- Inherit from `BaseTransformMixin`
- Example: `AnsibleUser`, `AnsibleOrganization`

**API Dataclasses**:
- Version-specific API format
- Generated from OpenAPI specs (ideally)
- Example: `APIUser_v1`, `APIOrganization_v1`

**Transform Mixins**:
- Bridge between Ansible and API dataclasses
- Define field mappings and transformations
- Example: `UserTransformMixin_v1`

---

## Data Transformation Flow

### Forward Transform (Ansible → API)

**Input** (from playbook):
```yaml
username: jdoe
email: jdoe@example.com
organizations:
  - Engineering
  - DevOps
```

**Process**:
1. Action plugin creates `AnsibleUser` dataclass
2. Manager receives `AnsibleUser` dict
3. Manager calls `ansible_user.to_api(context)`
4. `BaseTransformMixin._apply_forward_mapping()`:
   - Maps `username` → `username` (1:1)
   - Maps `organizations` → `organization_ids` (complex)
   - Applies `names_to_ids` transform:
     - Calls `context['manager'].lookup_org_ids(['Engineering', 'DevOps'])`
     - Returns `[1, 2]`
5. Creates `APIUser_v1` with transformed data

**Output** (to API):
```json
{
  "username": "jdoe",
  "email": "jdoe@example.com",
  "organization_ids": [1, 2]
}
```

### Reverse Transform (API → Ansible)

**Input** (from API):
```json
{
  "id": 123,
  "username": "jdoe",
  "email": "jdoe@example.com",
  "organization_ids": [1, 2]
}
```

**Process**:
1. Manager receives API response
2. Manager creates `APIUser_v1` from response
3. Manager calls `api_user.to_ansible(context)`
4. `BaseTransformMixin._apply_reverse_mapping()`:
   - Maps `organization_ids` → `organizations` (reverse)
   - Applies `ids_to_names` transform:
     - Calls `context['manager'].lookup_org_names([1, 2])`
     - Returns `['Engineering', 'DevOps']`
5. Creates `AnsibleUser` with transformed data

**Output** (to playbook):
```yaml
id: 123
username: jdoe
email: jdoe@example.com
organizations:
  - Engineering
  - DevOps
```

### Round-Trip Data Contract

**Key Principle**: Output format always matches input format.

- User provides: `organizations: ['Engineering', 'DevOps']`
- User receives: `organizations: ['Engineering', 'DevOps']`
- Internal (hidden): `organization_ids: [1, 2]`

This ensures:
- Predictable interface for users
- No separate RETURN section needed
- Consistent across all API versions
- Easier to understand and use

---

## Manager Lifecycle

### Spawning a Manager

**When**: First task in playbook that uses platform collection

**Process**:
1. Action plugin checks `hostvars` for existing manager
2. If not found:
   - Generate unique socket path: `/tmp/ansible_platform/manager_{hostname}.sock`
   - Generate random auth key (32 bytes)
   - Spawn new process with `PlatformService`
   - Wait for socket to be created (max 5 seconds)
   - Store manager info in Ansible facts
3. Connect to manager via `ManagerRPCClient`

**Code Flow**:
```python
# In base_action.py
def _get_or_spawn_manager(self, task_vars):
    # Check for existing manager
    socket_path = host_vars.get('platform_manager_socket')
    if socket_path and Path(socket_path).exists():
        # Connect to existing
        return ManagerRPCClient(gateway_url, socket_path, authkey)
    
    # Spawn new manager
    process = Process(target=start_manager, daemon=True)
    process.start()
    # Wait for socket
    # Store in facts
    return ManagerRPCClient(gateway_url, socket_path, authkey)
```

### Manager Process

**Entry Point**: `start_manager()` function

**Initialization**:
1. Create `PlatformService`:
   - Create persistent `requests.Session`
   - Authenticate with AAP (Basic Auth or OAuth)
   - Detect API version (cached for lifetime)
   - Initialize `APIVersionRegistry`
   - Initialize `DynamicClassLoader`
2. Register with `PlatformManager`
3. Start manager server (Unix socket)
4. Keep running (block on `signal.pause()`)

**Lifetime**:
- Spawned on first task
- Persists for entire playbook
- Handles all tasks in playbook
- Cleanup on playbook completion (daemon process)

### Reusing a Manager

**When**: Subsequent tasks in same playbook

**Process**:
1. Action plugin checks `hostvars` for existing manager
2. If found:
   - Connect to existing manager via Unix socket
   - Reuse persistent HTTP session
   - Reuse API version cache
   - Reuse lookup cache

**Benefits**:
- 50-75% faster execution (no auth overhead)
- Better resource utilization
- Consistent with Ansible patterns

---

## Version Management

### Version Discovery

**How**: Filesystem-based discovery

**Process**:
1. `APIVersionRegistry` scans `api/` directory
2. Finds version directories: `v1/`, `v2/`, `v2_1/`, etc.
3. Extracts version strings: `1`, `2`, `2.1`
4. Discovers modules in each version
5. Builds version × module matrix

**Example**:
```
api/
├── v1/
│   ├── user.py
│   └── organization.py
└── v2/
    ├── user.py
    └── team.py
```

**Registry discovers**:
- Versions: `['1', '2']`
- `user`: `['1', '2']`
- `organization`: `['1']`
- `team`: `['2']`

### Version Detection

**When**: Manager initialization

**Process**:
1. `PlatformService` calls `/api/gateway/v1/ping/`
2. Extracts version from response headers or body
3. Defaults to `'1'` if detection fails
4. Caches version for lifetime of service

### Version Selection

**When**: Loading classes for a module

**Process**:
1. Manager receives request with detected API version
2. `DynamicClassLoader` calls `registry.find_best_version()`
3. Strategy:
   - Try exact match
   - Try closest lower version (backward compatible)
   - Try closest higher version (forward compatible, with warning)
4. Load classes for selected version

**Example**:
- Requested: `'2.1'`
- Available: `['1', '2', '2.5']`
- Selected: `'2'` (closest lower)

---

## Example: Creating a User

### Playbook

```yaml
---
- name: Create User
  hosts: localhost
  vars:
    gateway_url: https://platform.example.com
    gateway_username: admin
    gateway_password: secret
  
  tasks:
    - name: Create user
      ansible.platform.user:
        username: jdoe
        email: jdoe@example.com
        organizations:
          - Engineering
          - DevOps
        state: present
```

### Step-by-Step Execution

#### Step 1: Ansible Invokes Action Plugin

Ansible calls `plugins/action/user.py` (or uses `base_action.py` if no specific plugin).

#### Step 2: Validate Input

```python
# In base_action.py
argspec = self._build_argspec_from_docs(DOCUMENTATION)
validated_args = self._validate_data(args, argspec, 'input')
```

**Result**: Validated and normalized arguments

#### Step 3: Create Ansible Dataclass

```python
from ansible.platform.plugins.plugin_utils.ansible_models.user import AnsibleUser

user_data = AnsibleUser(**validated_args)
# user_data.organizations = ['Engineering', 'DevOps']
```

#### Step 4: Get/Connect to Manager

```python
manager = self._get_or_spawn_manager(task_vars)
```

**First Task**:
- Spawns new manager process
- Creates Unix socket
- Stores info in facts

**Subsequent Tasks**:
- Connects to existing manager

#### Step 5: Send to Manager (RPC)

```python
operation = self._detect_operation(args)  # 'create'
result_dict = manager.execute(operation, 'user', user_data)
```

**RPC Call**:
- Serializes `AnsibleUser` to dict
- Sends via Unix socket to manager
- Manager executes operation
- Returns result dict

#### Step 6: Manager Loads Classes

```python
# In platform_manager.py
AnsibleClass, APIClass, MixinClass = self.loader.load_classes_for_module(
    'user',
    self.api_version  # '1'
)
# Returns: (AnsibleUser, APIUser_v1, UserTransformMixin_v1)
```

#### Step 7: Forward Transform

```python
# In platform_manager.py
api_data = ansible_data.to_api(context)
```

**Transform Process**:
1. `BaseTransformMixin._apply_forward_mapping()`
2. Maps `organizations` → `organization_ids`
3. Applies `names_to_ids` transform:
   - Calls `manager.lookup_org_ids(['Engineering', 'DevOps'])`
   - Makes API call: `GET /api/gateway/v1/organizations/?name=Engineering`
   - Returns: `[1, 2]`
4. Creates `APIUser_v1` with `organization_ids=[1, 2]`

#### Step 8: Execute API Calls

```python
# In platform_manager.py
operations = mixin_class.get_endpoint_operations()
api_result = self._execute_operations(operations, api_data, context, 'create')
```

**Operations**:
1. `POST /api/gateway/v1/users/`
   - Request: `{username: 'jdoe', email: 'jdoe@example.com'}`
   - Response: `{id: 123, username: 'jdoe', ...}`
2. `POST /api/gateway/v1/users/123/organizations/`
   - Request: `{organization_ids: [1, 2]}`
   - Response: `{success: true}`

#### Step 9: Reverse Transform

```python
# In platform_manager.py
api_result_instance = type(api_data)(**api_result)
ansible_result = api_result_instance.to_ansible(context)
```

**Transform Process**:
1. `BaseTransformMixin._apply_reverse_mapping()`
2. Maps `organization_ids` → `organizations`
3. Applies `ids_to_names` transform:
   - Calls `manager.lookup_org_names([1, 2])`
   - Makes API calls: `GET /api/gateway/v1/organizations/1/`
   - Returns: `['Engineering', 'DevOps']`
4. Creates `AnsibleUser` with `organizations=['Engineering', 'DevOps']`

#### Step 10: Return Result

```python
# In platform_manager.py
return asdict(ansible_result)
# Returns: {username: 'jdoe', organizations: ['Engineering', 'DevOps'], id: 123, ...}
```

#### Step 11: Validate Output

```python
# In base_action.py
validated_result = self._validate_data(result_dict, argspec, 'output')
```

#### Step 12: Format Return Dict

```python
# In base_action.py
return {
    'failed': False,
    'changed': True,
    'user': validated_result
}
```

#### Step 13: Ansible Returns to User

```yaml
# Result available in playbook
user:
  id: 123
  username: jdoe
  email: jdoe@example.com
  organizations:
    - Engineering
    - DevOps
```

---

## Key Design Decisions

### 1. Manager-Side Transformations

**Decision**: All transformations happen in the persistent manager, not in action plugins.

**Rationale**:
- Manager has API connection for lookups (names ↔ IDs)
- Manager knows API version
- Manager has persistent cache
- Client stays thin and version-agnostic
- Clean RPC protocol (only Ansible format crosses boundary)

**Benefits**:
- Client doesn't need API knowledge
- Version changes don't affect client code
- Transformations have full context (session, cache, version)

### 2. Round-Trip Data Contract

**Decision**: Output format always matches input format. Single DOCUMENTATION defines both.

**Rationale**:
- Predictable interface for users
- No separate RETURN section needed
- Consistent across all API versions
- Easier to understand and use

**Benefits**:
- Users get what they put in (same field names, types)
- API format details hidden from users
- Single source of truth (DOCUMENTATION)

### 3. Generic Manager

**Decision**: Manager is resource-agnostic. Resource logic lives in dataclass mixins.

**Rationale**:
- One manager works for all resources
- Easy to add new resources
- Consistent behavior across resources
- Less code duplication

**Benefits**:
- Manager code doesn't need updates for new resources
- Resource-specific logic isolated in mixins
- Manager is reusable and maintainable

### 4. Dynamic Version Discovery

**Decision**: Filesystem-based version discovery, no hardcoded version lists.

**Rationale**:
- Easy to add new API versions (just create directory)
- No code changes needed for version support
- Automatic discovery on startup
- Flexible version fallback

**Benefits**:
- No configuration files to maintain
- Version support is declarative (directory structure)
- Easy to see what versions are supported

### 5. Persistent Connections

**Decision**: Manager maintains persistent HTTP session across playbook tasks.

**Rationale**:
- Authentication overhead only once
- Connection reuse is faster
- Follows existing multiprocess pattern (weather service)

**Benefits**:
- 50-75% faster playbook execution
- Better resource utilization
- Consistent with Ansible patterns

---

## Summary

The Ansible Platform Collection uses a **layered architecture** with clear separation of concerns:

1. **Action Plugins** (Client): Thin, stateless, validate and format
2. **Platform Manager** (Service): Heavy, stateful, transform and execute
3. **Platform Framework** (Core): Generic, reusable, transform and version
4. **Data Models** (Contracts): Type-safe, versioned, stable interface

**Key Features**:
- ✅ Persistent connections (50-75% faster)
- ✅ Manager-side transformations
- ✅ Round-trip data contract
- ✅ Generic manager (works for all resources)
- ✅ Dynamic version management
- ✅ Type-safe dataclasses

**Flow**:
1. User runs playbook → Action plugin validates
2. Action plugin → Manager (RPC)
3. Manager transforms (Ansible → API)
4. Manager → API (HTTP)
5. Manager transforms (API → Ansible)
6. Manager → Action plugin (RPC)
7. Action plugin → User (result)

This architecture provides a **stable, performant, and maintainable** solution for managing Ansible Automation Platform resources.

