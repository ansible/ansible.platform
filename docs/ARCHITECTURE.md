# Ansible Platform Collection - Architecture Documentation

## Overview

This document describes the architecture of the Ansible Platform Collection POC implementation, which demonstrates the architecture proposed in [ANSTRAT-1640 SDP](../../handbook/The%20Ansible%20Engineering%20Handbook/System%20Design%20Plans/ANSTRAT-1640-persistent-connection-manager-for-ansible-platform-collection.md) and [P1 Proposal](../../handbook/The%20Ansible%20Engineering%20Handbook/proposals/ANSTRAT-1640-ANSTRAT-1640-Platform-API-Evolution.md).

### Key Features

- **Dual-Mode Connections**: Support for both direct (ephemeral managers) and persistent (long-lived managers) modes
- **Unified Architecture**: Both modes use the same manager process architecture with TransitMixin, API version detection, and Ansible dataclasses
- **API Version Management**: Filesystem-based version discovery and dynamic class loading
- **Action Plugin Architecture**: Migration from modules to action plugins (new architecture)
- **Shared Layers**: Both connection modes use the same layers (version detection, error handling, credentials, CRUD)
- **Quality Tooling**: Modern Python tooling (ruff, mypy, pydoclint) with automated checks

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
│  │  - Connection mode selection                          │  │
│  │  - Output validation                                 │  │
│  │  - Format return dict                                │  │
│  │                                                      │  │
│  │  NO transformations                                 │  │
│  │  NO API knowledge                                    │  │
│  │  NO version resolution                               │  │
│  └──────────────────┬───────────────────────────────────┘  │
└──────────────────────┼──────────────────────────────────────┘
                       │
                       │ Connection Mode Selection
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌──────────────────┐        ┌──────────────────┐
│   Direct Mode    │        │ Persistent Mode  │
│ ManagerRPCClient │        │ ManagerRPCClient │
│   → PlatformService│      │   → PlatformService│
│                  │        │                  │
│ - Ephemeral      │        │ - Long-lived      │
│ - Per-task       │        │ - Across tasks    │
│ - Shut down      │        │ - Reused session  │
│   after task     │        │ - Facts stored    │
└────────┬─────────┘        └────────┬──────────┘
         │                           │
         └───────────┬───────────────┘
                     │
                     │ Shared Architecture
                     │ - Manager Process
                     │ - TransitMixin
                     │ - API Version Detection
                     │ - Error Handling
                     │ - Credential Management
                     │ - CRUD Operations
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
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
  - Connection mode selection (standard vs experimental)

#### Layer 2: Connection Layer
- **Connection Plugin**: `plugins/connection/http.py`
  - Dispatcher pattern: Routes to persistent or direct mode based on `persistent` option
  - `get_client()` method returns appropriate client based on configuration
  
- **Direct Mode** (default, `persistent: false`): `plugins/plugin_utils/manager/`
  - Spawns ephemeral manager process per task
  - `ManagerRPCClient` - Client-side RPC communication to ephemeral manager
  - `PlatformService` - Manager process with HTTP session (shut down after task)
  - Uses shared architecture (TransitMixin, API version detection, error handling, credentials, CRUD)
  
- **Persistent Mode** (`persistent: true`): `plugins/plugin_utils/manager/`
  - Spawns or reuses long-lived manager process across tasks
  - `ManagerRPCClient` - Client-side RPC communication to persistent manager
  - `PlatformService` - Manager process with HTTP session reuse
  - Facts stored to enable manager reuse across tasks
  - Uses shared architecture (TransitMixin, API version detection, error handling, credentials, CRUD)

#### Layer 3: Platform Framework
- **Location**: `plugins/plugin_utils/platform/`
- **Responsibility**: Core transformation, version management, and shared utilities
- **Key Files**:
  - `base_client.py` - `BaseAPIClient` abstract class (shared interface)
  - `base_transform.py` - `BaseTransformMixin` (universal transformation)
  - `types.py` - Shared types (`TransformContext`, `EndpointOperation`)
  - `config.py` - `GatewayConfig` and gateway configuration extraction
  - `registry.py` - `APIVersionRegistry` (version discovery)
  - `loader.py` - `DynamicClassLoader` (runtime class loading)
  - `exceptions.py` - Error taxonomy
  - `retry.py` - Retry logic with exponential backoff
  - `credential_manager.py` - Credential management

