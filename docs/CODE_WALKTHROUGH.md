# Detailed Code Walkthrough: User Module Execution

This document provides a step-by-step walkthrough of what happens when you run a user module task in an Ansible playbook.

## Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  PLAYBOOK: ansible.platform.user                                │
│  username: demo777, email: demo006@example.com, state: present   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: Ansible Core                                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1. Loads action plugin: user.py                          │  │
│  │ 2. Instantiates ActionModule class                       │  │
│  │ 3. Calls ActionModule.run(task_vars)                     │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2: Action Plugin (user.py)                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 1: Build argspec from DOCUMENTATION                │  │
│  │ Step 2: Validate input (ArgumentSpecValidator)           │  │
│  │ Step 3: Get/spawn manager (_get_or_spawn_manager)      │  │
│  │ Step 4: Create AnsibleUser dataclass                     │  │
│  │ Step 5: Detect operation (create/update/delete)          │  │
│  │ Step 6: Execute via manager (RPC call)                  │  │
│  │ Step 7: Validate output                                 │  │
│  │ Step 8: Format return dict                              │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ RPC (Unix Socket)
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  PHASE 3: Manager Process (platform_manager.py)               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 9: Receive RPC call (execute())                    │  │
│  │ Step 10: Load version-specific classes                  │  │
│  │ Step 11: Forward Transform (AnsibleUser → APIUser_v1)   │  │
│  │ Step 12: Execute API call (HTTP POST)                   │  │
│  │ Step 13: Reverse Transform (API response → Ansible)    │  │
│  │ Step 14: Return result (via RPC)                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ HTTP/HTTPS
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  PHASE 4: Platform API (AAP Gateway)                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ POST /api/gateway/v1/users/                              │  │
│  │ Body: {"username": "demo777", "email": "..."}           │  │
│  │ Response: {"id": 7, "username": "demo777", ...}        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Example Playbook

```yaml
- name: Ensure user demo777 exists
  ansible.platform.user:
    gateway_hostname: "https://18.205.116.155/"
    gateway_token: "{{ lookup('env', 'AAP_TOKEN') }}"
    gateway_validate_certs: false
    gateway_username: admin
    gateway_password: Admin!Password!Gw
    username: demo777
    email: demo006@example.com
    state: present
```

---

## Step-by-Step Execution Flow

### Phase 1: Ansible Task Execution

#### Step 1: Ansible Core Loads Action Plugin

**Location**: Ansible core (not our code)

**What happens**:
1. Ansible sees `ansible.platform.user` in the task
2. Looks for action plugin at: `ansible_collections/ansible/platform/plugins/action/user.py`
3. Instantiates `ActionModule` class from `user.py`

**Code**: `user.py:20-27`
```python
class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = 'user'
```

---

### Phase 2: Action Plugin Initialization

#### Step 2: Action Plugin `run()` Method Called

**Location**: `plugins/action/user.py:29`

**What happens**:
```python
def run(self, tmp=None, task_vars=None):
    result = super(ActionModule, self).run(tmp, task_vars)  # Base class setup
    # ... our code ...
```

**Input**:
- `self._task.args` = `{'username': 'demo777', 'email': 'demo006@example.com', 'state': 'present', 'gateway_hostname': '...', ...}`
- `task_vars` = Ansible variables (inventory, facts, etc.)

---

### Phase 3: Input Validation

#### Step 3: Build Argument Spec from DOCUMENTATION

**Location**: `plugins/action/user.py:52-60`

**Code Flow**:
```python
# Step 1: Build argspec from DOCUMENTATION
argspec = self._build_argspec_from_docs(DOCUMENTATION)
```

**What `_build_argspec_from_docs()` does** (`base_action.py:365-400`):
1. Parses `DOCUMENTATION` string (YAML format)
2. Extracts `options` section
3. Builds Ansible `ArgumentSpec` format:
   ```python
   {
       'argument_spec': {
           'username': {'type': 'str', 'required': True},
           'email': {'type': 'str'},
           'state': {'type': 'str', 'default': 'present'},
           # ... etc
       },
       'mutually_exclusive': [],
       'required_together': [],
       # ... etc
   }
   ```

