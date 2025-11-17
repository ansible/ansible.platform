# Ansible Platform Collection - Architecture Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architecture Goals](#architecture-goals)
3. [System Architecture](#system-architecture)
4. [Component Details](#component-details)
5. [Data Flow](#data-flow)
6. [Key Design Decisions](#key-design-decisions)
7. [Migration from Legacy Architecture](#migration-from-legacy-architecture)

---

## Overview

The Ansible Platform Collection provides action plugins for managing Ansible Automation Platform (AAP) Gateway resources (users, organizations, teams, etc.) with automatic API version adaptation and code generation capabilities.

### Key Features

- **Persistent Connections**: Manager service maintains HTTP sessions across playbook tasks (50-75% faster execution)
- **Manager-Side Transformations**: All data transformations happen in the persistent manager, not in action plugins
- **Round-Trip Data Contract**: Output format always matches input format (single DOCUMENTATION source)
- **Generic Manager**: Resource-agnostic manager works for all modules
- **Dynamic Version Management**: Filesystem-based version discovery, no hardcoded version lists
- **Code Generation**: Automated dataclass generation from docstrings and OpenAPI specs

---

## Architecture Goals

### 1. User-Facing Stability
Ansible playbook interface remains stable across API versions. Users don't need to change playbooks when the platform API changes.

### 2. Code Generation
Minimize manual coding through automated generation from docstrings and OpenAPI specs. Target: 80% automated, 20% manual.

### 3. Version Flexibility
Support multiple API versions dynamically without hardcoding. Automatic version detection and fallback.

### 4. Performance
Maintain persistent platform connections for faster playbook execution. Reuse HTTP sessions across tasks.

### 5. Type Safety
Strong typing throughout with validation at multiple layers (input, transformation, output).

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Ansible Playbook                         │
│  - Stable YAML interface                                    │
│  - Version-agnostic                                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              CLIENT LAYER (Action Plugins)                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  BaseResourceActionPlugin                            │  │
│  │  - Input validation (ArgumentSpec)                   │  │
│  │  - Create Ansible dataclass                          │  │
│  │  - Manager spawning/connection                       │  │
│  │  - Output validation                                 │  │
│  │  - Format return dict                                │  │
│  │                                                      │  │
│  │  NO transformations                                 │  │
│  │  NO API knowledge                                    │  │
│  │  NO version resolution                               │  │
│  └──────────────────┬───────────────────────────────────┘  │
└──────────────────────┼──────────────────────────────────────┘
                       │
                       │ RPC (Ansible dataclasses only)
                       │
┌──────────────────────▼──────────────────────────────────────┐
│           MANAGER LAYER (Persistent Service)                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  PlatformService (PlatformManager)                   │  │
│  │  - Persistent HTTP session                           │  │
│  │  - API version detection & caching                   │  │
│  │  - Dynamic class loading                             │  │
│  │  - FORWARD TRANSFORM (Ansible → API)                │  │
│  │  - API calls (multi-endpoint support)                │  │
│  │  - REVERSE TRANSFORM (API → Ansible)                 │  │
│  │  - Lookup helpers (names ↔ IDs)                     │  │
│  │                                                      │  │
│  │  Generic: Works for ALL resources                   │  │
│  └──────────────────┬───────────────────────────────────┘  │
└──────────────────────┼──────────────────────────────────────┘
                       │
                       │ HTTP/HTTPS
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Platform API (AAP Gateway)                      │
│  - REST API endpoints                                        │
│  - Version-specific schemas                                  │
│  - Authentication (Basic/OAuth)                              │
└─────────────────────────────────────────────────────────────┘
```

### Component Layers

#### Layer 1: Client (Action Plugins)
- **Location**: `plugins/action/`
- **Responsibility**: Thin client that validates, sends, receives, and validates
- **Key File**: `base_action.py` - Base class for all resource action plugins
- **Characteristics**:
  - Stateless
  - No API knowledge
  - No transformations
  - Manager lifecycle management

#### Layer 2: Manager (Persistent Service)
- **Location**: `plugins/plugin_utils/manager/`
- **Responsibility**: Heavy lifting - transformations, API calls, version management
- **Key Files**:
  - `platform_manager.py` - PlatformService and PlatformManager
  - `rpc_client.py` - Client-side RPC communication
- **Characteristics**:
  - Stateful (persistent session)
  - Resource-agnostic
  - All transformations
  - Version-aware

#### Layer 3: Platform Framework
- **Location**: `plugins/plugin_utils/platform/`
- **Responsibility**: Core transformation and version management
- **Key Files**:
  - `base_transform.py` - BaseTransformMixin (universal transformation)
  - `types.py` - Shared types (EndpointOperation)
  - `registry.py` - APIVersionRegistry (version discovery)
  - `loader.py` - DynamicClassLoader (runtime class loading)
- **Characteristics**:
  - Generic, reusable
  - No resource-specific code
  - Filesystem-based discovery

#### Layer 4: Data Models
- **Location**: `plugins/plugin_utils/ansible_models/` and `plugins/plugin_utils/api/`
- **Responsibility**: Type-safe data structures
- **Key Files**:
  - `ansible_models/` - User-facing dataclasses (stable)
  - `api/v1/` - API dataclasses (versioned)
  - `docs/` - DOCUMENTATION strings (source of truth)
- **Characteristics**:
  - Generated from docstrings/OpenAPI
  - Type-safe
  - Round-trip contract

---

## Component Details

### 1. BaseTransformMixin

**Purpose**: Universal transformation logic inherited by all dataclasses.

**Location**: `plugins/plugin_utils/platform/base_transform.py`

**Key Methods**:
- `to_api(context)` - Transform Ansible → API format
- `to_ansible(context)` - Transform API → Ansible format
- `_apply_forward_mapping()` - Apply forward transformations
- `_apply_reverse_mapping()` - Apply reverse transformations

**How It Works**:
1. Subclasses define `_field_mapping` dict
2. Subclasses define `_transform_registry` dict
3. BaseTransformMixin applies mappings and transformations generically
4. Supports nested fields (dot notation)
5. Context-aware (can access manager for lookups)

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

### 2. APIVersionRegistry

**Purpose**: Discover available API versions by scanning filesystem.

**Location**: `plugins/plugin_utils/platform/registry.py`

**Key Methods**:
- `get_supported_versions()` - List all discovered versions
- `get_versions_for_module(module_name)` - Versions supporting a module
- `find_best_version(requested, module)` - Find best match with fallback

**How It Works**:
1. Scans `api/` directory for version directories (v1/, v2/, etc.)
2. Discovers module implementations in each version
3. Builds version × module matrix
4. Provides fallback logic (exact → lower → higher)

**Example**:
```
api/
├── v1/
│   ├── user.py
│   └── organization.py
└── v2/
    ├── user.py
    └── team.py

Registry discovers:
- Versions: ['1', '2']
- user: ['1', '2']
- organization: ['1']
- team: ['2']
```

### 3. DynamicClassLoader

**Purpose**: Load version-appropriate classes at runtime.

**Location**: `plugins/plugin_utils/platform/loader.py`

**Key Methods**:
- `load_classes_for_module(module_name, api_version)` - Load all classes for a module

**How It Works**:
1. Uses registry to find best version match
2. Dynamically imports Ansible dataclass
3. Dynamically imports API dataclass and mixin
4. Caches loaded classes for performance
5. Pattern matching for class discovery

**Returns**: Tuple of (AnsibleClass, APIClass, MixinClass)

### 4. PlatformService

**Purpose**: Persistent service that handles all API communication and transformations.

**Location**: `plugins/plugin_utils/manager/platform_manager.py`

**Key Methods**:
- `execute(operation, module_name, ansible_data_dict)` - Main entry point
- `_create_resource()` - Create with transformations
- `_update_resource()` - Update with transformations
- `_delete_resource()` - Delete resource
- `_find_resource()` - Find resource
- `_execute_operations()` - Multi-endpoint orchestration

**How It Works**:
1. Maintains persistent `requests.Session`
2. Detects and caches API version on startup
3. Loads version-specific classes via DynamicClassLoader
4. Performs forward transform (Ansible → API)
5. Executes API calls (potentially multiple endpoints)
6. Performs reverse transform (API → Ansible)
7. Returns Ansible-format data

**Authentication**:
- Supports Basic Auth (username/password)
- Supports OAuth Token (Bearer token)
- Authenticates once on service creation
- Session persists across requests

### 5. PlatformManager

**Purpose**: Multiprocessing Manager for sharing PlatformService across processes.

**Location**: `plugins/plugin_utils/manager/platform_manager.py`

**How It Works**:
1. Extends `BaseManager` with `ThreadingMixIn`
2. Registers `get_platform_service()` method
3. Uses Unix domain socket for communication
4. Thread-safe (multiple concurrent clients)
5. Daemon threads (cleanup on exit)

### 6. ManagerRPCClient

**Purpose**: Client-side interface for communicating with PlatformManager.

**Location**: `plugins/plugin_utils/manager/rpc_client.py`

**Key Methods**:
- `execute(operation, module_name, ansible_data)` - Execute operation via manager

**How It Works**:
1. Connects to manager via Unix socket
2. Gets proxy to PlatformService
3. Serializes dataclass to dict
4. Calls manager method via proxy
5. Returns result dict

### 7. BaseResourceActionPlugin

**Purpose**: Base class for all resource action plugins.

**Location**: `plugins/action/base_action.py`

**Key Methods**:
- `_get_or_spawn_manager(task_vars)` - Get or spawn manager
- `_build_argspec_from_docs(documentation)` - Parse DOCUMENTATION
- `_validate_data(data, argspec, direction)` - Validate input/output
- `_detect_operation(args)` - Detect create/update/delete/find

**How It Works**:
1. Checks hostvars for existing manager
2. If found, connects to existing manager
3. If not found, spawns new manager process
4. Stores manager info in facts for reuse
5. Validates input before sending to manager
6. Validates output after receiving from manager
7. Formats return dict for Ansible

**Manager Lifecycle**:
- First task spawns manager
- Subsequent tasks reuse same manager
- Manager persists for playbook duration
- Cleanup on playbook completion

---

## Data Flow

### Complete Request Flow

```
1. PLAYBOOK TASK
   └─> Action Plugin (user.py)
       │
       ├─> 2. Validate Input (ArgumentSpec)
       │   └─> DOCUMENTATION string
       │
       ├─> 3. Create AnsibleUser dataclass
       │   └─> organizations=['Engineering', 'DevOps']  # Names
       │
       ├─> 4. Get/Connect to Manager
       │   └─> ManagerRPCClient
       │
       └─> 5. Send to Manager (RPC)
           └─> execute('create', 'user', ansible_user_dict)
               │
               ▼
6. PLATFORM MANAGER (PlatformService)
   │
   ├─> 7. Load Version-Specific Classes
   │   └─> AnsibleUser, APIUser_v1, UserTransformMixin_v1
   │
   ├─> 8. Reconstruct AnsibleUser from dict
   │
   ├─> 9. FORWARD TRANSFORM (Ansible → API)
   │   └─> UserTransformMixin_v1.to_api(context)
   │       │
   │       ├─> Apply field mappings
   │       │   username → username
   │       │   organizations → organization_ids
   │       │
   │       └─> Apply transformations
   │           organizations=['Engineering'] → lookup_org_ids()
   │           → organization_ids=[1]
   │
   ├─> 10. Execute API Calls
   │    │
   │    ├─> POST /api/gateway/v1/users/
   │    │   └─> {username: 'jdoe', email: 'jdoe@example.com'}
   │    │   └─> Response: {id: 123, username: 'jdoe', ...}
   │    │
   │    └─> POST /api/gateway/v1/users/123/organizations/
   │        └─> {organization_ids: [1, 2]}
   │        └─> Response: {success: true}
   │
   ├─> 11. REVERSE TRANSFORM (API → Ansible)
   │    └─> APIUser_v1.to_ansible(context)
   │        │
   │        ├─> Apply reverse mappings
   │        │   organization_ids → organizations
   │        │
   │        └─> Apply reverse transformations
   │            organization_ids=[1, 2] → lookup_org_names()
   │            → organizations=['Engineering', 'DevOps']
   │
   └─> 12. Return AnsibleUser dict
       └─> {username: 'jdoe', organizations: ['Engineering', 'DevOps'], ...}
           │
           ▼
13. ACTION PLUGIN
    │
    ├─> 14. Validate Output (ArgumentSpec)
    │   └─> Same spec as input validation
    │
    └─> 15. Format Return Dict
        └─> {changed: True, failed: False, user: {...}}
            │
            ▼
16. ANSIBLE PLAYBOOK
    └─> Task completes, result available
```

### Round-Trip Data Contract

**Key Principle**: Output format matches input format.

**Input** (from playbook):
```yaml
username: jdoe
organizations:
  - Engineering
  - DevOps
```

**Output** (to playbook):
```yaml
username: jdoe
organizations:
  - Engineering
  - DevOps
id: 123
created: '2025-01-15T10:30:00Z'
```

**Internal** (never exposed to client):
```json
{
  "username": "jdoe",
  "organization_ids": [1, 2]  // API format
}
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

## Migration from Legacy Architecture

### Legacy Architecture (Current)

**Structure**:
```
plugins/
├── modules/
│   └── user.py  # Direct AnsibleModule subclass
└── module_utils/
    ├── aap_module.py  # Base module with session
    └── aap_user.py    # Resource-specific logic
```

**Characteristics**:
- Each module creates its own session
- No persistent connections
- Transformations in module code
- No version management
- Manual field mapping

### New Architecture (This Implementation)

**Structure**:
```
plugins/
├── action/
│   ├── base_action.py  # Base action plugin
│   └── user.py         # Thin action plugin
└── plugin_utils/
    ├── manager/
    │   ├── platform_manager.py  # Persistent service
    │   └── rpc_client.py        # RPC client
    ├── platform/
    │   ├── base_transform.py    # Universal transforms
    │   ├── registry.py           # Version discovery
    │   └── loader.py             # Dynamic loading
    ├── ansible_models/
    │   └── user.py               # Ansible dataclass
    ├── api/
    │   └── v1/
    │       └── user.py           # Transform mixin
    └── docs/
        └── user.py               # DOCUMENTATION
```

**Characteristics**:
- Persistent manager service
- Reused connections
- Manager-side transformations
- Dynamic version management
- Automated field mapping

### Migration Strategy

1. **Keep legacy modules** - Don't break existing playbooks
2. **Add new action plugins** - New architecture alongside old
3. **Gradual migration** - Migrate resources one at a time
4. **Feature flag** - Allow choosing old vs new architecture
5. **Deprecation path** - Eventually deprecate legacy modules

---

## Next Steps

1. **Code Generation Tools** - Automate dataclass generation
2. **First Resource Migration** - Migrate user module as example
3. **Testing Framework** - Unit and integration tests
4. **Documentation** - User-facing documentation
5. **CI/CD Integration** - Automated testing and validation

---

## Related Documentation

- `FLOW_EXPLANATION.md` - High-level flow explanation
- `CODE_WALKTHROUGH.md` - Detailed step-by-step code walkthrough with line numbers
- `IMPLEMENTATION_GUIDE.md` - Step-by-step implementation guide
- `DEVELOPER_GUIDE.md` - How to add new resources
- `API_REFERENCE.md` - API documentation for components