#### Layer 4: Data Models
- **Location**: `plugins/plugin_utils/ansible_models/` and `plugins/plugin_utils/api/`
- **Responsibility**: Type-safe data structures
- **Key Files**:
  - `ansible_models/` - User-facing dataclasses (stable, version-agnostic)
  - `api/v1/` - API dataclasses and transform mixins (version-specific)
  - `api/v2/` - Future API version implementations
  - `docs/` - DOCUMENTATION strings (source of truth)

## Component Details

### 1. BaseAPIClient

**Purpose**: Abstract base class defining the common interface for both connection modes.

**Location**: `plugins/plugin_utils/platform/base_client.py`

**Key Methods**:
- `execute(operation, module_name, ansible_data)` - Execute CRUD operation
- `_detect_api_version()` - Detect API version from platform
- `_authenticate()` - Authenticate with platform
- `get_api_version()` - Get detected API version
- `lookup_organization_ids(names)` - Lookup organization IDs by names
- `lookup_organization_names(ids)` - Lookup organization names by IDs
- `shutdown()` - Gracefully shut down client

**Shared Infrastructure**:
- `APIVersionRegistry` - Version discovery
- `DynamicClassLoader` - Dynamic class loading
- `cache` - Connection-level cache for lookups

### 2. Direct Mode (Ephemeral Managers)

**Purpose**: Ephemeral manager process for direct connection mode (default).

**Location**: `plugins/connection/http.py::_get_direct_client()`

**Characteristics**:
- Spawns new manager process per task
- Manager process uses `requests.Session` for HTTP requests
- Manager is shut down immediately after task completes
- Uses all shared architecture (TransitMixin, API version detection, error handling, credentials, CRUD)
- Cache persists for task lifetime only
- Socket path: `/tmp/ap/manager_<uid>_e<hash>_<cred_hash>.sock` (short path to avoid AF_UNIX limit)

### 3. PlatformService (Both Modes)

**Purpose**: Manager process service that handles all API communication and transformations.

**Location**: `plugins/plugin_utils/manager/platform_manager.py`

**Characteristics**:
- Uses `requests.Session` for HTTP requests
- Detects and caches API version on startup
- Loads version-specific classes via `DynamicClassLoader`
- Performs forward transform (Ansible → API) via TransitMixin
- Executes API calls (potentially multiple endpoints)
- Performs reverse transform (API → Ansible) via TransitMixin
- Cache persists for manager lifetime

**Lifecycle**:
- **Direct Mode**: Manager spawned per task, shut down immediately after task
- **Persistent Mode**: Manager spawned once, reused across tasks, shut down when play completes

### 4. APIVersionRegistry

**Purpose**: Discover available API versions by scanning filesystem.

**Location**: `plugins/plugin_utils/platform/registry.py`

**How It Works**:
1. Scans `api/` directory for version directories (`v1/`, `v2/`, etc.)
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

### 5. DynamicClassLoader

**Purpose**: Load version-appropriate classes at runtime.

**Location**: `plugins/plugin_utils/platform/loader.py`

**How It Works**:
1. Uses registry to find best version match
2. Dynamically imports Ansible dataclass
3. Dynamically imports API dataclass and transform mixin
4. Caches loaded classes for performance

**Returns**: Tuple of `(AnsibleClass, APIClass, MixinClass)`

### 6. BaseTransformMixin

**Purpose**: Universal transformation logic inherited by all dataclasses.

**Location**: `plugins/plugin_utils/platform/base_transform.py`

**Key Methods**:
- `to_api(context)` - Transform Ansible → API format
- `from_api(api_data, context)` - Transform API → Ansible format

**How It Works**:
1. Subclasses define `_field_mapping` dict
2. Subclasses define transform methods
3. BaseTransformMixin applies mappings and transformations generically
4. Context-aware (can access manager for lookups)

### 7. BaseResourceActionPlugin

**Purpose**: Base class for all resource action plugins.

**Location**: `plugins/action/base_action.py`

**Key Methods**:
- `_get_or_spawn_manager(task_vars)` - Get connection client based on mode
- `_build_argspec_from_docs(documentation)` - Parse DOCUMENTATION
- `_validate_data(data, argspec, direction)` - Validate input/output

**Connection Mode Selection**:
- Delegates to connection plugin's `get_client()` method
- Connection plugin checks `persistent` option (default: false)
- Direct mode (`persistent: false`) → Ephemeral `ManagerRPCClient` → `PlatformService` (shut down after task)
- Persistent mode (`persistent: true`) → Long-lived `ManagerRPCClient` → `PlatformService` (reused across tasks)