**Output**: `argspec` dict ready for validation

---

#### Step 4: Validate Input Parameters

**Location**: `plugins/action/user.py:77-89`

**Code Flow**:
```python
# Step 2: Validate input
validated_input = self._validate_data(
    module_args,  # From self._task.args
    argspec,
    'input'
)
```

**What `_validate_data()` does** (`base_action.py:402-430`):
1. Creates `ArgumentSpecValidator` with argspec
2. Validates all parameters against spec
3. Normalizes types (e.g., converts strings to bools)
4. Checks required fields, mutually exclusive, etc.
5. Returns validated dict

**Input**:
```python
{
    'username': 'demo777',
    'email': 'demo006@example.com',
    'state': 'present',
    'gateway_hostname': 'https://18.205.116.155/',
    # ... auth params ...
}
```

**Output**: Same dict, but validated and normalized

---

### Phase 4: Manager Connection

#### Step 5: Get or Spawn Manager

**Location**: `plugins/action/user.py:92-108`

**Code Flow**:
```python
# Step 3: Get or spawning manager
manager = self._get_or_spawn_manager(task_vars)
```

**What `_get_or_spawn_manager()` does** (`base_action.py:169-318`):

**5a. Extract Gateway Config (Platform SDK)**:
```python
# Uses Platform SDK for generic config extraction
from ...platform.config import extract_gateway_config

gateway_config = extract_gateway_config(
    task_args=self._task.args,
    host_vars=host_vars,
    required=True
)
# Returns GatewayConfig dataclass
```

**5b. Check for Existing Manager**:
```python
# Check hostvars and task_vars for existing manager
socket_path = (
    host_vars.get('platform_manager_socket') or 
    task_vars.get('platform_manager_socket')
)
authkey_b64 = (
    host_vars.get('platform_manager_authkey') or 
    task_vars.get('platform_manager_authkey')
)

if socket_path and authkey_b64 and Path(socket_path).exists():
    # Connect to existing manager
    authkey = base64.b64decode(authkey_b64)
    client = ManagerRPCClient(gateway_config.base_url, socket_path, authkey)
    return client, None  # Returns tuple: (client, facts_dict)
```

**5c. Spawn New Manager** (if not found, uses Platform SDK):
```python
# Uses Platform SDK ProcessManager for generic process management
from ...manager.process_manager import ProcessManager

# Generate connection info
conn_info = ProcessManager.generate_connection_info(
    identifier=inventory_hostname,
    socket_dir=socket_dir
)

# Spawn manager process
process = ProcessManager.spawn_manager_process(
    script_path=script_path,
    socket_path=conn_info.socket_path,
    socket_dir=str(socket_dir),
    identifier=inventory_hostname,
    gateway_config=gateway_config,
    authkey_b64=conn_info.authkey_b64,
    sys_path=parent_sys_path
)

# Wait for process startup
ProcessManager.wait_for_process_startup(...)

# Return tuple: (client, facts_dict)
return client, {
    'platform_manager_socket': socket_path,
    'platform_manager_authkey': authkey_b64,
    'gateway_url': gateway_config.base_url
}
```

**5d. Set Facts in Result** (`user.py:101-106`):
```python
manager, facts_to_set = self._get_or_spawn_manager(task_vars)

if facts_to_set:
    result['ansible_facts'] = facts_to_set
    result['_ansible_facts_cacheable'] = True
    # Facts will be available in hostvars for next task
```

**Manager Process Startup** (`manager_process.py:16-195`):
1. Reads arguments and environment variables
2. Restores `sys.path` from parent
3. Imports `PlatformService` and `PlatformManager`
4. Creates `PlatformService` (authenticates, detects API version)
5. Registers service with `PlatformManager`
6. Starts BaseManager server: `server.serve_forever()`

**Output**: `ManagerRPCClient` instance connected to manager

---

### Phase 5: Data Preparation

#### Step 6: Create Ansible Dataclass

**Location**: `plugins/action/user.py:110-117`

