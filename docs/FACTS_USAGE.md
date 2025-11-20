# Ansible Facts Usage in Platform Collection

This document explains exactly where and how Ansible facts are used in the platform collection.

## Overview

Ansible facts are used to **persist manager connection information** across tasks in a playbook. This allows the manager process to be spawned once and reused by all subsequent tasks, providing significant performance benefits.

## Where Facts Are Used

### 1. Reading Facts (Checking for Existing Manager)

**Location**: `plugins/action/base_action.py:191-197`

**Code**:
```python
def _get_or_spawn_manager(self, task_vars: dict):
    # Check if manager info in hostvars
    hostvars = task_vars.get('hostvars', {})
    inventory_hostname = task_vars.get('inventory_hostname', 'localhost')
    host_vars = hostvars.get(inventory_hostname, {})
    
    socket_path = host_vars.get('platform_manager_socket')
    authkey_b64 = host_vars.get('platform_manager_authkey')
```

**What it does**:
- Extracts `hostvars` from `task_vars` (Ansible's variable dictionary)
- Gets the current host's variables using `inventory_hostname`
- Checks if `platform_manager_socket` and `platform_manager_authkey` facts exist
- If both exist and socket file exists, reuses the existing manager

**Also reads from facts** (lines 202-235):
- `gateway_url` or `gateway_hostname` - Platform URL
- `gateway_username` or `aap_username` - Authentication username
- `gateway_password` or `aap_password` - Authentication password
- `gateway_token` or `aap_token` - OAuth token
- `gateway_validate_certs` - SSL certificate validation flag
- `gateway_request_timeout` - Request timeout value

**Priority order**:
1. Task arguments (highest priority)
2. Host facts (from previous tasks)
3. Default values (lowest priority)

### 2. Writing Facts (Storing Manager Info)

**Location**: `plugins/action/base_action.py:298-318` and `plugins/action/user.py:101-106`

**Code**:
```python
# In base_action.py: _get_or_spawn_manager() returns tuple
return client, {
    'platform_manager_socket': socket_path,
    'platform_manager_authkey': authkey_b64,
    'gateway_url': gateway_config.base_url
}

# In user.py: Set facts directly in result dict
manager, facts_to_set = self._get_or_spawn_manager(task_vars)

if facts_to_set:
    logger.info(f"Setting facts for manager reuse: socket={facts_to_set.get('platform_manager_socket')}")
    result['ansible_facts'] = facts_to_set
    result['_ansible_facts_cacheable'] = True
    logger.info("Facts set successfully in result (will be available for next task via hostvars)")
```

**What it does**:
- After spawning a new manager process, stores connection info in Ansible facts
- Sets facts **directly in the result dict** (not via `set_fact` module)
- Sets `_ansible_facts_cacheable: True` so facts persist across multiple plays in a playbook
- Stores:
  - `platform_manager_socket`: Path to Unix socket for RPC communication
  - `platform_manager_authkey`: Base64-encoded authentication key
  - `gateway_url`: Platform URL (for validation)

**When it happens**:
- Only when spawning a **new** manager (not when reusing existing one)
- After manager process is successfully started and socket is created
- Facts are set in the result dict, which Ansible's TaskExecutor processes automatically

## Facts Stored

### `platform_manager_socket`
- **Type**: String (file path)
- **Example**: `/tmp/ansible_platform/manager_localhost.sock`
- **Purpose**: Path to Unix domain socket for RPC communication
- **Used by**: `ManagerRPCClient` to connect to manager

### `platform_manager_authkey`
- **Type**: String (base64-encoded bytes)
- **Example**: `"dGhpc2lzYXNlY3JldGtleQ=="`
- **Purpose**: Authentication key for secure RPC communication
- **Used by**: `ManagerRPCClient` to authenticate with manager

### `gateway_url`
- **Type**: String (URL)
- **Example**: `"https://platform.example.com"`
- **Purpose**: Platform URL (stored for validation/consistency)
- **Used by**: Validation to ensure same platform is used across tasks

## Flow Diagram

```
Task 1 (First Task):
┌─────────────────────────────────────┐
│ Action Plugin                       │
│ 1. Check hostvars for manager      │
│    → Not found                      │
│ 2. Spawn new manager                │
│ 3. Store facts:                     │
│    - platform_manager_socket        │
│    - platform_manager_authkey       │
│    - gateway_url                    │
│ 4. Connect to manager               │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Ansible Facts (hostvars)            │
│ platform_manager_socket: "/tmp/..." │
│ platform_manager_authkey: "abc..."  │
│ gateway_url: "https://..."         │
└─────────────────────────────────────┘

Task 2 (Subsequent Task):
┌─────────────────────────────────────┐
│ Action Plugin                       │
│ 1. Check hostvars for manager      │
│    → Found!                         │
│ 2. Verify socket exists             │
│ 3. Connect to existing manager      │
│    (No fact writing needed)         │
└─────────────────────────────────────┘
```

## Benefits

1. **Performance**: Manager is spawned once, reused across all tasks
   - Saves ~50-75% execution time (no auth overhead per task)
   - Persistent HTTP session across tasks
   - Cached API version detection
   - Cached lookup tables (org names ↔ IDs)

2. **Resource Efficiency**: Single manager process handles all tasks
   - One persistent connection instead of many
   - Better resource utilization

3. **Consistency**: Same manager instance ensures:
   - Same API version across all tasks
   - Consistent authentication
   - Shared cache state

## Technical Details

### How Facts Are Populated in Ansible (Complete Flow)

Here's the exact flow of how facts get from the result dict to `hostvars`:

#### Step 1: Action Plugin Sets Facts in Result
**Location**: `plugins/action/user.py:101-106`

```python
manager, facts_to_set = self._get_or_spawn_manager(task_vars)

if facts_to_set:
    result['ansible_facts'] = facts_to_set
    result['_ansible_facts_cacheable'] = True
```

The action plugin returns a result dict with:
```python
{
    'ansible_facts': {
        'platform_manager_socket': '/tmp/...',
        'platform_manager_authkey': 'abc...',
        'gateway_url': 'https://...'
    },
    '_ansible_facts_cacheable': True,
    'changed': True,
    'user': {...}
}
```

#### Step 2: TaskExecutor Processes Result
**Location**: `ansible/lib/ansible/executor/task_executor.py:775-789`

The `TaskExecutor` extracts `ansible_facts` from the result and adds them to the `variables` dict:
```python
if 'ansible_facts' in result:
    af = result['ansible_facts']
    variables['ansible_facts'] = combine_vars(
        variables.get('ansible_facts', {}), 
        namespace_facts(af)
    )
    # Also injects facts into top-level variables if configured
    variables.update(clean_facts(af))
```

#### Step 3: Strategy Plugin Stores Facts
**Location**: `ansible/lib/ansible/plugins/strategy/__init__.py:709-720`

The strategy plugin (e.g., `linear`, `free`) processes the result and stores facts:

```python
cacheable = result_item.pop('_ansible_facts_cacheable', False)
for target_host in host_list:
    is_set_fact = original_task.action in C._ACTION_SET_FACT
    
    # If cacheable=True OR not set_fact action, store in fact cache
    if not is_set_fact or cacheable:
        self._variable_manager.set_host_facts(
            target_host, 
            result_item['ansible_facts'].copy()
        )
    
    # set_fact always creates non-persistent facts (host vars)
    if is_set_fact:
        self._variable_manager.set_nonpersistent_facts(
            target_host, 
            result_item['ansible_facts'].copy()
        )
```

#### Step 4: VariableManager Stores in Fact Cache
**Location**: `ansible/lib/ansible/vars/manager.py:564-587`

`VariableManager.set_host_facts()` stores facts in the fact cache:
```python
def set_host_facts(self, host, facts):
    try:
        host_cache = self._fact_cache.get(host)
    except KeyError:
        host_cache = facts
    else:
        host_cache |= facts  # Merge with existing
    
    # Save back to backing store (file or memory)
    self._fact_cache.set(host, host_cache)
```

#### Step 5: Facts Available in hostvars
**Location**: `ansible/lib/ansible/vars/manager.py:289-310`

When `get_vars()` is called for subsequent tasks, facts are retrieved:
```python
# Get facts from cache
facts = self._fact_cache.get(host.name)

# Namespace them as ansible_facts
all_vars |= namespace_facts(facts)

# Optionally inject into top-level namespace
if INJECT_FACTS:
    all_vars.update(clean_facts(facts))
```

These facts are then available in `task_vars['hostvars'][hostname]` for subsequent tasks.

### Fact Storage Locations

1. **Fact Cache** (`VariableManager._fact_cache`):
   - Persistent storage (file-based or memory)
   - Accessed via `VariableManager.set_host_facts()`
   - Retrieved via `VariableManager._fact_cache.get(host)`
   - Used when `cacheable: True`

2. **Non-Persistent Facts** (`VariableManager._nonpersistent_fact_cache`):
   - In-memory only (not persisted)
   - Accessed via `VariableManager.set_nonpersistent_facts()`
   - Used for regular `set_fact` (without `cacheable`)

3. **hostvars** (in `task_vars`):
   - Combined view of all variables for a host
   - Includes facts from cache + non-persistent facts
   - Structure: `hostvars[hostname][fact_name] = value`
   - Built dynamically when `get_vars()` is called

### How Facts Work in Ansible

1. **hostvars**: Dictionary containing variables for all hosts
   - Structure: `hostvars[hostname][fact_name] = value`
   - Accessible via `task_vars.get('hostvars', {})`
   - Built from fact cache + non-persistent facts + other sources

2. **set_fact module**: Sets facts for current host
   - With `cacheable: True`: Stored in fact cache (persistent)
   - Without `cacheable`: Stored as non-persistent facts (in-memory only)
   - Both are available in `hostvars` for subsequent tasks

3. **Fact Scope**: Facts are per-host
   - Each host in inventory has its own facts
   - Manager is spawned per-host (if using multiple hosts)

### Error Handling

- Facts are set directly in the result dict, so there's no risk of module execution failure
- If facts aren't set (e.g., if `_get_or_spawn_manager` returns `None` for facts), manager connection still works
- Next task will spawn a new manager if facts are missing from hostvars

### Security Considerations

- `authkey` is base64-encoded but not encrypted in facts
- Facts are stored in Ansible's fact cache (file system or memory)
- Accessible to all tasks in the playbook
- Should be treated as sensitive data

## Related Code Locations

- **Reading facts**: `plugins/action/base_action.py:208-222`
- **Writing facts**: `plugins/action/base_action.py:298-318` (returns facts dict) and `plugins/action/user.py:101-106` (sets in result)
- **Using facts**: `plugins/action/base_action.py:221-233` (reuse logic)
- **Manager connection**: `plugins/plugin_utils/manager/rpc_client.py`
- **Platform SDK config**: `plugins/plugin_utils/platform/config.py` (GatewayConfig extraction)
- **Process management**: `plugins/plugin_utils/manager/process_manager.py` (ProcessManager)

## See Also

- `ARCHITECTURE.md` - Overall architecture
- `FLOW_EXPLANATION.md` - Complete flow explanation
- `CODE_WALKTHROUGH.md` - Detailed code walkthrough

