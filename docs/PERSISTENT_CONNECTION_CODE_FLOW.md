# Persistent Connection Mode - Complete Code Flow

This document provides a comprehensive walkthrough of the code flow when using `platform_connection_mode: experimental` (persistent connection mode) in the `ansible.platform` collection.

## Table of Contents

1. [Overview](#overview)
2. [Flow Diagram](#flow-diagram)
3. [Step-by-Step Code Flow](#step-by-step-code-flow)
4. [Key Components](#key-components)
5. [Data Transformations](#data-transformations)
6. [Connection Reuse](#connection-reuse)

---

## Overview

In persistent connection mode, a separate long-lived process (`PlatformService`) maintains an HTTP session and handles all API communication. Action plugins communicate with this process via RPC (Remote Procedure Call) over Unix sockets.

**Key Benefits:**
- **Connection Reuse**: Multiple tasks share the same HTTP session
- **Performance**: Reduced authentication overhead, connection pooling
- **Caching**: API version detection, organization lookups cached across tasks
- **Isolation**: Manager process isolated from Ansible worker processes

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
│    - If experimental: _get_or_spawn_persistent_manager()               │
│    - Checks facts for existing manager                                 │
│    - Spawns new manager if needed                                      │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. PROCESS SPAWNING (process_manager.py)                               │
│    - Generates socket path and authkey                                  │
│    - Spawns manager_process.py as separate process                     │
│    - Returns socket path and authkey                                    │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. MANAGER PROCESS (manager_process.py)                                │
│    - Standalone script that runs PlatformService                        │
│    - Registers with multiprocessing BaseManager                          │
│    - Listens on Unix socket for RPC calls                               │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. RPC CLIENT (rpc_client.py)                                          │
│    - ManagerRPCClient connects to manager via socket                  │
│    - Provides execute() method for action plugins                      │
│    - Handles serialization/deserialization                              │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 6. PLATFORM SERVICE (platform_manager.py)                               │
│    - PlatformService.execute() receives RPC call                       │
│    - Loads version-appropriate classes                                  │
│    - Executes operation (create/update/delete/find)                    │
│    - Returns result dict                                                │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 7. API VERSION MANAGEMENT                                              │
│    - APIVersionRegistry discovers available versions                   │
│    - DynamicClassLoader loads classes for detected version             │
│    - Returns (AnsibleClass, APIClass, MixinClass)                      │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 8. TRANSFORM MIXINS (api/v1/user.py)                                   │
│    - UserTransformMixin_v1.to_api() transforms Ansible → API          │
│    - Handles complex mappings (org names → IDs)                        │
│    - Returns APIUser_v1 dataclass                                       │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 9. HTTP REQUEST (platform_manager.py)                                  │
│    - _execute_operations() makes HTTP request                          │
│    - Uses persistent requests.Session                                  │
│    - Handles authentication, retries, errors                            │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 10. RESPONSE PROCESSING                                                │
│     - Mixin.from_api() transforms API → Ansible                        │
│     - Returns AnsibleUser dataclass                                    │
│     - Converted to dict for Ansible return                             │
└────────────────────┬──────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 11. RETURN TO ACTION PLUGIN                                           │
│     - Result dict returned via RPC                                     │
│     - Action plugin validates and formats output                       │
│     - Returns to Ansible                                                │
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
        
        # 1.3: Get or spawn manager (routes to base_action.py)
        # Returns: Tuple[Union[DirectHTTPClient, ManagerRPCClient], Optional[Dict[str, Any]]]
        manager, facts_to_set = self._get_or_spawn_manager(task_vars)
        
        # 1.4: Set facts if a new manager was spawned
        if facts_to_set:
            result['ansible_facts'] = facts_to_set
            result['_ansible_facts_cacheable'] = True
        
        # 1.5: Create AnsibleUser dataclass from validated input
        user = AnsibleUser(**user_data)
        
        # 1.6: Detect operation (create/update/delete)
        operation = self._detect_operation(validated_params)
        
        # 1.7: Execute via manager (RPC call for experimental mode, direct HTTP for standard)
        manager_result = manager.execute(
            operation=operation,
            module_name=self.MODULE_NAME,
            ansible_data=user.__dict__
        )
        
        # 1.8: Validate and format output
        return result
```

**Key Points:**
- Entry point for user module
- Validates input using argspec
- Creates AnsibleUser dataclass
- Delegates execution to manager (RPC for experimental mode, direct HTTP for standard)
- Type hints on `_get_or_spawn_manager()` enable IDE navigation to method definition

---

### Step 2: Base Action Plugin - Manager Selection

**File:** `plugins/action/base_action.py`

```python
def _get_or_spawn_manager(
    self, 
    task_vars: dict
) -> Tuple[Union['DirectHTTPClient', 'ManagerRPCClient'], Optional[Dict[str, Any]]]:
    """
    Get connection client based on connection mode.
    
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
        # Standard mode (direct HTTP)
        return self._get_direct_client(task_vars, gateway_config)
```

**Key Points:**
- Routes to appropriate client based on `connection_mode`
- For experimental mode, calls `_get_or_spawn_persistent_manager()`
- For standard mode, calls `_get_direct_client()`
- Returns typed tuple: `(client, facts_dict)` where client is either `DirectHTTPClient` or `ManagerRPCClient`
- Type hints enable proper IDE navigation and type checking

**Type Information:**
- Method signature includes return type annotation for better IDE support
- Uses `TYPE_CHECKING` imports to avoid circular dependencies
- Return type: `Tuple[Union['DirectHTTPClient', 'ManagerRPCClient'], Optional[Dict[str, Any]]]`

---

### Step 2a: Standard Mode - Direct HTTP Client

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
- Used when `connection_mode != 'experimental'`
- Creates new `DirectHTTPClient` instance per task
- Returns typed tuple: `(DirectHTTPClient, None)`
- No facts to set (standard mode doesn't use persistent connections)

---

### Step 3: Spawn or Reuse Persistent Manager

**File:** `plugins/action/base_action.py`

```python
def _get_or_spawn_persistent_manager(
    self, 
    task_vars: dict, 
    gateway_config: Any
) -> Tuple['ManagerRPCClient', Optional[Dict[str, Any]]]:
    """
    Get existing persistent manager or spawn new one (experimental mode).
    
    Returns:
        Tuple of (ManagerRPCClient, facts_dict):
        - ManagerRPCClient: The manager client instance
        - facts_dict: Dict with facts to set (socket, authkey, gateway_url)
          if new manager was spawned, or None if reusing existing manager.
    """
    # 3.1: Check facts for existing manager
    socket_path = host_vars.get('platform_manager_socket')
    authkey_b64 = host_vars.get('platform_manager_authkey')
    
    # 3.2: Generate expected socket path based on credentials
    expected_conn_info = ProcessManager.generate_connection_info(
        identifier=inventory_hostname,
        socket_dir=socket_dir,
        gateway_config=gateway_config
    )
    expected_socket_path = expected_conn_info.socket_path
    
    # 3.3: Check if manager exists with matching credentials
    if socket_path == expected_socket_path and Path(socket_path).exists():
        # REUSE EXISTING MANAGER
        logger.info("🔄 REUSING EXISTING PERSISTENT MANAGER")
        client = ManagerRPCClient(gateway_config.base_url, socket_path, authkey)
        return client, None  # No facts to set (already set)
    
    # 3.4: Spawn new manager
    logger.info("🆕 SPAWNING NEW PERSISTENT MANAGER")
    conn_info = ProcessManager.generate_connection_info(...)
    process = ProcessManager.spawn_manager_process(...)
    
    # 3.5: Connect to new manager
    client = ManagerRPCClient(gateway_config.base_url, socket_path, authkey)
    
    # 3.6: Return client and facts to set
    return client, {
        'platform_manager_socket': socket_path,
        'platform_manager_authkey': authkey_b64
    }
```

**Key Points:**
- Checks facts for existing manager
- Validates socket path matches expected (same credentials)
- Spawns new manager if needed
- Returns typed tuple: `(ManagerRPCClient, Optional[Dict[str, Any]])`
- Type hints enable proper IDE navigation and type checking

**Type Information:**
- Method signature includes return type annotation for better IDE support
- Return type: `Tuple['ManagerRPCClient', Optional[Dict[str, Any]]]`
- Facts dict contains: `platform_manager_socket`, `platform_manager_authkey`, `gateway_url`

---

### Step 4: Process Spawning

**File:** `plugins/plugin_utils/manager/process_manager.py`

```python
class ProcessManager:
    @staticmethod
    def generate_connection_info(identifier, socket_dir, gateway_config):
        # 4.1: Generate unique socket path based on credentials
        # Format: manager_{uid}_{hostname}_{hash}.sock
        socket_path = socket_dir / f"manager_{uid}_{identifier}_{hash}.sock"
        
        # 4.2: Generate authkey for secure RPC
        authkey = os.urandom(32)
        authkey_b64 = base64.b64encode(authkey).decode('utf-8')
        
        return ConnectionInfo(socket_path, authkey, authkey_b64)
    
    @staticmethod
    def spawn_manager_process(script_path, socket_path, gateway_config, ...):
        # 4.3: Prepare command-line arguments
        cmd = [
            sys.executable,
            str(script_path),
            '--socket-path', str(socket_path),
            '--base-url', gateway_config.base_url,
            # ... other args
        ]
        
        # 4.4: Spawn process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 4.5: Wait for socket file to be created
        wait_for_socket(socket_path, timeout=10)
        
        return process
```

**Key Points:**
- Generates unique socket path based on credentials
- Creates secure authkey for RPC
- Spawns manager_process.py as separate process
- Waits for socket to be ready

---

### Step 5: Manager Process Initialization

**File:** `plugins/plugin_utils/manager/manager_process.py`

```python
def main():
    # 5.1: Parse command-line arguments
    args = parse_args()
    
    # 5.2: Create GatewayConfig
    gateway_config = GatewayConfig(
        base_url=args.base_url,
        verify_ssl=args.verify_ssl,
        timeout=args.timeout
    )
    
    # 5.3: Create PlatformService
    service = PlatformService(gateway_config)
    
    # 5.4: Register with BaseManager
    PlatformManager.register('get_platform_service', callable=lambda: service)
    
    # 5.5: Create and start manager
    manager = PlatformManager(
        address=args.socket_path,
        authkey=args.authkey
    )
    manager.start()
    
    # 5.6: Register shutdown handler
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    # 5.7: Keep process alive (listening for RPC calls)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()
```

**Key Points:**
- Standalone script that runs PlatformService
- Registers with multiprocessing BaseManager
- Listens on Unix socket for RPC calls
- Handles graceful shutdown

---

### Step 6: RPC Client Connection

**File:** `plugins/plugin_utils/manager/rpc_client.py`

```python
class ManagerRPCClient:
    def __init__(self, base_url, socket_path, authkey):
        # 6.1: Register manager class
        PlatformManager.register('get_platform_service')
        
        # 6.2: Connect to manager
        self.manager = PlatformManager(
            address=socket_path,
            authkey=authkey
        )
        self.manager.connect()
        
        # 6.3: Get service proxy
        self.service_proxy = self.manager.get_platform_service()
    
    def execute(self, operation, module_name, ansible_data):
        # 6.4: Convert dataclass to dict for RPC
        if is_dataclass(ansible_data):
            data_dict = asdict(ansible_data)
        else:
            data_dict = ansible_data
        
        # 6.5: Execute via proxy (RPC call)
        result_dict = self.service_proxy.execute(
            operation,
            module_name,
            data_dict
        )
        
        return result_dict
```

**Key Points:**
- Connects to manager via Unix socket
- Gets proxy to PlatformService
- Handles serialization (dataclass → dict)
- Makes RPC call to manager process

---

### Step 7: Platform Service - Execute Operation

**File:** `plugins/plugin_utils/manager/platform_manager.py`

```python
class PlatformService(BaseAPIClient):
    def execute(self, operation, module_name, ansible_data_dict):
        # 7.1: Load version-appropriate classes
        AnsibleClass, APIClass, MixinClass = self.loader.load_classes_for_module(
            module_name,
            self.api_version
        )
        
        # 7.2: Reconstruct Ansible dataclass
        ansible_instance = AnsibleClass(**ansible_data_dict)
        
        # 7.3: Build transformation context
        context = TransformContext(
            manager=self,
            session=self.session,
            cache=self.cache,
            api_version=self.api_version
        )
        
        # 7.4: Execute operation
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
- Loads version-appropriate classes dynamically
- Reconstructs Ansible dataclass from dict
- Builds transformation context
- Routes to appropriate operation method

---

### Step 8: API Version Management

**File:** `plugins/plugin_utils/platform/loader.py`

```python
class DynamicClassLoader:
    def load_classes_for_module(self, module_name, api_version):
        # 8.1: Find best matching version
        best_version = self.registry.find_best_version(api_version, module_name)
        
        # 8.2: Check cache
        cache_key = f"{module_name}_{best_version}"
        if cache_key in self._class_cache:
            return self._class_cache[cache_key]
        
        # 8.3: Load Ansible class (stable, version-independent)
        ansible_class = self._load_ansible_class(module_name)
        # Example: AnsibleUser from ansible_models/user.py
        
        # 8.4: Load API classes (version-specific)
        api_class, mixin_class = self._load_api_classes(module_name, best_version)
        # Example: APIUser_v1, UserTransformMixin_v1 from api/v1/user.py
        
        # 8.5: Cache and return
        result = (ansible_class, api_class, mixin_class)
        self._class_cache[cache_key] = result
        return result
```

**Key Points:**
- Discovers available API versions from filesystem
- Finds best matching version
- Loads Ansible class (stable)
- Loads API class and mixin (version-specific)
- Caches loaded classes

---

### Step 9: Transform Ansible → API

**File:** `plugins/plugin_utils/api/v1/user.py`

```python
class UserTransformMixin_v1(BaseTransformMixin):
    @classmethod
    def to_api(cls, ansible_instance, context):
        # 9.1: Create API dataclass instance
        api_instance = cls.from_ansible_data(ansible_instance, context)
        # Returns APIUser_v1 dataclass
        
        # 9.2: Handle complex transformations
        # Example: organization names → IDs
        if ansible_instance.organizations:
            org_ids = cls._names_to_ids(
                ansible_instance.organizations,
                context
            )
            api_instance.organization_ids = org_ids
        
        return api_instance
```

**File:** `plugins/plugin_utils/manager/platform_manager.py`

```python
def _create_resource(self, ansible_data, mixin_class, context):
    # 9.3: FORWARD TRANSFORM: Ansible → API
    api_data = ansible_data.to_api(context)
    # Returns APIUser_v1 dataclass
    
    # 9.4: Get endpoint operations from mixin
    operations = mixin_class.get_endpoint_operations()
    # Returns list of EndpointOperation objects
    
    # 9.5: Execute operations (HTTP request)
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

### Step 10: HTTP Request Execution

**File:** `plugins/plugin_utils/manager/platform_manager.py`

```python
def _execute_operations(self, operations, api_data, context, required_for):
    # 10.1: Convert API dataclass to dict
    from dataclasses import asdict
    api_dict = asdict(api_data)
    
    # 10.2: Get operation details
    op = operations[0]  # For create, typically one operation
    method = op.method  # 'POST'
    endpoint = op.endpoint  # '/api/gateway/v1/users/'
    url = f"{self.base_url}{endpoint}"
    
    # 10.3: Make HTTP request using persistent session
    response = self._make_request(
        method=method,
        url=url,
        data=api_dict,
        context=context
    )
    
    # 10.4: Parse response
    if response.status_code == 201:  # Created
        return response.json()
    else:
        raise HTTPError(f"Request failed: {response.status_code}")
```

**File:** `plugins/plugin_utils/manager/platform_manager.py`

```python
def _make_request(self, method, url, data=None, context=None):
    # 10.5: Use persistent requests.Session
    # Session maintains cookies, connection pooling, etc.
    response = self.session.request(
        method=method,
        url=url,
        json=data,
        headers=self._get_headers(),
        verify=self.verify_ssl,
        timeout=self.timeout
    )
    
    # 10.6: Handle authentication if needed
    if response.status_code == 401:
        self._authenticate()
        response = self.session.request(...)  # Retry
    
    return response
```

**Key Points:**
- Uses persistent `requests.Session`
- Maintains cookies, connection pooling
- Handles authentication automatically
- Retries on 401 errors

---

### Step 11: Transform API → Ansible

**File:** `plugins/plugin_utils/api/v1/user.py`

```python
class UserTransformMixin_v1(BaseTransformMixin):
    @classmethod
    def from_api(cls, api_data, context):
        # 11.1: Convert API dict to API dataclass
        api_instance = APIUser_v1(**api_data)
        
        # 11.2: Build Ansible data dict
        ansible_data = {}
        
        # 11.3: Simple field mappings
        simple_fields = ['username', 'email', 'first_name', 'last_name', ...]
        for field in simple_fields:
            value = getattr(api_instance, field, None)
            if value is not None:
                ansible_data[field] = value
        
        # 11.4: Complex transformation: organization IDs → names
        if api_instance.organization_ids:
            org_names = cls._ids_to_names(
                api_instance.organization_ids,
                context
            )
            ansible_data['organizations'] = org_names
        
        # 11.5: Return AnsibleUser dataclass
        return AnsibleUser(**ansible_data)
```

**File:** `plugins/plugin_utils/manager/platform_manager.py`

```python
def _create_resource(self, ansible_data, mixin_class, context):
    # ... HTTP request executed ...
    
    # 11.6: REVERSE TRANSFORM: API → Ansible
    if api_result:
        ansible_instance = mixin_class.from_api(api_result, context)
        # Returns AnsibleUser dataclass
        
        # 11.7: Convert to dict for Ansible return
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

### Step 12: Return to Action Plugin

**File:** `plugins/action/user.py`

```python
def run(self, tmp=None, task_vars=None):
    # ... previous steps ...
    
    # 12.1: Execute via manager (RPC call)
    manager_result = manager.execute(
        operation=operation,
        module_name=self.MODULE_NAME,
        ansible_data=user.__dict__
    )
    # Returns dict with user data and 'changed' field
    
    # 12.2: Validate output
    validated_output = self._validate_data(
        filtered_result,
        argspec,
        'output'
    )
    
    # 12.3: Format result
    result.update(validated_output.validated_parameters)
    result['changed'] = manager_result.get('changed', False)
    
    # 12.4: Return to Ansible
    return result
```

**Key Points:**
- Receives result dict from RPC call
- Validates output against argspec
- Formats result for Ansible
- Returns to Ansible core

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
  - Example: `_get_or_spawn_manager()` returns `Tuple[Union['DirectHTTPClient', 'ManagerRPCClient'], Optional[Dict[str, Any]]]`

### 2. Process Management
- **Location:** `plugins/plugin_utils/manager/`
- **Purpose:** Spawn and manage persistent manager process
- **Key Files:**
  - `process_manager.py`: Process spawning utilities
  - `manager_process.py`: Standalone manager process script

### 3. RPC Communication
- **Location:** `plugins/plugin_utils/manager/`
- **Purpose:** Client-server communication over Unix sockets
- **Key Files:**
  - `rpc_client.py`: RPC client for action plugins
  - `platform_manager.py`: PlatformService (server-side)

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
- **Location:** `plugins/plugin_utils/manager/platform_manager.py`
- **Purpose:** Make HTTP requests to Gateway API
- **Key Features:**
  - Persistent `requests.Session`
  - Automatic authentication
  - Connection pooling
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
- **Caching:** Lookup results cached in `context.cache` for performance

---

## Connection Reuse

### First Task

1. Action plugin calls `_get_or_spawn_persistent_manager()`
2. No manager found in facts
3. Spawns new manager process
4. Connects via RPC
5. Sets facts: `platform_manager_socket`, `platform_manager_authkey`

### Subsequent Tasks

1. Action plugin calls `_get_or_spawn_persistent_manager()`
2. Finds manager in facts
3. Validates socket path matches expected (same credentials)
4. Reuses existing manager via RPC
5. No new process spawned

### Benefits of Reuse

- **Same HTTP Session:** Cookies, authentication maintained
- **Connection Pooling:** TCP connections reused
- **Caching:** API version, organization lookups cached
- **Performance:** Reduced overhead per task

---

## Summary

The persistent connection mode provides a robust architecture for managing API connections across multiple Ansible tasks:

1. **Isolation:** Manager process isolated from Ansible workers
2. **Reuse:** Multiple tasks share same connection
3. **Performance:** Reduced authentication and connection overhead
4. **Caching:** API version detection and lookups cached
5. **Type Safety:** Dataclass-first approach throughout
6. **Version Management:** Dynamic class loading for API versions
7. **IDE Support:** Type hints enable proper navigation and autocomplete

### Type Hints and IDE Navigation

The codebase includes comprehensive type hints to improve developer experience:

- **Method Signatures:** All manager-related methods include return type annotations
- **Type Imports:** Uses `TYPE_CHECKING` to avoid circular dependencies while providing type information
- **Return Types:** Methods return typed tuples, enabling IDE "Go to Definition" functionality
- **Type Safety:** Type hints help catch errors at development time

**Example:**
```python
def _get_or_spawn_manager(
    self, 
    task_vars: dict
) -> Tuple[Union['DirectHTTPClient', 'ManagerRPCClient'], Optional[Dict[str, Any]]]:
    # Method implementation
```

This enables IDEs to:
- Navigate to method definitions via "Go to Definition"
- Provide autocomplete suggestions
- Show type information on hover
- Catch type mismatches during development

This architecture enables efficient execution of multiple tasks in a playbook while maintaining clean separation of concerns, type safety, and excellent IDE support.