**Code Flow**:
```python
# Step 4: Create dataclass from validated input
user_data = {
    k: v for k, v in validated_input.items()
    if v is not None and k not in auth_params
}
user = AnsibleUser(**user_data)
```

**What happens**:
1. Filters out auth parameters (not part of user data)
2. Creates `AnsibleUser` dataclass instance

**Input**:
```python
{
    'username': 'demo777',
    'email': 'demo006@example.com',
    'state': 'present'
}
```

**Output**: `AnsibleUser(username='demo777', email='demo006@example.com', state='present')`

**Code**: `ansible_models/user.py:12-61`

---

#### Step 7: Detect Operation Type

**Location**: `plugins/action/user.py:119-121`

**Code Flow**:
```python
# Step 5: Detect operation
operation = self._detect_operation(validated_input)
```

**What `_detect_operation()` does** (`base_action.py:432-450`):
- `state='absent'` → `'delete'`
- `state='present'` + `id` provided → `'update'`
- `state='present'` + no `id` → `'create'`
- `state='find'` → `'find'`

**Output**: `'create'` (since no `id` provided)

---

#### Step 8: Idempotency Check (for create operations)

**Location**: `plugins/action/user.py:123-139`

**Code Flow**:
```python
# Step 5.5: For 'create' with state='present', check if user exists
if operation == 'create' and validated_input.get('state') == 'present':
    find_result = manager.execute(
        operation='find',
        module_name='user',
        ansible_data={'username': user.username}
    )
    if find_result and find_result.get('id'):
        operation = 'update'  # Switch to update
        user.id = find_result.get('id')
```

**What happens**:
1. Calls manager's `find` operation
2. If user exists, switches to `update` and sets `user.id`
3. If not found, proceeds with `create`

**This ensures idempotency**: Running the playbook twice won't create duplicate users.

---

### Phase 6: RPC Communication

#### Step 9: Execute Operation via Manager (RPC Call)

**Location**: `plugins/action/user.py:141-147`

**Code Flow**:
```python
# Step 6: Execute via manager
manager_result = manager.execute(
    operation='create',  # or 'update'
    module_name='user',
    ansible_data=user.__dict__
)
```

**What `manager.execute()` does** (`rpc_client.py:67-99`):
1. Converts dataclass to dict: `asdict(user)`
2. Calls service proxy via BaseManager RPC:
   ```python
   result_dict = self.service_proxy.execute(
       'create',
       'user',
       {'username': 'demo777', 'email': 'demo006@example.com', ...}
   )
   ```

**RPC Communication**:
- Client (`rpc_client.py`) → Unix Socket → Server (`platform_manager.py`)
- BaseManager handles serialization (pickle)
- Method call sent over socket
- Response received and unpickled

---

### Phase 7: Manager-Side Processing

#### Step 10: Manager Receives RPC Call

**Location**: `plugins/plugin_utils/manager/platform_manager.py:196-273`

**Code Flow**:
```python
def execute(self, operation, module_name, ansible_data_dict):
    # Load version-appropriate classes
    AnsibleClass, APIClass, MixinClass = self.loader.load_classes_for_module(
        'user',
        self.api_version  # e.g., '1'
    )
    
    # Reconstruct Ansible dataclass
    ansible_instance = AnsibleClass(**ansible_data_dict)
    # → AnsibleUser(username='demo777', ...)
```

**What happens**:
1. `DynamicClassLoader` loads:
   - `AnsibleUser` from `ansible_models/user.py`
   - `APIUser_v1` from `api/v1/user.py`
   - `UserTransformMixin_v1` from `api/v1/user.py`
2. Reconstructs `AnsibleUser` from dict

---

#### Step 11: Forward Transformation (Ansible → API)

**Location**: `platform_manager.py:275-312` (for create)

**Code Flow**:
```python
def _create_resource(self, ansible_data, mixin_class, context):
    # FORWARD TRANSFORM: Ansible → API
    api_data = ansible_data.to_api(context)
```

