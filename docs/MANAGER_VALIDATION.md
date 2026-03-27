# Manager Existence Validation

This document explains exactly how we validate that a Manager already exists and how we handle edge cases.

## Answer: Yes, It Uses a Unix Domain Socket!

The manager uses a **Unix domain socket** for RPC communication. Validation happens in **3 steps**.

## Validation Flow

### Step 1: Check Facts (hostvars)

**Location**: `plugins/action/base_action.py:196-197`

```python
socket_path = host_vars.get('platform_manager_socket')
authkey_b64 = host_vars.get('platform_manager_authkey')
```

**What it checks**:
- Is `platform_manager_socket` stored in Ansible facts?
- Is `platform_manager_authkey` stored in Ansible facts?

**If either is missing**: Manager doesn't exist → spawn new one

### Step 2: Check Socket File Exists

**Location**: `plugins/action/base_action.py:247`

```python
if socket_path and authkey_b64 and Path(socket_path).exists():
```

**What it checks**:
- Does the socket file exist on the filesystem?
- Uses `Path(socket_path).exists()` to check

**Socket path format**: `/tmp/ansible_platform/manager_{hostname}.sock`

**If socket file doesn't exist**: Manager doesn't exist → spawn new one

### Step 3: Try to Connect

**Location**: `plugins/action/base_action.py:248-252`

```python
try:
    authkey = base64.b64decode(authkey_b64)
    client = ManagerRPCClient(gateway_url, socket_path, authkey)
    logger.info("Connected to existing manager")
    return client
except Exception as e:
    logger.warning(
        f"Failed to connect to existing manager: {e}. "
        f"Spawning new one..."
    )
    # Fall through to spawn new one
```

**What it does**:
- Attempts to connect via `ManagerRPCClient`
- If connection succeeds → manager exists, reuse it
- If connection fails → manager is dead, spawn new one

## Complete Validation Code

**Location**: `plugins/action/base_action.py:246-258`

```python
# If manager already running, try to connect
if socket_path and authkey_b64 and Path(socket_path).exists():
    try:
        authkey = base64.b64decode(authkey_b64)
        client = ManagerRPCClient(gateway_url, socket_path, authkey)
        logger.info("Connected to existing manager")
        return client
    except Exception as e:
        logger.warning(
            f"Failed to connect to existing manager: {e}. "
            f"Spawning new one..."
        )
        # Fall through to spawn new one

# Spawn new manager (if we get here, validation failed)
```

## What Happens During Connection?

**Location**: `plugins/plugin_utils/manager/rpc_client.py:57-64`

```python
# Connect to manager
logger.debug(f"Connecting to manager at {socket_path}")
self.manager = PlatformManager(
    address=socket_path,
    authkey=authkey
)
self.manager.connect()  # ← This will fail if manager is dead

# Get service proxy
self.service_proxy = self.manager.get_platform_service()
logger.info("Connected to Platform Manager")
```

**What `manager.connect()` does**:
- Attempts to connect to the Unix socket at `socket_path`
- Authenticates using `authkey`
- If manager process is dead, socket connection fails
- Exception is caught, and we spawn a new manager

## Edge Cases Handled

### Case 1: Socket File Exists But Manager is Dead

**Scenario**: 
- Socket file exists (leftover from crashed manager)
- Manager process is dead

**What happens**:
1. ✅ Step 1 passes (facts exist)
2. ✅ Step 2 passes (socket file exists)
3. ❌ Step 3 fails (`manager.connect()` raises exception)
4. ✅ Exception caught, spawns new manager

**Code**:
```python
except Exception as e:
    logger.warning(
        f"Failed to connect to existing manager: {e}. "
        f"Spawning new one..."
    )
    # Fall through to spawn new one
```

### Case 2: Facts Exist But Socket File Missing

**Scenario**:
- Facts exist in `hostvars`
- Socket file was deleted (e.g., system cleanup)

**What happens**:
1. ✅ Step 1 passes (facts exist)
2. ❌ Step 2 fails (`Path(socket_path).exists()` returns False)
3. ✅ Spawns new manager

**Code**:
```python
if socket_path and authkey_b64 and Path(socket_path).exists():
    # This condition fails, so we skip to spawning
```

### Case 3: No Facts (First Task)

**Scenario**:
- First task in playbook
- No facts stored yet

**What happens**:
1. ❌ Step 1 fails (no facts in `hostvars`)
2. ✅ Spawns new manager
3. ✅ Stores facts for subsequent tasks

## Socket Details

### Socket Type: Unix Domain Socket

- **Type**: Unix domain socket (not TCP/IP)
- **Protocol**: Local inter-process communication (IPC)
- **Path**: `/tmp/ansible_platform/manager_{hostname}.sock`
- **Format**: Filesystem path (not network address)

### Why Unix Domain Socket?

1. **Fast**: No network overhead (local IPC)
2. **Secure**: Only accessible on same machine
3. **Simple**: No port management needed
4. **Standard**: Python's `multiprocessing.managers` uses this

### Socket Lifecycle

1. **Created**: When manager process starts
   ```python
   # In manager_process.py
   manager = PlatformManager(address=socket_path, authkey=authkey)
   server = manager.get_server()
   server.serve_forever()  # Creates socket file
   ```

2. **Used**: For RPC communication
   ```python
   # In rpc_client.py
   self.manager.connect()  # Connects to socket
   ```

3. **Removed**: When manager process exits
   - Unix sockets are automatically cleaned up when process dies
   - But sometimes socket file remains (stale socket)

## Validation Decision Tree

```
┌─────────────────────────────────────────┐
│ Check hostvars for socket_path         │
└───────────────┬─────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ Facts exist?  │
        └───────┬───────┘
                │
        ┌───────┴────────┐
        │                │
       YES              NO
        │                │
        ▼                ▼
┌───────────────┐  ┌──────────────┐
│ Check socket  │  │ Spawn new    │
│ file exists   │  │ manager      │
└───────┬───────┘  └──────────────┘
        │
        ▼
┌───────────────┐
│ Socket file   │
│ exists?       │
└───────┬───────┘
        │
┌───────┴────────┐
│                │
YES              NO
│                │
▼                ▼
┌───────────────┐  ┌──────────────┐
│ Try to        │  │ Spawn new    │
│ connect       │  │ manager      │
└───────┬───────┘  └──────────────┘
        │
        ▼
┌───────────────┐
│ Connection    │
│ succeeds?     │
└───────┬───────┘
        │
┌───────┴────────┐
│                │
YES              NO
│                │
▼                ▼
┌───────────────┐  ┌──────────────┐
│ Reuse         │  │ Spawn new    │
│ existing      │  │ manager      │
│ manager       │  └──────────────┘
└───────────────┘
```

## Summary

**Validation uses 3 checks**:

1. ✅ **Facts check**: `socket_path` and `authkey_b64` in `hostvars`
2. ✅ **File check**: Socket file exists on filesystem (`Path(socket_path).exists()`)
3. ✅ **Connection check**: Can actually connect to manager (`ManagerRPCClient.connect()`)

**If all 3 pass**: Manager exists → reuse it  
**If any fail**: Manager doesn't exist → spawn new one

**Yes, it uses a Unix domain socket!** The socket file path is stored in Ansible facts, and we check if the file exists before attempting to connect.

