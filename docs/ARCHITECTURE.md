# Ansible Platform Collection - Architecture Documentation

## Overview

This document describes the architecture of the Ansible Platform Collection POC implementation, which demonstrates the architecture proposed in [ANSTRAT-1640 SDP](../../handbook/The%20Ansible%20Engineering%20Handbook/System%20Design%20Plans/ANSTRAT-1640-persistent-connection-manager-for-ansible-platform-collection.md) and [P1 Proposal](../../handbook/The%20Ansible%20Engineering%20Handbook/proposals/ANSTRAT-1640-ANSTRAT-1640-Platform-API-Evolution.md).

### Key Features

- **Dual-Mode Connections**: Support for both standard (direct HTTP) and experimental (persistent manager) modes
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
│  Standard Mode   │        │ Experimental Mode│
│ DirectHTTPClient │        │ ManagerRPCClient │
│                  │        │   → PlatformService│
│ - Direct HTTP    │        │ - Persistent      │
│ - Per-task       │        │ - Across tasks     │
│ - New session    │        │ - Reused session  │
└────────┬─────────┘        └────────┬──────────┘
         │                           │
         └───────────┬───────────────┘
                     │
                     │ Shared Layers
                     │ - Version Detection
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
- **Standard Mode**: `plugins/plugin_utils/platform/direct_client.py`
  - `DirectHTTPClient` - Direct HTTP requests, new session per task
  - Inherits from `BaseAPIClient`
  - Uses shared layers (version detection, error handling, credentials, CRUD)
  
- **Experimental Mode**: `plugins/plugin_utils/manager/`
  - `PlatformService` - Persistent service with HTTP session reuse
  - `PlatformManager` - Multiprocessing Manager for sharing service
  - `ManagerRPCClient` - Client-side RPC communication
  - Uses shared layers (version detection, error handling, credentials, CRUD)

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

### 2. DirectHTTPClient (Standard Mode)

**Purpose**: Direct HTTP client for standard connection mode.

**Location**: `plugins/plugin_utils/platform/direct_client.py`

**Characteristics**:
- New `requests.Session` per task
- Authenticates on initialization
- Detects API version on initialization
- Uses all shared layers (version detection, error handling, credentials, CRUD)
- Cache persists for task lifetime only

### 3. PlatformService (Experimental Mode)

**Purpose**: Persistent service that handles all API communication and transformations.

**Location**: `plugins/plugin_utils/manager/platform_manager.py`

**Characteristics**:
- Persistent `requests.Session` across tasks
- Detects and caches API version on startup
- Loads version-specific classes via `DynamicClassLoader`
- Performs forward transform (Ansible → API)
- Executes API calls (potentially multiple endpoints)
- Performs reverse transform (API → Ansible)
- Cache persists across tasks

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
- Checks `gateway_config.connection_mode`
- Standard mode → `DirectHTTPClient`
- Experimental mode → `ManagerRPCClient` → `PlatformService`

## Data Flow

### Standard Mode Flow

```
1. Playbook Task
   └─> Action Plugin
       ├─> Validate Input
       ├─> Create AnsibleUser dataclass
       ├─> Get DirectHTTPClient (standard mode)
       │   ├─> Authenticate
       │   ├─> Detect API version
       │   └─> Load version-specific classes
       ├─> Execute operation
       │   ├─> Forward transform (Ansible → API)
       │   ├─> API call
       │   └─> Reverse transform (API → Ansible)
       ├─> Validate Output
       └─> Format Return Dict
```

### Experimental Mode Flow

```
1. Playbook Task
   └─> Action Plugin
       ├─> Validate Input
       ├─> Create AnsibleUser dataclass
       ├─> Get ManagerRPCClient (experimental mode)
       │   └─> Connect to PlatformService (persistent)
       ├─> Execute via RPC
       │   └─> PlatformService
       │       ├─> Load version-specific classes
       │       ├─> Forward transform (Ansible → API)
       │       ├─> API call (reused session)
       │       └─> Reverse transform (API → Ansible)
       ├─> Validate Output
       └─> Format Return Dict
```

## Key Design Decisions

### 1. Dual-Mode Connection Support

**Decision**: Support both standard (direct HTTP) and experimental (persistent manager) modes.

**Rationale**:
- Standard mode provides familiar behavior (like current modules)
- Experimental mode provides performance benefits (session reuse)
- Both modes share the same layers (version detection, error handling, credentials, CRUD)
- Users can opt-in to experimental mode when needed

**Benefits**:
- Backward compatibility with standard mode
- Performance optimization available via experimental mode
- Shared codebase reduces maintenance burden

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