**What `to_api()` does** (`ansible_models/user.py:49-61`):
```python
def to_api(self, context):
    from ..api.v1.user import UserTransformMixin_v1
    return UserTransformMixin_v1.from_ansible_data(self, context)
```

**What `from_ansible_data()` does** (`api/v1/user.py:48-80`):
1. Maps simple fields: `username`, `email`, etc.
2. Transforms `organizations` (names → IDs):
   ```python
   if ansible_instance.organizations:
       api_data['organization_ids'] = cls._names_to_ids(
           ansible_instance.organizations,
           context
       )
   ```
3. Returns `APIUser_v1` instance

**Input**: `AnsibleUser(username='demo777', email='demo006@example.com')`
**Output**: `APIUser_v1(username='demo777', email='demo006@example.com')`

---

#### Step 12: Execute API Call

**Location**: `platform_manager.py:298-301`

**Code Flow**:
```python
# Get endpoint operations from mixin
operations = mixin_class.get_endpoint_operations()
# → {'create': EndpointOperation(path='/api/gateway/v1/users/', method='POST', ...)}

# Execute operations
api_result = self._execute_operations(
    operations, api_data, context, required_for='create'
)
```

**What `_execute_operations()` does** (`platform_manager.py:472-588`):
1. Gets `create` operation from `UserTransformMixin_v1.get_endpoint_operations()`
2. Extracts fields for this endpoint
3. Builds URL: `https://18.205.116.155/api/gateway/v1/users/`
4. Makes HTTP POST request:
   ```python
   response = self.session.post(
       url,
       json={'username': 'demo777', 'email': 'demo006@example.com'},
       timeout=self.request_timeout,
       verify=self.verify_ssl
   )
   ```
5. Parses JSON response

**API Response**:
```json
{
    "id": 7,
    "username": "demo777",
    "email": "demo006@example.com",
    "created": "2025-11-15T16:10:42.860956Z",
    "modified": "2025-11-15T16:10:42.860948Z",
    "url": "/api/gateway/v1/users/7/"
}
```

---

#### Step 13: Reverse Transformation (API → Ansible)

**Location**: `platform_manager.py:303-310`

**Code Flow**:
```python
# REVERSE TRANSFORM: API → Ansible
if api_result:
    ansible_result = mixin_class.from_api(api_result, context)
    ansible_result['changed'] = True  # Mark as changed
    return ansible_result
```

**What `from_api()` does** (`api/v1/user.py:243-278`):
1. Maps API fields back to Ansible fields
2. Transforms `organization_ids` → `organizations` (IDs → names):
   ```python
   if 'organization_ids' in api_data:
       ansible_data['organizations'] = cls._ids_to_names(
           api_data['organization_ids'],
           context
       )
   ```
3. Returns dict in Ansible format

**Input**: API response dict
**Output**: `{'username': 'demo777', 'email': 'demo006@example.com', 'id': 7, 'changed': True, ...}`

---

### Phase 8: Response Handling

#### Step 14: Receive Result from Manager

**Location**: `plugins/action/user.py:148-149`

**Code Flow**:
```python
# Step 6: Execute via manager
manager_result = manager.execute(...)
# → {'username': 'demo777', 'email': 'demo006@example.com', 'id': 7, 'changed': True, ...}
```

**Result received via RPC**:
- BaseManager unpickles the response
- Returns dict to action plugin

---

#### Step 15: Validate Output

**Location**: `plugins/action/user.py:151-175`

**Code Flow**:
```python
# Step 7: Validate output
read_only_fields = {'id', 'created', 'modified', 'url'}
argspec_fields = set(argspec.get('argument_spec', {}).keys())

# Filter out read-only fields for validation
filtered_result = {
    k: v for k, v in manager_result.items()
    if k in argspec_fields or k in read_only_fields
}

validated_output = self._validate_data(
    {k: v for k, v in filtered_result.items() if k in argspec_fields},
    argspec,
    'output'
)

# Add back read-only fields
for field in read_only_fields:
    if field in filtered_result:
        validated_output[field] = filtered_result[field]
```

