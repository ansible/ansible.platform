# Standard Connection Mode - Complete Code Flow

This document provides a comprehensive walkthrough of the code flow when using the default connection mode (standard mode) in the `ansible.platform` collection. Standard mode uses direct HTTP requests without a persistent manager process.

## Table of Contents

1. [Overview](#overview)
2. [Flow Diagram](#flow-diagram)
3. [Step-by-Step Code Flow](#step-by-step-code-flow)
4. [Key Components](#key-components)
5. [Data Transformations](#data-transformations)
6. [Connection Lifecycle](#connection-lifecycle)
7. [Comparison with Persistent Mode](#comparison-with-persistent-mode)

---

## Overview

In standard connection mode (the default), each task creates its own HTTP session, authenticates, and makes direct HTTP requests to the Gateway API. There is no persistent process or connection reuse between tasks.

**Key Characteristics:**
- **Direct HTTP:** Each task makes direct HTTP requests
- **No Persistence:** New session per task
- **Simple Architecture:** No manager process or RPC
- **Shared Layers:** Uses same version detection, transforms, and error handling as persistent mode
- **Default Mode:** Used when `platform_connection_mode` is not specified or set to `standard`

**Benefits:**
- **Simplicity:** Straightforward architecture, easy to debug
- **Isolation:** Each task is independent
- **Compatibility:** Works well with Ansible's worker process model
- **No Process Management:** No need to manage persistent processes

**Trade-offs:**
- **No Connection Reuse:** Each task creates new connections
- **No Cross-Task Caching:** API version detection and lookups repeated per task
- **More Authentication Overhead:** Authenticates for each task

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. USER ACTION PLUGIN (user.py)                                       │
│    - Entry point: ActionModule.run()                                    │
│    - Validates input, builds argspec                                   │
│    - Calls _get_or_spawn_manager()                                     │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. BASE ACTION PLUGIN (base_action.py)                                 │
│    - _get_or_spawn_manager() routes based on connection_mode            │
│    - If standard: _get_direct_client()                                 │
│    - Creates DirectHTTPClient instance                                │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. DIRECT HTTP CLIENT (direct_client.py)                               │
│    - DirectHTTPClient.__init__() initializes                           │
│    - Sets up credential management                                     │
│    - Creates new requests.Session (or Ansible Request)                 │
│    - Configures authentication headers                                 │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. BASE API CLIENT (base_client.py)                                   │
│    - BaseAPIClient.__init__() sets up shared layers                   │
│    - Initializes APIVersionRegistry                                    │
│    - Initializes DynamicClassLoader                                    │
│    - Sets up cache                                                      │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. EXECUTE OPERATION (direct_client.py)                               │
│    - DirectHTTPClient.execute() called by action plugin               │
│    - Detects API version (if not already detected)                     │
│    - Loads version-appropriate classes                                 │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 6. API VERSION MANAGEMENT                                              │
│    - APIVersionRegistry discovers available versions                   │
│    - DynamicClassLoader loads classes for detected version             │
│    - Returns (AnsibleClass, APIClass, MixinClass)                      │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 7. TRANSFORM MIXINS (api/v1/user.py)                                   │
│    - UserTransformMixin_v1.to_api() transforms Ansible → API          │
│    - Handles complex mappings (org names → IDs)                        │
│    - Returns APIUser_v1 dataclass                                       │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 8. HTTP REQUEST (direct_client.py)                                     │
│    - _make_request() makes direct HTTP request                         │
│    - Uses session created for this task                                │
│    - Handles authentication, retries, errors                            │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 9. RESPONSE PROCESSING                                                │
│     - Mixin.from_api() transforms API → Ansible                        │
│     - Returns AnsibleUser dataclass                                    │
│     - Converted to dict for Ansible return                             │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 10. RETURN TO ACTION PLUGIN                                           │
│     - Result dict returned directly                                    │
│     - Action plugin validates and formats output                       │
│     - Returns to Ansible                                               │
│     - Session discarded (no persistence)                                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Code Flow

### Step 1: User Action Plugin Entry Point

**File:** `plugins/action/user.py`

```python
class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = 'user'
    
    def run(self, tmp=None, task_vars=None):
        # 1.1: Build argspec from DOCUMENTATION
        argspec = self._build_argspec_from_docs(DOCUMENTATION)
        
        # 1.2: Validate input
        validated_input = self._validate_data(module_args, argspec, 'input')
        
        # 1.3: Get direct HTTP client (routes to base_action.py)
        # Returns: Tuple[DirectHTTPClient, None]
        manager, facts_to_set = self._get_or_spawn_manager(task_vars)
        # In standard mode: manager is DirectHTTPClient, facts_to_set is None
        
        # 1.4: Create AnsibleUser dataclass from validated input
        user = AnsibleUser(**user_data)
        
        # 1.5: Detect operation (create/update/delete)
        operation = self._detect_operation(validated_params)
        
        # 1.6: Execute via direct HTTP client
        manager_result = manager.execute(
            operation=operation,
            module_name=self.MODULE_NAME,
            ansible_data=user.__dict__
        )
        
        # 1.7: Validate and format output
        return result
```

**Key Points:**
- Entry point for user module
- Validates input using argspec
- Creates AnsibleUser dataclass
- Calls `execute()` on DirectHTTPClient (not RPC)
- No facts to set (standard mode doesn't use persistent connections)

---

### Step 2: Base Action Plugin - Manager Selection

**File:** `plugins/action/base_action.py`

```python
def _get_or_spawn_manager(
    self, 
    task_vars: dict
) -> Tuple[Union['DirectHTTPClient', 'ManagerRPCClient'], Optional[Dict[str, Any]]]:
    """
    Get connection client based on connection_mode.
    
    Returns:
        Tuple of (client, facts_dict):
        - client: DirectHTTPClient (standard) or ManagerRPCClient (experimental)
        - facts_dict: Dict with facts to set (only for experimental mode)
          None for standard mode (no facts needed)
    """
    # 2.1: Extract gateway config (includes connection_mode)
    gateway_config = extract_gateway_config(
        task_args=self._task.args,
        host_vars=task_vars,
        required=True
    )
    
    # 2.2: Route based on connection_mode
    if gateway_config.connection_mode == 'experimental':
        # Persistent connection mode
        return self._get_or_spawn_persistent_manager(task_vars, gateway_config)
    else:
        # Standard mode (default): Use direct HTTP client
        return self._get_direct_client(task_vars, gateway_config)
```

**Key Points:**
- Routes to appropriate client based on `connection_mode`
- For standard mode (default), calls `_get_direct_client()`
- Returns typed tuple: `(DirectHTTPClient, None)` for standard mode
- Type hints enable proper IDE navigation and type checking

---

### Step 3: Create Direct HTTP Client

**File:** `plugins/action/base_action.py`

```python
def _get_direct_client(
    self, 
    task_vars: dict, 
    gateway_config: Any
) -> Tuple['DirectHTTPClient', None]:
    """
    Get or create DirectHTTPClient for standard mode.
    
    Returns:
        Tuple of (DirectHTTPClient, None):
        - DirectHTTPClient: Direct HTTP client instance
        - None: No facts to set (standard mode doesn't need facts)
    """
    from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient

    logger.debug("Using standard connection mode (DirectHTTPClient)")

    # Create direct HTTP client (new instance per task)
    client = DirectHTTPClient(gateway_config)

    logger.info(f"DirectHTTPClient created for {gateway_config.base_url}")

    return client, None
```

**Key Points:**
- Creates new `DirectHTTPClient` instance for each task
- No facts to set (standard mode doesn't use persistent connections)
- Returns typed tuple: `(DirectHTTPClient, None)`
- Client is created fresh for each task (no reuse)

---

### Step 4: Direct HTTP Client Initialization

**File:** `plugins/plugin_utils/platform/direct_client.py`

```python
class DirectHTTPClient(BaseAPIClient):
    def __init__(self, config: GatewayConfig):
        # 4.1: Call parent constructor (sets up shared layers)
        super().__init__(config)
        # BaseAPIClient.__init__() initializes:
        # - APIVersionRegistry
        # - DynamicClassLoader
        # - Cache
        
        # 4.2: Initialize credential management
        self.credential_manager = get_credential_manager()
        self.credential_store = self.credential_manager.get_or_create_store(
            gateway_url=self.base_url,
            username=config.username,
            password=config.password,
            oauth_token=config.oauth_token,
            process_id=str(id(self))
        )
        
        # 4.3: Get credentials from store
        self.username, self.password, self.oauth_token = self.credential_store.get_auth_credentials()
        
        # 4.4: Initialize session (new session per task)
        self.session = Request(
            cookies=CookieJar(),
            validate_certs=self.verify_ssl,
            timeout=self.request_timeout
        )
        self.session.headers.update({
            'User-Agent': 'Ansible Platform Collection',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # 4.5: Configure authentication (deferred until first request)
        self.api_version = None  # Will be set on first request
        self._authenticated = False
        
        logger.info("DirectHTTPClient: Initialized (authentication deferred until first request)")
```

**Key Points:**
- Inherits from `BaseAPIClient` (shares all shared layers)
- Creates new session per task (no persistence)
- Uses credential manager for secure credential storage
- Authentication deferred until first request (avoids worker process issues)
- API version detection deferred until first request

---

### Step 5: Base API Client - Shared Layers

**File:** `plugins/plugin_utils/platform/base_client.py`

```python
class BaseAPIClient(ABC):
    def __init__(self, config: GatewayConfig):
        # 5.1: Store configuration
        self.config = config
        self.base_url = config.base_url.rstrip('/')
        self.verify_ssl = config.verify_ssl
        self.request_timeout = config.request_timeout

        # 5.2: Shared: Version detection infrastructure
        self.registry = APIVersionRegistry()
        self.loader = DynamicClassLoader(self.registry)

        # 5.3: Shared: API version (detected during first request)
        self.api_version: Optional[str] = None

        # 5.4: Shared: Cache for lookups (org names ↔ IDs, etc.)
        self.cache: Dict[str, Any] = {}

        logger.info(f"BaseAPIClient initialized: base_url={self.base_url}, mode={config.connection_mode}")
```

**Key Points:**
- Sets up shared infrastructure used by both standard and experimental modes
- Initializes `APIVersionRegistry` for version discovery
- Initializes `DynamicClassLoader` for runtime class loading
- Provides cache for lookups (organization names ↔ IDs, etc.)
- Both connection modes use these same shared layers

---

### Step 6: Execute Operation

**File:** `plugins/plugin_utils/platform/direct_client.py`

```python
def execute(
    self,
    operation: str,
    module_name: str,
    ansible_data_dict: dict
) -> dict:
    """
    Execute a generic operation on any resource.
    
    This is the main entry point called by action plugins.
    """
    # 6.1: Detect API version (if not already detected)
    if self.api_version is None:
        self.api_version = self._detect_api_version()
        logger.info(f"DirectHTTPClient: Detected API version: {self.api_version}")
    
    # 6.2: Authenticate (if not already authenticated)
    if not self._authenticated:
        self._authenticate()
        self._authenticated = True
    
    # 6.3: Load version-appropriate classes
    AnsibleClass, APIClass, MixinClass = self.loader.load_classes_for_module(
        module_name,
        self.api_version
    )
    
    # 6.4: Reconstruct Ansible dataclass
    ansible_instance = AnsibleClass(**ansible_data_dict)
    
    # 6.5: Build transformation context
    context = TransformContext(
        manager=self,
        session=self.session,
        cache=self.cache,
        api_version=self.api_version
    )
    
    # 6.6: Execute operation
    if operation == 'create':
        result = self._create_resource(ansible_instance, MixinClass, context)
    elif operation == 'update':
        result = self._update_resource(ansible_instance, MixinClass, context)
    elif operation == 'delete':
        result = self._delete_resource(ansible_instance, MixinClass, context)
    elif operation == 'find':
        result = self._find_resource(ansible_instance, MixinClass, context)
    
    return result
```

**Key Points:**
- Main entry point for action plugins
- Detects API version on first request
- Authenticates on first request
- Uses shared layers (loader, registry) to get version-appropriate classes
- Routes to appropriate operation method

---

### Step 7: API Version Management

**File:** `plugins/plugin_utils/platform/loader.py`

```python
class DynamicClassLoader:
    def load_classes_for_module(self, module_name, api_version):
        # 7.1: Find best matching version
        best_version = self.registry.find_best_version(api_version, module_name)
        
        # 7.2: Check cache
        cache_key = f"{module_name}_{best_version}"
        if cache_key in self._class_cache:
            return self._class_cache[cache_key]
        
        # 7.3: Load Ansible class (stable, version-independent)
        ansible_class = self._load_ansible_class(module_name)
        # Example: AnsibleUser from ansible_models/user.py
        
        # 7.4: Load API classes (version-specific)
        api_class, mixin_class = self._load_api_classes(module_name, best_version)
        # Example: APIUser_v1, UserTransformMixin_v1 from api/v1/user.py
        
        # 7.5: Cache and return
        result = (ansible_class, api_class, mixin_class)
        self._class_cache[cache_key] = result
        return result
```

**Key Points:**
- Discovers available API versions from filesystem
- Finds best matching version
- Loads Ansible class (stable)
- Loads API class and mixin (version-specific)
- Caches loaded classes (per client instance)

---

### Step 8: Transform Ansible → API

**File:** `plugins/plugin_utils/api/v1/user.py`

```python
class UserTransformMixin_v1(BaseTransformMixin):
    @classmethod
    def to_api(cls, ansible_instance, context):
        # 8.1: Create API dataclass instance
        api_instance = cls.from_ansible_data(ansible_instance, context)
        # Returns APIUser_v1 dataclass
        
        # 8.2: Handle complex transformations
        # Example: organization names → IDs
        if ansible_instance.organizations:
            org_ids = cls._names_to_ids(
                ansible_instance.organizations,
                context
            )
            api_instance.organization_ids = org_ids
        
        return api_instance
```

**File:** `plugins/plugin_utils/platform/direct_client.py`

```python
def _create_resource(self, ansible_data, mixin_class, context):
    # 8.3: FORWARD TRANSFORM: Ansible → API
    api_data = ansible_data.to_api(context)
    # Returns APIUser_v1 dataclass
    
    # 8.4: Get endpoint operations from mixin
    operations = mixin_class.get_endpoint_operations()
    # Returns list of EndpointOperation objects
    
    # 8.5: Execute operations (HTTP request)
    api_result = self._execute_operations(
        operations, api_data, context, required_for='create'
    )
    
    return api_result
```

**Key Points:**
- Transforms AnsibleUser → APIUser_v1
- Handles complex mappings (org names → IDs)
- Uses mixin's `to_api()` method
- Returns API dataclass instance

---

### Step 9: HTTP Request Execution

**File:** `plugins/plugin_utils/platform/direct_client.py`

```python
def _make_request(
    self,
    method: str,
    url: str,
    operation: str = 'http_request',
    resource: str = 'unknown',
    **kwargs
):
    """
    Make HTTP request with retry logic.
    
    Uses Ansible's Request.open() for better worker process compatibility.
    """
    # 9.1: Prepare request data
    data = None
    if 'json' in kwargs:
        data = json.dumps(kwargs.pop('json'))
    
    # 9.2: Make HTTP request using session (new session per task)
    response = self.session.open(
        method.upper(),
        url,
        validate_certs=self.verify_ssl,
        timeout=self.request_timeout,
        follow_redirects=True,
        data=data,
    )
    
    # 9.3: Handle authentication errors
    status = getattr(response, 'status', getattr(response, 'code', 'unknown'))
    if status == 401:
        # Retry with fresh authentication
        self._authenticate()
        response = self.session.open(...)  # Retry
    
    return response
```

**Key Points:**
- Uses Ansible's `Request.open()` for worker process compatibility
- New session per task (no persistence)
- Handles authentication automatically
- Retries on 401 errors
- No connection pooling across tasks

---

### Step 10: Transform API → Ansible

**File:** `plugins/plugin_utils/api/v1/user.py`

```python
class UserTransformMixin_v1(BaseTransformMixin):
    @classmethod
    def from_api(cls, api_data, context):
        # 10.1: Convert API dict to API dataclass
        api_instance = APIUser_v1(**api_data)
        
        # 10.2: Build Ansible data dict
        ansible_data = {}
        
        # 10.3: Simple field mappings
        simple_fields = ['username', 'email', 'first_name', 'last_name', ...]
        for field in simple_fields:
            value = getattr(api_instance, field, None)
            if value is not None:
                ansible_data[field] = value
        
        # 10.4: Complex transformation: organization IDs → names
        if api_instance.organization_ids:
            org_names = cls._ids_to_names(
                api_instance.organization_ids,
                context
            )
            ansible_data['organizations'] = org_names
        
        # 10.5: Return AnsibleUser dataclass
        return AnsibleUser(**ansible_data)
```

**File:** `plugins/plugin_utils/platform/direct_client.py`

```python
def _create_resource(self, ansible_data, mixin_class, context):
    # ... HTTP request executed ...
    
    # 10.6: REVERSE TRANSFORM: API → Ansible
    if api_result:
        ansible_instance = mixin_class.from_api(api_result, context)
        # Returns AnsibleUser dataclass
        
        # 10.7: Convert to dict for Ansible return
        from dataclasses import asdict
        ansible_result = asdict(ansible_instance)
        ansible_result['changed'] = True
        return ansible_result
```

**Key Points:**
- Transforms APIUser_v1 → AnsibleUser
- Handles complex mappings (org IDs → names)
- Uses mixin's `from_api()` method
- Returns AnsibleUser dataclass, then converts to dict

---

### Step 11: Return to Action Plugin

**File:** `plugins/action/user.py`

```python
def run(self, tmp=None, task_vars=None):
    # ... previous steps ...
    
    # 11.1: Execute via direct HTTP client
    manager_result = manager.execute(
        operation=operation,
        module_name=self.MODULE_NAME,
        ansible_data=user.__dict__
    )
    # Returns dict with user data and 'changed' field
    
    # 11.2: Validate output
    validated_output = self._validate_data(
        filtered_result,
        argspec,
        'output'
    )
    
    # 11.3: Format result
    result.update(validated_output.validated_parameters)
    result['changed'] = manager_result.get('changed', False)
    
    # 11.4: Return to Ansible
    # DirectHTTPClient instance is discarded (no persistence)
    return result
```

**Key Points:**
- Receives result dict from direct HTTP call
- Validates output against argspec
- Formats result for Ansible
- Returns to Ansible core
- Client instance is discarded after task completes

---

## Key Components

### 1. Action Plugins
- **Location:** `plugins/action/`
- **Purpose:** Entry point for Ansible modules
- **Key Files:**
  - `user.py`: User-specific action plugin
  - `base_action.py`: Base class with common functionality
- **Type Hints:**
  - Uses `TYPE_CHECKING` imports to avoid circular dependencies
  - Methods include return type annotations for IDE support
  - Example: `_get_direct_client()` returns `Tuple['DirectHTTPClient', None]`

### 2. Direct HTTP Client
- **Location:** `plugins/plugin_utils/platform/direct_client.py`
- **Purpose:** Direct HTTP client for standard mode
- **Key Features:**
  - Inherits from `BaseAPIClient` (shares all shared layers)
  - Creates new session per task
  - Uses Ansible's `Request.open()` for worker process compatibility
  - Deferred authentication and version detection

### 3. Base API Client
- **Location:** `plugins/plugin_utils/platform/base_client.py`
- **Purpose:** Abstract base class for both connection modes
- **Shared Layers:**
  - `APIVersionRegistry`: Version discovery
  - `DynamicClassLoader`: Runtime class loading
  - Cache: Lookup caching
  - Error taxonomy: Standardized error handling

### 4. API Version Management
- **Location:** `plugins/plugin_utils/platform/`
- **Purpose:** Discover and load version-specific classes
- **Key Files:**
  - `registry.py`: API version registry
  - `loader.py`: Dynamic class loader

### 5. Transform Mixins
- **Location:** `plugins/plugin_utils/api/v1/`
- **Purpose:** Transform between Ansible and API formats
- **Key Files:**
  - `user.py`: User transform mixin for API v1

### 6. HTTP Communication
- **Location:** `plugins/plugin_utils/platform/direct_client.py`
- **Purpose:** Make HTTP requests to Gateway API
- **Key Features:**
  - Uses Ansible's `Request.open()` (not `requests` library)
  - New session per task
  - Automatic authentication
  - Retry logic

---

## Data Transformations

### Transformation Flow

```
AnsibleUser (dataclass)
    │
    │ to_api(context)
    ▼
APIUser_v1 (dataclass)
    │
    │ asdict()
    ▼
API Dict (JSON)
    │
    │ HTTP POST
    ▼
Gateway API Response (JSON)
    │
    │ from_api(context)
    ▼
AnsibleUser (dataclass)
    │
    │ asdict()
    ▼
Result Dict (Ansible format)
```

### Complex Transformations

**Organization Names ↔ IDs:**
- **Forward (Ansible → API):** `organizations: ['org1', 'org2']` → `organization_ids: [1, 2]`
- **Reverse (API → Ansible):** `organization_ids: [1, 2]` → `organizations: ['org1', 'org2']`
- **Caching:** Lookup results cached in `context.cache` for performance (per client instance)

---

## Connection Lifecycle

### Per-Task Lifecycle

1. **Task Starts:**
   - Action plugin calls `_get_or_spawn_manager()`
   - `_get_direct_client()` creates new `DirectHTTPClient` instance
   - Client initializes:
     - Sets up credential management
     - Creates new session
     - Configures authentication headers

2. **First Request:**
   - `execute()` method called
   - API version detected (if not already detected)
   - Authentication performed (if not already authenticated)
   - Classes loaded for detected version

3. **Subsequent Requests (same task):**
   - Reuses same client instance
   - Reuses same session
   - Reuses detected API version
   - Reuses loaded classes

4. **Task Completes:**
   - Result returned to Ansible
   - Client instance discarded
   - Session discarded
   - No persistence to next task

### No Cross-Task Reuse

- Each task creates new `DirectHTTPClient` instance
- Each task creates new session
- Each task detects API version independently
- Each task loads classes independently
- No shared state between tasks

---

## Comparison with Persistent Mode

### Standard Mode (Default)

**Architecture:**
- Direct HTTP requests
- New session per task
- No manager process

**Benefits:**
- Simple architecture
- Easy to debug
- No process management
- Works well with Ansible workers

**Trade-offs:**
- No connection reuse
- No cross-task caching
- More authentication overhead

### Experimental Mode (Persistent)

**Architecture:**
- Persistent manager process
- RPC communication
- Shared HTTP session

**Benefits:**
- Connection reuse
- Cross-task caching
- Reduced authentication overhead

**Trade-offs:**
- More complex architecture
- Process management required
- More moving parts

### Shared Layers

Both modes use the same shared layers:
- ✅ **APIVersionRegistry** - Version discovery
- ✅ **DynamicClassLoader** - Runtime class loading
- ✅ **Transform Mixins** - Data transformation
- ✅ **Error Taxonomy** - Standardized error handling
- ✅ **Credential Management** - Secure credential storage
- ✅ **Cache** - Lookup caching (per client instance in standard mode)

---

## Summary

Standard connection mode provides a straightforward architecture for API communication:

1. **Simplicity:** Direct HTTP requests, no persistent processes
2. **Isolation:** Each task is independent
3. **Compatibility:** Works well with Ansible's worker process model
4. **Shared Layers:** Uses same version detection, transforms, and error handling as persistent mode
5. **Type Safety:** Dataclass-first approach throughout
6. **IDE Support:** Type hints enable proper navigation and autocomplete

### Type Hints and IDE Navigation

The codebase includes comprehensive type hints to improve developer experience:

- **Method Signatures:** All client-related methods include return type annotations
- **Type Imports:** Uses `TYPE_CHECKING` to avoid circular dependencies while providing type information
- **Return Types:** Methods return typed tuples, enabling IDE "Go to Definition" functionality
- **Type Safety:** Type hints help catch errors at development time

**Example:**
```python
def _get_direct_client(
    self, 
    task_vars: dict, 
    gateway_config: Any
) -> Tuple['DirectHTTPClient', None]:
    # Method implementation
```

This enables IDEs to:
- Navigate to method definitions via "Go to Definition"
- Provide autocomplete suggestions
- Show type information on hover
- Catch type mismatches during development

This architecture provides a simple, reliable way to interact with the Gateway API while maintaining clean separation of concerns, type safety, and excellent IDE support.
