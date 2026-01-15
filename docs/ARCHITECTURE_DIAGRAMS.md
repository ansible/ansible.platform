# Architecture and Sequence Diagrams - Ansible Platform Collection

This document contains comprehensive architecture and sequence diagrams for the Ansible Platform Collection.

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Component Architecture](#component-architecture)
3. [Data Flow Architecture](#data-flow-architecture)
4. [Manager Lifecycle](#manager-lifecycle)
5. [Sequence Diagrams](#sequence-diagrams)
   - [First Task: Spawning Manager](#first-task-spawning-manager)
   - [Subsequent Task: Reusing Manager](#subsequent-task-reusing-manager)
   - [Complete Create Operation](#complete-create-operation)
   - [Data Transformation Flow](#data-transformation-flow)
   - [Version Discovery and Class Loading](#version-discovery-and-class-loading)
   - [Multi-Endpoint Operation](#multi-endpoint-operation)

---

## High-Level Architecture

```mermaid
graph TB
    subgraph "Layer 1: Ansible Playbook"
        PB[Playbook YAML<br/>Stable Interface]
    end
    
    subgraph "Layer 2: Action Plugins (Client)"
        AP[Action Plugin<br/>BaseResourceActionPlugin]
        AP --> |Validates| IV[Input Validation]
        AP --> |Creates| DC[Ansible Dataclass]
        AP --> |Connects| MC[ManagerRPCClient]
        AP --> |Validates| OV[Output Validation]
    end
    
    subgraph "Layer 3: Platform Manager (Service)"
        PM[PlatformManager<br/>Unix Socket Server]
        PS[PlatformService<br/>Persistent HTTP Session]
        PS --> |Detects| AV[API Version]
        PS --> |Loads| CL[DynamicClassLoader]
        PS --> |Transforms| FT[Forward Transform<br/>Ansible → API]
        PS --> |Executes| AC[API Calls]
        PS --> |Transforms| RT[Reverse Transform<br/>API → Ansible]
        PM --> |Manages| PS
    end
    
    subgraph "Layer 4: Platform Framework (Platform SDK)"
        BT[BaseTransformMixin<br/>Universal Transform Logic]
        VR[APIVersionRegistry<br/>Version Discovery]
        DL[DynamicClassLoader<br/>Runtime Class Loading]
        GC[GatewayConfig<br/>Config Extraction]
        PM[ProcessManager<br/>Process Management]
        TC[TransformContext<br/>Type-Safe Context]
        FT --> BT
        RT --> BT
        CL --> VR
        CL --> DL
        AP --> |Uses| GC
        AP --> |Uses| PM
        BT --> |Uses| TC
    end
    
    subgraph "Layer 5: AAP Gateway API"
        API[REST API<br/>Versioned Endpoints]
    end
    
    PB --> |Task Execution| AP
    AP --> |RPC via Unix Socket| PM
    PM --> |HTTP/HTTPS| API
    
    style PB fill:#e1f5ff
    style AP fill:#fff4e1
    style PM fill:#ffe1f5
    style PS fill:#ffe1f5
    style BT fill:#e1ffe1
    style VR fill:#e1ffe1
    style DL fill:#e1ffe1
    style API fill:#ffe1e1
```

---

## Component Architecture

```mermaid
graph LR
    subgraph "Action Plugin Layer"
        BA[BaseResourceActionPlugin]
        BA --> |Inherits| AB[ActionBase]
        BA --> |Uses| MRC[ManagerRPCClient]
        BA --> |Validates| ASV[ArgumentSpecValidator]
        BA --> |Parses| DOC[DOCUMENTATION]
    end
    
    subgraph "Manager Layer"
        MRC --> |Connects via| US[Unix Socket]
        US --> |RPC| PM[PlatformManager]
        PM --> |Manages| PS[PlatformService]
        PS --> |Uses| RS[requests.Session]
        PS --> |Caches| VC[Version Cache]
        PS --> |Caches| LC[Lookup Cache]
    end
    
    subgraph "Platform Framework"
        PS --> |Uses| DL[DynamicClassLoader]
        DL --> |Uses| VR[APIVersionRegistry]
        VR --> |Scans| FS[FileSystem<br/>api/v1/, api/v2/]
        PS --> |Uses| BT[BaseTransformMixin]
        BT --> |Applied by| TM[Transform Mixins<br/>UserTransformMixin_v1]
    end
    
    subgraph "Data Models"
        AD[Ansible Dataclasses<br/>ansible_models/]
        APD[API Dataclasses<br/>api/v1/generated/]
        TM --> |Transforms| AD
        TM --> |Transforms| APD
    end
    
    style BA fill:#fff4e1
    style PS fill:#ffe1f5
    style BT fill:#e1ffe1
    style AD fill:#e1f5ff
    style APD fill:#ffe1e1
```

---

## Data Flow Architecture

```mermaid
flowchart TD
    Start[Playbook Task] --> Input[User Input<br/>organizations: ['Engineering']]
    
    Input --> Validate1[Action Plugin:<br/>Validate Input]
    Validate1 --> CreateDC[Create AnsibleUser<br/>organizations: ['Engineering']]
    
    CreateDC --> RPC[RPC Call via Unix Socket]
    RPC --> Manager[PlatformService]
    
    Manager --> LoadClasses[Load Version Classes<br/>AnsibleUser, APIUser_v1, UserTransformMixin_v1]
    
    LoadClasses --> Forward[Forward Transform<br/>to_api(context)]
    
    Forward --> Lookup[Lookup Org IDs<br/>lookup_org_ids(['Engineering'])]
    Lookup --> API1[API Call:<br/>GET /organizations/?name=Engineering]
    API1 --> OrgID[Returns: org_id=1]
    
    OrgID --> Transform1[Transform:<br/>organizations → organization_ids<br/>['Engineering'] → [1]]
    
    Transform1 --> APICall[API Call:<br/>POST /users/<br/>organization_ids: [1]]
    APICall --> APIResp[API Response:<br/>id: 123, organization_ids: [1]]
    
    APIResp --> Reverse[Reverse Transform<br/>to_ansible(context)]
    
    Reverse --> Lookup2[Lookup Org Names<br/>lookup_org_names([1])]
    Lookup2 --> API2[API Call:<br/>GET /organizations/1/]
    API2 --> OrgName[Returns: name='Engineering']
    
    OrgName --> Transform2[Transform:<br/>organization_ids → organizations<br/>[1] → ['Engineering']]
    
    Transform2 --> CreateResult[Create AnsibleUser Result<br/>organizations: ['Engineering']]
    
    CreateResult --> RPC2[RPC Return via Unix Socket]
    RPC2 --> Validate2[Action Plugin:<br/>Validate Output]
    Validate2 --> Output[Return to Playbook<br/>organizations: ['Engineering']]
    
    style Input fill:#e1f5ff
    style CreateDC fill:#e1f5ff
    style Transform1 fill:#fff4e1
    style APICall fill:#ffe1e1
    style Transform2 fill:#fff4e1
    style CreateResult fill:#e1f5ff
    style Output fill:#e1f5ff
```

---

## Manager Lifecycle

```mermaid
stateDiagram-v2
    [*] --> CheckManager: First Task
    
    CheckManager --> SpawnManager: Manager Not Found
    CheckManager --> ConnectManager: Manager Found
    
    SpawnManager --> ExtractConfig: Extract Gateway Config<br/>(Platform SDK)
    ExtractConfig --> GenerateConnInfo: Generate Connection Info<br/>(Platform SDK ProcessManager)
    GenerateConnInfo --> StartProcess: Spawn Manager Process<br/>(Platform SDK)
    StartProcess --> InitService: Initialize PlatformService
    InitService --> CreateSession: Create HTTP Session
    CreateSession --> Authenticate: Authenticate with AAP
    Authenticate --> DetectVersion: Detect API Version
    DetectVersion --> InitRegistry: Initialize Registry
    InitRegistry --> StartServer: Start Manager Server
    StartServer --> WaitSocket: Wait for Socket<br/>(Platform SDK)
    WaitSocket --> SetFactsInResult: Set Facts in Result Dict<br/>(ansible_facts, _ansible_facts_cacheable)
    SetFactsInResult --> ConnectManager: Connect to Manager
    
    ConnectManager --> Ready: Manager Ready
    
    Ready --> ExecuteTask: Execute Task
    ExecuteTask --> Ready: Task Complete
    
    Ready --> [*]: Playbook Complete
    
    note right of Ready
        Manager persists for
        entire playbook duration
        Reused by all tasks
    end note
```

---

## Sequence Diagrams

### First Task: Spawning Manager

```mermaid
sequenceDiagram
    participant PB as Playbook
    participant AP as Action Plugin
    participant HV as HostVars
    participant PM as Manager Process
    participant PS as PlatformService
    participant API as AAP Gateway

    PB->>AP: Execute Task
    AP->>AP: Extract gateway config (Platform SDK)
    AP->>HV: Check for existing manager
    HV-->>AP: No manager found
    
    AP->>AP: Generate connection info (Platform SDK ProcessManager)
    AP->>PM: Spawn manager process (Platform SDK)
    
    PM->>PS: Create PlatformService
    PS->>PS: Create requests.Session
    PS->>API: Authenticate (Basic/OAuth)
    API-->>PS: Authentication success
    PS->>API: Detect API version (/ping)
    API-->>PS: Version: v1
    PS->>PS: Initialize APIVersionRegistry
    PS->>PS: Initialize DynamicClassLoader
    PM->>PM: Start Unix socket server
    
    PM-->>AP: Socket ready
    AP->>AP: Set facts in result dict<br/>(ansible_facts, _ansible_facts_cacheable)
    AP->>AP: Connect via ManagerRPCClient
    AP-->>PB: Manager ready (result includes facts)
```

### Subsequent Task: Reusing Manager

```mermaid
sequenceDiagram
    participant PB as Playbook
    participant AP as Action Plugin
    participant HV as HostVars
    participant MRC as ManagerRPCClient
    participant PM as PlatformManager
    participant PS as PlatformService

    PB->>AP: Execute Task
    AP->>HV: Check for existing manager
    HV-->>AP: Manager found (socket_path, authkey)
    
    AP->>AP: Verify socket exists
    AP->>MRC: Create ManagerRPCClient
    MRC->>PM: Connect via Unix socket
    PM-->>MRC: Connection established
    MRC->>PM: get_platform_service()
    PM-->>MRC: Service proxy
    MRC-->>AP: Client ready
    
    Note over PS: Persistent session reused<br/>No re-authentication needed
    
    AP-->>PB: Manager ready (reused)
```

### Complete Create Operation

```mermaid
sequenceDiagram
    participant PB as Playbook
    participant AP as Action Plugin
    participant MRC as ManagerRPCClient
    participant PS as PlatformService
    participant DL as DynamicClassLoader
    participant BT as BaseTransformMixin
    participant API as AAP Gateway

    PB->>AP: Create user task
    AP->>AP: Validate input (ArgumentSpec)
    AP->>AP: Create AnsibleUser dataclass
    Note over AP: organizations: ['Engineering', 'DevOps']
    
    AP->>MRC: execute('create', 'user', ansible_user_dict)
    MRC->>PS: execute(operation, module_name, data_dict)
    
    PS->>DL: load_classes_for_module('user', '1')
    DL->>DL: Find best version match
    DL->>DL: Import AnsibleUser
    DL->>DL: Import APIUser_v1
    DL->>DL: Import UserTransformMixin_v1
    DL-->>PS: (AnsibleUser, APIUser_v1, UserTransformMixin_v1)
    
    PS->>PS: Reconstruct AnsibleUser from dict
    
    PS->>PS: Create TransformContext dataclass<br/>(manager, session, cache, api_version)
    PS->>BT: Forward Transform: to_api(context)
    Note over BT: context is TransformContext<br/>(type-safe, not dict)
    BT->>PS: lookup_org_ids(['Engineering', 'DevOps'])
    PS->>API: GET /organizations/?name=Engineering
    API-->>PS: {id: 1, name: 'Engineering'}
    PS->>API: GET /organizations/?name=DevOps
    API-->>PS: {id: 2, name: 'DevOps'}
    PS-->>BT: [1, 2]
    BT->>BT: Apply field mapping
    Note over BT: organizations → organization_ids<br/>['Engineering', 'DevOps'] → [1, 2]
    BT-->>PS: APIUser_v1 instance
    
    PS->>PS: Get endpoint operations
    PS->>API: POST /api/gateway/v1/users/
    Note over API: {username: 'jdoe', email: 'jdoe@example.com'}
    API-->>PS: {id: 123, username: 'jdoe', ...}
    
    PS->>API: POST /api/gateway/v1/users/123/organizations/
    Note over API: {organization_ids: [1, 2]}
    API-->>PS: {success: true}
    
    PS->>BT: Reverse Transform: to_ansible(context)
    Note over BT: context is TransformContext<br/>(type-safe, not dict)
    BT->>PS: lookup_org_names([1, 2])
    PS->>API: GET /organizations/1/
    API-->>PS: {id: 1, name: 'Engineering'}
    PS->>API: GET /organizations/2/
    API-->>PS: {id: 2, name: 'DevOps'}
    PS-->>BT: ['Engineering', 'DevOps']
    BT->>BT: Apply reverse mapping
    Note over BT: organization_ids → organizations<br/>[1, 2] → ['Engineering', 'DevOps']
    BT-->>PS: AnsibleUser instance
    
    PS-->>MRC: AnsibleUser dict
    MRC-->>AP: Result dict
    AP->>AP: Validate output (ArgumentSpec)
    AP-->>PB: {changed: True, user: {...}}
    Note over PB: organizations: ['Engineering', 'DevOps']
```

### Data Transformation Flow

```mermaid
sequenceDiagram
    participant AD as AnsibleUser<br/>(Input)
    participant BT as BaseTransformMixin
    participant TM as UserTransformMixin_v1
    participant PS as PlatformService
    participant API as AAP Gateway
    participant APD as APIUser_v1<br/>(API Format)
    participant AD2 as AnsibleUser<br/>(Output)

    Note over AD: User Input<br/>organizations: ['Engineering']
    
    AD->>BT: to_api(context)
    Note over BT: context is TransformContext<br/>(type-safe dataclass, not dict)
    BT->>TM: _apply_forward_mapping()
    TM->>TM: Check _field_mapping
    Note over TM: organizations → organization_ids<br/>forward_transform: names_to_ids
    
    TM->>PS: lookup_org_ids(['Engineering'])
    PS->>API: GET /organizations/?name=Engineering
    API-->>PS: {id: 1, name: 'Engineering'}
    PS-->>TM: [1]
    
    TM->>TM: Apply transform
    Note over TM: ['Engineering'] → [1]
    TM->>APD: Create APIUser_v1
    Note over APD: organization_ids: [1]
    
    APD->>API: POST /users/ (with organization_ids: [1])
    API-->>APD: Response: {id: 123, organization_ids: [1]}
    
    APD->>BT: to_ansible(context)
    Note over BT: context is TransformContext<br/>(type-safe dataclass, not dict)
    BT->>TM: _apply_reverse_mapping()
    TM->>TM: Check _field_mapping
    Note over TM: organization_ids → organizations<br/>reverse_transform: ids_to_names
    
    TM->>PS: lookup_org_names([1])
    PS->>API: GET /organizations/1/
    API-->>PS: {id: 1, name: 'Engineering'}
    PS-->>TM: ['Engineering']
    
    TM->>TM: Apply reverse transform
    Note over TM: [1] → ['Engineering']
    TM->>AD2: Create AnsibleUser
    Note over AD2: organizations: ['Engineering']
    
    Note over AD,AD2: Round-Trip Contract:<br/>Output matches Input
```

### Version Discovery and Class Loading

```mermaid
sequenceDiagram
    participant PS as PlatformService
    participant VR as APIVersionRegistry
    participant FS as FileSystem
    participant DL as DynamicClassLoader
    participant IM as Import Module
    participant CC as Class Cache

    PS->>VR: Initialize APIVersionRegistry()
    VR->>FS: Scan api/ directory
    FS-->>VR: Found: v1/, v2/
    
    VR->>FS: Scan v1/ directory
    FS-->>VR: Found: user.py, organization.py
    
    VR->>FS: Scan v2/ directory
    FS-->>VR: Found: user.py, team.py
    
    VR->>VR: Build version matrix
    Note over VR: Versions: ['1', '2']<br/>user: ['1', '2']<br/>organization: ['1']<br/>team: ['2']
    
    PS->>PS: Detect API version from API
    PS-->>PS: api_version = '1'
    
    PS->>DL: load_classes_for_module('user', '1')
    DL->>VR: find_best_version('1', 'user')
    VR-->>DL: '1' (exact match)
    
    DL->>CC: Check cache
    CC-->>DL: Not cached
    
    DL->>IM: Import ansible_models.user
    IM-->>DL: AnsibleUser class
    
    DL->>IM: Import api.v1.user
    IM-->>DL: APIUser_v1, UserTransformMixin_v1
    
    DL->>CC: Cache classes
    DL-->>PS: (AnsibleUser, APIUser_v1, UserTransformMixin_v1)
    
    Note over PS: Classes loaded and cached<br/>Ready for transformation
```

### Multi-Endpoint Operation

```mermaid
sequenceDiagram
    participant PS as PlatformService
    participant TM as UserTransformMixin_v1
    participant EO as EndpointOperations
    participant API as AAP Gateway

    PS->>TM: get_endpoint_operations()
    TM-->>PS: Operations dict
    
    Note over EO: Operation 1: create<br/>path: /users/<br/>order: 1<br/>fields: ['username', 'email']
    
    Note over EO: Operation 2: assign_orgs<br/>path: /users/{id}/organizations/<br/>order: 2<br/>depends_on: 'create'<br/>fields: ['organization_ids']
    
    PS->>PS: Sort operations by dependencies & order
    Note over PS: Execution order:<br/>1. create (order=1)<br/>2. assign_orgs (order=2, depends_on='create')
    
    PS->>API: POST /api/gateway/v1/users/
    Note over API: {username: 'jdoe', email: 'jdoe@example.com'}
    API-->>PS: {id: 123, username: 'jdoe', ...}
    PS->>PS: Store id=123 for next operation
    
    PS->>PS: Build path with {id} parameter
    Note over PS: /users/{id}/organizations/<br/>→ /users/123/organizations/
    
    PS->>API: POST /api/gateway/v1/users/123/organizations/
    Note over API: {organization_ids: [1, 2]}
    API-->>PS: {success: true}
    
    PS->>PS: Combine results
    PS-->>PS: Return main result
```

---

## Component Interaction Matrix

```mermaid
graph TB
    subgraph "Action Plugin Components"
        BA[BaseResourceActionPlugin]
        MRC[ManagerRPCClient]
    end
    
    subgraph "Manager Components"
        PM[PlatformManager]
        PS[PlatformService]
    end
    
    subgraph "Platform Framework"
        BT[BaseTransformMixin]
        VR[APIVersionRegistry]
        DL[DynamicClassLoader]
        EO[EndpointOperation]
    end
    
    subgraph "Data Models"
        AD[Ansible Dataclasses]
        APD[API Dataclasses]
        TM[Transform Mixins]
    end
    
    BA -->|uses| MRC
    MRC -->|RPC via| PM
    PM -->|manages| PS
    PS -->|uses| DL
    PS -->|uses| BT
    DL -->|uses| VR
    AD -->|transforms via| BT
    APD -->|transforms via| BT
    TM -->|inherits| BT
    TM -->|defines| EO
    
    style BA fill:#fff4e1
    style PS fill:#ffe1f5
    style BT fill:#e1ffe1
    style AD fill:#e1f5ff
    style APD fill:#ffe1e1
```

---

## File Structure and Dependencies

```mermaid
graph TD
    ROOT[ansible.platform/]
    
    ROOT --> PLUGINS[plugins/]
    PLUGINS --> ACTION[action/]
    PLUGINS --> MODULES[modules/]
    PLUGINS --> PLUGIN_UTILS[plugin_utils/]
    
    ACTION --> BA[base_action.py<br/>BaseResourceActionPlugin]
    ACTION --> USER_ACT[user.py<br/>ActionModule]
    
    PLUGIN_UTILS --> MANAGER[manager/]
    PLUGIN_UTILS --> PLATFORM[platform/]
    PLUGIN_UTILS --> ANSIBLE_MODELS[ansible_models/]
    PLUGIN_UTILS --> API[api/]
    PLUGIN_UTILS --> DOCS[docs/]
    
    MANAGER --> PM[platform_manager.py<br/>PlatformService, PlatformManager]
    MANAGER --> RPC[rpc_client.py<br/>ManagerRPCClient]
    
    PLATFORM --> BT[base_transform.py<br/>BaseTransformMixin]
    PLATFORM --> REG[registry.py<br/>APIVersionRegistry]
    PLATFORM --> LOAD[loader.py<br/>DynamicClassLoader]
    PLATFORM --> TYPES[types.py<br/>EndpointOperation]
    
    ANSIBLE_MODELS --> USER_AM[user.py<br/>AnsibleUser]
    
    API --> V1[v1/]
    V1 --> USER_API[user.py<br/>APIUser_v1, UserTransformMixin_v1]
    V1 --> GEN[generated/<br/>models.py]
    
    DOCS --> USER_DOC[user.py<br/>DOCUMENTATION]
    
    BA -->|inherits| ACTION_BASE[ActionBase]
    USER_ACT -->|inherits| BA
    USER_ACT -->|uses| USER_DOC
    USER_ACT -->|uses| USER_AM
    
    BA -->|uses| RPC
    RPC -->|connects to| PM
    PM -->|uses| BT
    PM -->|uses| LOAD
    LOAD -->|uses| REG
    USER_API -->|inherits| BT
    USER_API -->|inherits| GEN
    
    style BA fill:#fff4e1
    style PM fill:#ffe1f5
    style BT fill:#e1ffe1
    style USER_AM fill:#e1f5ff
    style USER_API fill:#ffe1e1
```

---

## Legend

### Color Coding

- **Blue** (`#e1f5ff`): User-facing components (Playbook, Ansible dataclasses)
- **Orange** (`#fff4e1`): Client layer (Action plugins)
- **Pink** (`#ffe1f5`): Service layer (Manager, PlatformService)
- **Green** (`#e1ffe1`): Framework layer (Transform, Registry, Loader)
- **Red** (`#ffe1e1`): API layer (API dataclasses, Gateway API)

### Diagram Types

1. **Graph Diagrams**: Show component relationships and architecture
2. **Flowchart Diagrams**: Show data flow and transformations
3. **State Diagrams**: Show state transitions and lifecycle
4. **Sequence Diagrams**: Show temporal interactions between components

---

## Notes

- All diagrams use **Mermaid syntax** and can be rendered in:
  - GitHub/GitLab markdown viewers
  - VS Code with Mermaid extension
  - Online Mermaid editors (mermaid.live)
  - Documentation tools (MkDocs, Docusaurus, etc.)

- **Sequence diagrams** show the temporal flow of operations
- **Architecture diagrams** show component relationships
- **Flow diagrams** show data transformation paths
- **State diagrams** show lifecycle and state transitions

---

## Related Documentation

- `ARCHITECTURE.md` - Detailed architecture documentation
- `FLOW_EXPLANATION.md` - Complete flow explanation
- `API_REFERENCE.md` - Component API reference
- `IMPLEMENTATION_GUIDE.md` - Implementation details