**Why filter read-only fields?**
- API returns `id`, `created`, `modified`, `url`
- These aren't in the module's `DOCUMENTATION` (argspec)
- We filter them out for validation, then add them back

---

#### Step 16: Format Return Dictionary

**Location**: `plugins/action/user.py:177-183`

**Code Flow**:
```python
# Step 8: Format return dict
result.update({
    'changed': manager_result.get('changed', False),  # True for create
    'failed': False,
    'user': validated_output,  # Full user data
    'id': validated_output.get('id'),  # Convenience field
})
```

**Final Result**:
```python
{
    'changed': True,
    'failed': False,
    'user': {
        'username': 'demo777',
        'email': 'demo006@example.com',
        'id': 7,
        'created': '2025-11-15T16:10:42.860956Z',
        'modified': '2025-11-15T16:10:42.860948Z',
        'url': '/api/gateway/v1/users/7/'
    },
    'id': 7
}
```

---

### Phase 9: Ansible Output

#### Step 17: Ansible Displays Result

**Location**: Ansible core (not our code)

**What Ansible does**:
1. Receives result dict from action plugin
2. Displays to user:
   ```
   ok: [127.0.0.1] => {
       "changed": true,
       "id": 7,
       "user": {
           "username": "demo777",
           "email": "demo006@example.com",
           ...
       }
   }
   ```
3. Updates play recap: `changed=1`

---

## Second Task: Reusing Manager

When the second task runs:

```yaml
- name: Ensure user demo888 exists
  ansible.platform.user:
    username: demo888
    # ... same auth params ...
```

**What's different**:

1. **Step 5 (Manager Connection)**: 
   - Finds existing manager in `hostvars`
   - Connects to existing manager (no spawn)
   - Reuses persistent HTTP session

2. **All other steps**: Same as first task

**Benefits**:
- No authentication overhead (session reused)
- No API version detection (cached)
- Faster execution (50-75% improvement)

---

## Key Data Transformations

### Transformation Flow

```
Playbook Input (YAML)
    ↓
Validated Input (dict)
    ↓
AnsibleUser (dataclass)
    ↓ [Forward Transform]
APIUser_v1 (dataclass)
    ↓ [HTTP POST]
Platform API
    ↓ [HTTP Response]
API Response (dict)
    ↓ [Reverse Transform]
AnsibleUser (dict)
    ↓
Validated Output (dict)
    ↓
Playbook Output (YAML)
```

### Example Transformation

**Input** (Playbook):
```yaml
username: demo777
email: demo006@example.com
organizations: ['Engineering', 'DevOps']
```

**After Forward Transform** (API Request):
```json
{
    "username": "demo777",
    "email": "demo006@example.com",
    "organization_ids": [1, 2]  // Names converted to IDs
}
```

**After API Response** (Reverse Transform):
```python
{
    "username": "demo777",
    "email": "demo006@example.com",
    "organizations": ["Engineering", "DevOps"],  // IDs converted back to names
    "id": 7,
    "created": "2025-11-15T16:10:42.860956Z"
}
```

---

## File Locations Summary

| Component | File | Key Function/Method |
|-----------|------|---------------------|
| **Playbook** | `user.yml` | Defines tasks |
| **Action Plugin** | `plugins/action/user.py` | `ActionModule.run()` |
| **Base Action** | `plugins/action/base_action.py` | `_get_or_spawn_manager()`, `_validate_data()`, etc. |
| **RPC Client** | `plugins/plugin_utils/manager/rpc_client.py` | `ManagerRPCClient.execute()` |
| **Manager Service** | `plugins/plugin_utils/manager/platform_manager.py` | `PlatformService.execute()` |
| **Manager Process** | `plugins/plugin_utils/manager/manager_process.py` | `main()` - spawns manager |
| **Ansible Model** | `plugins/plugin_utils/ansible_models/user.py` | `AnsibleUser` dataclass |
| **API Model** | `plugins/plugin_utils/api/v1/user.py` | `APIUser_v1`, `UserTransformMixin_v1` |
| **Documentation** | `plugins/plugin_utils/docs/user.py` | `DOCUMENTATION` string |

---

