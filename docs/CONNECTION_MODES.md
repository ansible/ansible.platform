# Connection Modes Guide

## Overview

The `ansible.platform` collection supports two connection modes, both using the same unified architecture:

1. **Direct Mode** (default): Ephemeral manager processes, one per task
2. **Persistent Mode** (opt-in): Long-lived manager process, reused across tasks

Both modes use the same architecture:
- Manager processes (separate from action plugin workers)
- TransitMixin for transformations
- API version detection
- Ansible dataclasses
- Shared error handling, credential management, and CRUD operations

## Why Manager Processes?

**Problem**: Action plugins run in Ansible worker processes, which cannot safely make direct HTTP requests. Attempting to use `requests` or Ansible's `Request` class in action plugins causes worker crashes.

**Solution**: Both modes spawn separate manager processes that handle all HTTP communication. This ensures:
- ✅ No worker crashes
- ✅ Safe HTTP requests
- ✅ Unified architecture for both modes

## Direct Mode (Default)

### Characteristics

- **Manager Lifecycle**: Spawned per task, shut down immediately after task completes
- **HTTP Sessions**: New session per task
- **Performance**: Slight overhead from spawning manager per task (~2-3 seconds per task)
- **Simplicity**: No state management, no facts to track
- **Use Case**: Default mode, suitable for most use cases

### Configuration

```yaml
- hosts: localhost
  connection: ansible.platform.http
  # persistent defaults to false, so this is direct mode
  tasks:
    - ansible.platform.user:
        username: demo
```

### How It Works

```
Task 1:
  └─> Spawn ephemeral manager process
      └─> Execute task via RPC
          └─> Shut down manager

Task 2:
  └─> Spawn new ephemeral manager process
      └─> Execute task via RPC
          └─> Shut down manager
```

### Socket Path

Direct mode uses short socket paths to avoid Unix domain socket length limits:
- Location: `/tmp/ap/manager_<uid>_e<hash>_<cred_hash>.sock`
- `e` prefix indicates ephemeral
- Hash ensures uniqueness

## Persistent Mode

### Characteristics

- **Manager Lifecycle**: Spawned on first task, reused across all tasks in play, shut down when play completes
- **HTTP Sessions**: Reused session across tasks (better performance)
- **Performance**: Manager spawn overhead only on first task (~2-3 seconds), subsequent tasks are faster
- **State Management**: Facts stored to enable manager reuse
- **Use Case**: When running multiple tasks in a play, persistent mode provides better performance

### Configuration

**Via Variable:**
```yaml
- hosts: localhost
  connection: ansible.platform.http
  vars:
    ansible_platform_persistent: true
  tasks:
    - ansible.platform.user:
        username: demo1
    - ansible.platform.user:
        username: demo2
```

**Via Connection Option:**
```yaml
- hosts: localhost
  connection: ansible.platform.http
  connection_options:
    persistent: true
  tasks:
    - ansible.platform.user:
        username: demo1
    - ansible.platform.user:
        username: demo2
```

**Via Inventory:**
```ini
[platform_hosts]
localhost ansible_connection=ansible.platform.http ansible_platform_persistent=true
```

### How It Works

```
Task 1:
  └─> Check for existing manager in facts
      └─> Not found: Spawn manager, store facts
          └─> Execute task via RPC

Task 2:
  └─> Check for existing manager in facts
      └─> Found: Reuse manager (no spawn overhead)
          └─> Execute task via RPC

Play Complete:
  └─> Shut down persistent manager
```

### Facts Stored

Persistent mode stores the following facts to enable manager reuse:
- `platform_manager_socket`: Socket path to manager
- `platform_manager_authkey`: Base64-encoded authkey for authentication

These facts are stored per host and persist for the duration of the play.

## Performance Comparison

### Direct Mode

```
Task 1: ~2.9s (includes manager spawn: ~2s)
Task 2: ~2.7s (includes manager spawn: ~2s)
Total:  ~5.6s
```

### Persistent Mode

```
Task 1: ~2.9s (includes manager spawn: ~2s)
Task 2: ~0.8s (reuses manager, no spawn overhead)
Total:  ~3.7s (saves ~1.9s)
```

**Note**: Performance numbers are approximate and depend on network latency, API response times, and system load.

## When to Use Each Mode

### Use Direct Mode When:
- ✅ Running single tasks
- ✅ Tasks are independent
- ✅ Simplicity is preferred
- ✅ No performance concerns
- ✅ Default behavior (no configuration needed)

### Use Persistent Mode When:
- ✅ Running multiple tasks in a play
- ✅ Performance is important
- ✅ Tasks benefit from session reuse
- ✅ You want to minimize manager spawn overhead

## Architecture Details

### Unified Architecture

Both modes use the same components:

1. **Connection Plugin** (`plugins/connection/http.py`)
   - Dispatcher: Routes to persistent or direct mode
   - `get_client()` method returns appropriate client

2. **Manager Process** (`plugins/plugin_utils/manager/manager_process.py`)
   - Separate process handling HTTP requests
   - Uses `requests.Session` for HTTP communication
   - Implements TransitMixin for transformations
   - Handles API version detection

3. **RPC Client** (`plugins/plugin_utils/manager/rpc_client.py`)
   - Client-side RPC communication
   - Connects to manager via Unix domain socket
   - Handles authentication and error handling

4. **Shared Layers**
   - TransitMixin: Ansible ↔ API transformations
   - API Version Detection: Automatic version discovery
   - Error Handling: Comprehensive error taxonomy
   - Credential Management: Secure credential storage
   - CRUD Operations: Standardized CRUD interface

### Lifecycle Management

**Direct Mode:**
- Manager spawned in `_get_direct_client()`
- Manager shut down in `cleanup()` after task completes
- No facts stored

**Persistent Mode:**
- Manager spawned in `_get_persistent_client()` if not found in facts
- Manager reused if found in facts
- Manager shut down in `cleanup()` when all tasks in play complete
- Facts stored to enable reuse

## Troubleshooting

### Manager Spawn Failures

If manager processes fail to spawn:
1. Check socket directory permissions: `/tmp/ap/` should be writable
2. Check for socket path length issues (Unix domain socket limit ~104 chars)
3. Check manager error logs: `/tmp/ap/manager_error_<identifier>.log`

### Manager Connection Failures

If RPC connections fail:
1. Verify manager process is running: `ps aux | grep manager_process`
2. Check socket file exists: `ls -la /tmp/ap/manager_*.sock`
3. Verify authkey matches (stored in facts for persistent mode)

### Performance Issues

If performance is slower than expected:
1. Use persistent mode for multiple tasks
2. Check network latency to gateway
3. Monitor manager process CPU/memory usage
4. Review API response times

## Migration from Old Architecture

If you were using the old architecture with `DirectHTTPClient`:

**Old (No longer supported):**
```python
# DirectHTTPClient used Ansible's Request class
# This caused worker crashes in action plugins
```

**New (Current):**
```python
# Both modes use manager processes
# Direct mode: Ephemeral managers
# Persistent mode: Long-lived managers
```

The new architecture ensures no worker crashes while maintaining the same functionality.

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Complete system architecture
- [CONNECTION_PLUGIN_FINAL_IMPLEMENTATION.md](CONNECTION_PLUGIN_FINAL_IMPLEMENTATION.md) - Connection plugin implementation
- [PLAYBOOK_MIGRATION.md](PLAYBOOK_MIGRATION.md) - Migration guide