## Data Flow

### Direct Mode Flow (Default)

```
1. Playbook Task
   └─> Action Plugin
       ├─> Validate Input
       ├─> Create AnsibleUser dataclass
       ├─> Connection Plugin: get_client() (persistent: false)
       │   └─> Spawn ephemeral manager process
       │       └─> Wait for manager to be ready
       ├─> Get ManagerRPCClient (ephemeral)
       │   └─> Connect to PlatformService (ephemeral)
       ├─> Execute via RPC
       │   └─> PlatformService
       │       ├─> Load version-specific classes
       │       ├─> Forward transform (Ansible → API) via TransitMixin
       │       ├─> API call (new session)
       │       └─> Reverse transform (API → Ansible) via TransitMixin
       ├─> Validate Output
       ├─> Format Return Dict
       └─> Cleanup: Shut down ephemeral manager
```

### Persistent Mode Flow

```
1. Playbook Task
   └─> Action Plugin
       ├─> Validate Input
       ├─> Create AnsibleUser dataclass
       ├─> Connection Plugin: get_client() (persistent: true)
       │   └─> Check for existing manager in facts
       │       ├─> Found: Reuse existing manager
       │       └─> Not found: Spawn new manager, store facts
       ├─> Get ManagerRPCClient (persistent)
       │   └─> Connect to PlatformService (long-lived)
       ├─> Execute via RPC
       │   └─> PlatformService
       │       ├─> Load version-specific classes
       │       ├─> Forward transform (Ansible → API) via TransitMixin
       │       ├─> API call (reused session)
       │       └─> Reverse transform (API → Ansible) via TransitMixin
       ├─> Validate Output
       └─> Format Return Dict

2. Next Task (same play)
   └─> Reuses same manager from facts
       └─> (No manager spawn overhead)

3. Play Complete
   └─> Cleanup: Shut down persistent manager
```

## Key Design Decisions

### 1. Dual-Mode Connection Support

**Decision**: Support both direct (ephemeral managers) and persistent (long-lived managers) modes, both using the same manager process architecture.

**Rationale**:
- Both modes use the same architecture (TransitMixin, API version detection, Ansible dataclasses)
- Direct mode (default) provides simplicity: one manager per task, shut down immediately
- Persistent mode provides performance: manager reused across tasks, session reuse
- No worker process crashes: HTTP requests made in separate manager processes, not in action plugin worker
- Users can opt-in to persistent mode when performance is needed

**Benefits**:
- Unified architecture: same code path for both modes
- Performance optimization available via persistent mode
- Shared codebase reduces maintenance burden
- No HTTP request limitations: manager processes can safely make HTTP requests

### 2. Shared Layers

**Decision**: Both connection modes use the same shared infrastructure.

**Shared Components**:
- Version detection (`APIVersionRegistry`, `DynamicClassLoader`)
- Error taxonomy (`exceptions.py`, `retry.py`)
- Credential management (`credential_manager.py`)
- CRUD operations (transform mixins, endpoint operations)
- Caching (connection-level cache)

**Benefits**:
- Consistent behavior across modes
- Single codebase for shared logic
- Easier maintenance and testing

### 3. API Version Management

**Decision**: Filesystem-based version discovery with dynamic class loading.

**Rationale**:
- Easy to add new API versions (just create directory)
- No code changes needed for version support
- Automatic discovery on startup
- Flexible version fallback

**Benefits**:
- No hardcoded version lists
- Version support is declarative (directory structure)
- Easy to see what versions are supported

### 4. Action Plugin Architecture

**Decision**: Replace modules with action plugins.

**Rationale**:
- Avoid core serialization overhead
- Enable new architecture (version management, shared layers)
- Better separation of concerns

**Benefits**:
- Faster execution (no serialization overhead)
- Cleaner architecture
- Better maintainability

## Related Documentation

- **SDP**: [ANSTRAT-1640 SDP](../../handbook/The%20Ansible%20Engineering%20Handbook/System%20Design%20Plans/ANSTRAT-1640-persistent-connection-manager-for-ansible-platform-collection.md)
- **P1 Proposal**: [Platform API Evolution Proposal](../../handbook/The%20Ansible%20Engineering%20Handbook/proposals/ANSTRAT-1640-ANSTRAT-1640-Platform-API-Evolution.md)
- **Architecture Diagrams**: [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md)