## Debugging Tips

### Enable Verbose Output

```bash
ansible-playbook user.yml -vvv  # Shows all debug messages
```

### Check Manager Logs

```bash
# Manager error log
cat /tmp/ansible_platform/manager_error_localhost.log

# Manager stderr log
cat /tmp/ansible_platform/manager_stderr_localhost.log
```

### Verify Manager is Running

```bash
# Check if socket exists
ls -la /tmp/ansible_platform/manager_*.sock

# Check process
ps aux | grep manager_process.py
```

### Trace RPC Calls

Add logging to `rpc_client.py` and `platform_manager.py` to see RPC communication.

---

## Code Snippets with Line Numbers

### Step 1: Build Argspec (`base_action.py:379-412`)

```python
def _build_argspec_from_docs(self, documentation: str) -> dict:
    doc_data = yaml.safe_load(documentation)  # Parse YAML
    options = doc_data.get('options', {})
    
    argspec = {
        'argument_spec': options,  # ← Key for ArgumentSpecValidator
        'mutually_exclusive': doc_data.get('mutually_exclusive', []),
        'required_together': doc_data.get('required_together', []),
        'required_one_of': doc_data.get('required_one_of', []),
        'required_if': doc_data.get('required_if', []),
    }
    return argspec
```

### Step 2: Validate Input (`base_action.py:414-467`)

```python
def _validate_data(self, data: dict, argspec: dict, direction: str) -> dict:
    validator = ArgumentSpecValidator(
        argument_spec=argspec.get('argument_spec', {}),
        mutually_exclusive=argspec.get('mutually_exclusive'),
        # ... other params ...
    )
    
    result = validator.validate(data)
    if result.error_messages:
        raise AnsibleError(f"{direction.title()} validation failed: ...")
    
    return result.validated_parameters
```

### Step 3: Get/Spawn Manager (`base_action.py:169-318`)

```python
def _get_or_spawn_manager(self, task_vars: dict):
    # Extract gateway config using Platform SDK
    from ...platform.config import extract_gateway_config
    gateway_config = extract_gateway_config(
        task_args=self._task.args,
        host_vars=host_vars,
        required=True
    )
    
    # Check for existing manager
    socket_path = host_vars.get('platform_manager_socket') or task_vars.get('platform_manager_socket')
    if socket_path and Path(socket_path).exists():
        return ManagerRPCClient(...), None  # Returns tuple
    
    # Spawn new manager using Platform SDK
    from ...manager.process_manager import ProcessManager
    conn_info = ProcessManager.generate_connection_info(...)
    process = ProcessManager.spawn_manager_process(...)
    ProcessManager.wait_for_process_startup(...)
    
    # Return tuple: (client, facts_dict)
    return ManagerRPCClient(...), {
        'platform_manager_socket': socket_path,
        'platform_manager_authkey': authkey_b64,
        'gateway_url': gateway_config.base_url
    }
```

**Facts are set in result** (`user.py:101-106`):
```python
manager, facts_to_set = self._get_or_spawn_manager(task_vars)
if facts_to_set:
    result['ansible_facts'] = facts_to_set
    result['_ansible_facts_cacheable'] = True
```

### Step 4: Create Dataclass (`user.py:110-117`)

```python
user_data = {
    k: v for k, v in validated_input.items()
    if v is not None and k not in auth_params
}
user = AnsibleUser(**user_data)
# → AnsibleUser(username='demo777', email='demo006@example.com', ...)
```

### Step 5: Execute via Manager (`user.py:143-147`)

```python
manager_result = manager.execute(
    operation='create',
    module_name='user',
    ansible_data=user.__dict__
)
```

### Step 6: RPC Client (`rpc_client.py:67-99`)

```python
def execute(self, operation: str, module_name: str, ansible_data: Any):
    # Convert to dict
    data_dict = asdict(ansible_data) if is_dataclass(ansible_data) else ansible_data
    
    # RPC call via BaseManager
    result_dict = self.service_proxy.execute(
        operation,
        module_name,
        data_dict
    )
    return result_dict
```

