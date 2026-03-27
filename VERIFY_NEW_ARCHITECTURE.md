# Verifying the New Architecture is Running

## Current Status

The new architecture code (BaseResourceActionPlugin, PlatformManager, etc.) has been added, but it's not yet fully implemented for existing modules. The playbook is currently using the **old/legacy module implementation**.

## How to Tell Which Code is Running

### Signs of OLD architecture:
```
Including module_utils file .../aap_module.py
Including module_utils file .../aap_user.py
Including module_utils file .../aap_object.py
```
- ❌ No persistent connection
- ❌ Each task creates a new HTTP session
- ❌ No manager process

### Signs of NEW architecture:
```
Including module_utils file .../platform_manager.py
Including module_utils file .../rpc_client.py
Including module_utils file .../base_transform.py
```
- ✅ Persistent connection manager
- ✅ HTTP session reused across tasks
- ✅ Manager process running in background

## Step 1: Run with Increased Verbosity

Run your playbook with `-vvv` to see debug output:

```bash
cd /Users/rohit/dev-workspace/ansible-dev/ansible_collections/ansible/platform

ansible-playbook user.yml -vvv
```

You should now see:
```
🚀 NEW ARCHITECTURE: User action plugin is running!
✅ Manager socket exists: /tmp/aap_platform_manager.sock
(or)
❌ Manager socket not found: /tmp/aap_platform_manager.sock
   Manager will be spawned on first use
```

## Step 2: Check for Action Plugin

Look for this in the output:
```
Loading action plugin user from ...
```

If you see the action plugin loading, the NEW architecture entry point is being used!

## Step 3: Check for Manager Process

While the playbook is running (or after), check for the manager process:

```bash
# Check for manager socket
ls -la /tmp/aap_platform_manager.sock

# Check for manager process
ps aux | grep platform_manager

# Check for any Python processes related to the manager
ps aux | grep python | grep manager
```

## Step 4: Full Implementation

The action plugin I just created is a **debug wrapper** that:
1. Shows it's being invoked (proves action plugin works)
2. Checks for manager socket
3. Delegates to old module (so your playbook still works)

For FULL new architecture, you would need:

### Required Files:
1. ✅ `plugins/action/user.py` - Action plugin (debug version created)
2. ❌ `plugins/plugin_utils/docs/user.py` - DOCUMENTATION
3. ❌ `plugins/plugin_utils/ansible_models/user.py` - Ansible dataclass
4. ❌ `plugins/plugin_utils/api/v1/user.py` - Transform mixin
5. ✅ `plugins/plugin_utils/platform/base_transform.py` - Base class (exists)
6. ✅ `plugins/plugin_utils/manager/platform_manager.py` - Manager (exists)

### To see the difference:

**Before (OLD - no action plugin):**
```bash
ansible-playbook user.yml -vvv 2>&1 | grep -i "including module_utils"
```
You'll see: `aap_module.py`, `aap_user.py`, `aap_object.py`

**After (NEW - with action plugin):**
```bash
ansible-playbook user.yml -vvv 2>&1 | grep -i "action plugin"
```
You'll see: `Loading action plugin user from ...`

## Example: Run Now

```bash
cd /Users/rohit/dev-workspace/ansible-dev/ansible_collections/ansible/platform

# Run with debug output
ansible-playbook user.yml -vvv 2>&1 | grep -E "(🚀|✅|❌|action plugin)"

# OR save full output
ansible-playbook user.yml -vvv > /tmp/ansible_run.log 2>&1
less /tmp/ansible_run.log
```

## What You'll See

### With the debug action plugin (current state):
```
TASK [Ensure user demo3 exists]
🚀 NEW ARCHITECTURE: User action plugin is running!
❌ Manager socket not found: /tmp/aap_platform_manager.sock
   Manager will be spawned on first use
Delegating to legacy module implementation...
[... old module runs ...]
✅ Action plugin completed
```

### With full implementation (future):
```
TASK [Ensure user demo3 exists]
🚀 Spawning platform manager...
✅ Manager ready at /tmp/aap_platform_manager.sock
📤 Sending user data to manager via RPC
📥 Received result from manager
✅ User created successfully
```

## Performance Comparison

Run this to see if there's a speed difference:

```bash
# Old architecture (bypass action plugin)
time ansible-playbook user.yml

# With action plugin (but still using old code internally)
time ansible-playbook user.yml -vvv
```

When fully implemented, the new architecture should be 50-75% faster on multi-task playbooks due to connection reuse.