### Step 7: Manager Execute (`platform_manager.py:196-273`)

```python
def execute(self, operation: str, module_name: str, ansible_data_dict: dict):
    # Load classes
    AnsibleClass, APIClass, MixinClass = self.loader.load_classes_for_module(
        module_name, self.api_version
    )
    
    # Reconstruct dataclass
    ansible_instance = AnsibleClass(**ansible_data_dict)
    
    # Build TransformContext (type-safe, not dict)
    from ...platform.types import TransformContext
    context = TransformContext(
        manager=self,
        session=self.session,
        cache=self.cache,
        api_version=self.api_version
    )
    
    # Execute operation
    if operation == 'create':
        result = self._create_resource(ansible_instance, MixinClass, context)
    # ...
    
    return result
```

### Step 8: Forward Transform (`platform_manager.py:292-293`)

```python
# In _create_resource()
api_data = ansible_data.to_api(context)
# → Calls UserTransformMixin_v1.from_ansible_data()
# → context is TransformContext dataclass (type-safe)
# → Returns APIUser_v1 instance
```

### Step 9: API Call (`platform_manager.py:472-588`)

```python
def _execute_operations(self, operations, api_data, context, required_for):
    # Get create operation
    endpoint_op = operations['create']
    # → EndpointOperation(path='/api/gateway/v1/users/', method='POST', ...)
    
    # Build URL
    url = self._build_url(endpoint_op.path)
    # → https://18.205.116.155/api/gateway/v1/users/
    
    # Make request
    response = self.session.post(
        url,
        json=asdict(api_data),  # Convert APIUser_v1 to dict
        timeout=self.request_timeout,
        verify=self.verify_ssl
    )
    
    return response.json()
```

### Step 10: Reverse Transform (`platform_manager.py:307`)

```python
# In _create_resource()
ansible_result = mixin_class.from_api(api_result, context)
# → Calls UserTransformMixin_v1.from_api()
# → Returns dict in Ansible format
ansible_result['changed'] = True
return ansible_result
```

### Step 11: Validate Output (`user.py:151-175`)

```python
# Filter read-only fields
read_only_fields = {'id', 'created', 'modified', 'url'}
filtered_result = {
    k: v for k, v in manager_result.items()
    if k in argspec_fields or k in read_only_fields
}

# Validate
validated_output = self._validate_data(
    {k: v for k, v in filtered_result.items() if k in argspec_fields},
    argspec,
    'output'
)

# Add back read-only fields
for field in read_only_fields:
    if field in filtered_result:
        validated_output[field] = filtered_result[field]
```

### Step 12: Format Result (`user.py:177-183`)

```python
result.update({
    'changed': manager_result.get('changed', False),  # True
    'failed': False,
    'user': validated_output,
    'id': validated_output.get('id'),
})
```

---

## Summary

1. **Ansible** loads action plugin
2. **Action Plugin** validates input, gets/spawns manager
3. **RPC Client** sends request to manager via Unix socket
4. **Manager** transforms data, calls API, transforms response
5. **RPC Client** receives response
6. **Action Plugin** validates output, formats result
7. **Ansible** displays result to user

The entire flow maintains **type safety** and **validation** at every step, ensuring data integrity throughout the process.

---

## Key Design Decisions

### Why Manager-Side Transformations?

- **Performance**: Transformations happen once in persistent process
- **Consistency**: Single source of truth for API format
- **Version Management**: Manager handles API version detection

### Why RPC Instead of Direct Calls?

- **Persistence**: Manager maintains HTTP session across tasks
- **Isolation**: Manager process separate from Ansible process
- **Reusability**: Multiple tasks share same manager

### Why subprocess.Popen Instead of multiprocessing.Process?

- **Reliability**: Avoids import issues with Ansible's complex plugin system
- **macOS Compatibility**: No fork/SSL issues
- **Simplicity**: No pickling concerns

### Why BaseManager for RPC?

- **Built-in**: Python standard library, well-tested
- **Thread-safe**: ThreadingMixIn handles concurrent clients
- **Efficient**: Unix domain sockets for local IPC

