# Connection Plugin & Manager Process Review Guide

Critical review checklist for changes to core infrastructure: connection plugin, manager process, RPC layer, and base clients.

## When to Use

**CRITICAL: Use this guide when PR changes ANY of these files:**

### Core Infrastructure Files

```
plugins/connection/
├── http.py                           # Connection plugin (persistent vs direct routing)

plugins/plugin_utils/manager/
├── process_manager.py                # Subprocess spawning, socket management
├── platform_manager.py               # PlatformService + PlatformManager (in subprocess)
├── manager_process.py                # Subprocess entry point (main())
├── rpc_client.py                     # Client-side RPC communication

plugins/plugin_utils/platform/
├── base_client.py                    # Base API client (shared logic)
├── direct_client.py                  # Direct connection mode implementation
├── config.py                         # GatewayConfig, authentication
└── registry.py                       # Module registry, API version detection
```

**Why this matters:**
- Changes affect **ALL modules** in the collection
- Breaking changes impact **ALL users**
- Bugs here are **hard to debug** (cross-module impact)
- Security issues affect **entire authentication flow**
- Performance issues affect **all playbook runs**

---

## Critical Checks (Do These First)

### 1. Backwards Compatibility Impact

**Question:** Does this change break existing modules?

```bash
# Test ALL modules, not just one
pytest tests/unit/plugins/plugin_utils/ -v

# Run molecule tests for multiple modules
molecule test -s organization_mock
molecule test -s team_mock
molecule test -s user_mock

# Check if existing playbooks still work
ansible-playbook tests/integration/playbook.yml
```

**Checklist:**

- [ ] **No breaking changes to public APIs** (RPC protocol, config, etc.)
- [ ] **Existing modules still work** (test at least 3 different modules)
- [ ] **Both connection modes work** (persistent and direct)
- [ ] **All authentication methods work** (username/password, token, OAuth)
- [ ] **Deprecation warnings** if behavior changes

**Example breaking change:**

```python
# ❌ BREAKING: Changed RPC method signature
# BEFORE
def execute(self, operation, ansible_instance):
    pass

# AFTER
def execute(self, operation, ansible_instance, extra_param):  # Breaks all callers!
    pass

# ✅ SAFE: Added optional parameter
def execute(self, operation, ansible_instance, extra_param=None):
    pass
```

### 2. Connection Mode Verification

**Both modes must work:**

- **Persistent mode** - Manager subprocess lives across tasks
- **Direct mode** - Ephemeral, new process per task

```python
# Test both modes
# Persistent (default)
ansible-playbook test.yml  # Uses persistent connection

# Direct (fallback)
AAP_CONNECTION_MODE=direct ansible-playbook test.yml
```

**Checklist:**

- [ ] Change works in **persistent mode**
- [ ] Change works in **direct mode**
- [ ] Mode detection still works (persistent preferred, direct fallback)
- [ ] Connection manager cleanup still works
- [ ] Socket permissions correct (Unix domain socket)

### 3. Fork Safety (macOS + Python 3.12)

**Critical:** Manager subprocess must be fork-safe

```python
# ❌ DANGEROUS: HTTP session created before fork
session = requests.Session()  # Created in main process

# Later
subprocess.Popen(...)  # Fork happens
# Now session is broken on macOS + Python 3.12!

# ✅ SAFE: Create session AFTER fork in subprocess
def run_in_subprocess():
    session = requests.Session()  # Created in subprocess
```

**Why this matters:**
- Python 3.12 changed fork behavior on macOS
- HTTP sessions break across fork
- This is WHY we have a manager subprocess pattern

**Checklist:**

- [ ] No HTTP sessions/connections created before subprocess spawn
- [ ] No shared state between parent and subprocess
- [ ] Manager process creates own HTTP session
- [ ] Tested on macOS + Python 3.12 (if possible)

---

## File-Specific Checks

### plugins/connection/http.py

**Purpose:** Routes execution to persistent or direct connection mode

#### Changes to Check

**1. Connection Mode Routing**

```python
# Verify routing logic still works
def run(self, cmd, in_data=None, sudoable=True):
    # Should route to persistent or direct based on mode
    if self._use_persistent_connection():
        return self._run_persistent(cmd, in_data)
    else:
        return self._run_direct(cmd, in_data)
```

**Checklist:**

- [ ] Persistent mode detection still works
- [ ] Direct mode fallback still works
- [ ] Mode switching doesn't break mid-playbook
- [ ] Connection errors handled gracefully

**2. Error Handling**

```python
# ✅ GOOD: Graceful fallback
try:
    return self._run_persistent(cmd, in_data)
except ConnectionError as e:
    self._display.vvv(f"Persistent connection failed: {e}, falling back to direct")
    return self._run_direct(cmd, in_data)

# ❌ BAD: Crashes entire playbook
return self._run_persistent(cmd, in_data)  # No fallback!
```

**Checklist:**

- [ ] Connection errors don't crash playbook
- [ ] Falls back to direct mode on persistent failure
- [ ] Error messages are clear and actionable
- [ ] Logging at appropriate verbosity level

**3. State Management**

**Checklist:**

- [ ] No shared state between tasks (unless intended)
- [ ] Connection cleanup happens on close
- [ ] No resource leaks (sockets, file descriptors)

---

### plugins/plugin_utils/manager/process_manager.py

**Purpose:** Spawns and manages the subprocess, handles socket communication

#### Critical Areas

**1. Subprocess Spawning**

```python
@staticmethod
def spawn_manager_process(script_path, socket_path, gateway_config, ...):
    # CRITICAL: All arguments must be subprocess.Popen compatible
    cmd = [
        sys.executable,
        str(script_path),       # ✅ Must be str or Path
        socket_path,
        str(gateway_config.base_url),      # ✅ Convert vault strings
        str(gateway_config.username) if gateway_config.username else "",
        str(gateway_config.password) if gateway_config.password else "",
    ]
    
    process = subprocess.Popen(cmd, ...)
```

**Checklist:**

- [ ] **All cmd arguments are str/bytes/Path** (not custom objects)
- [ ] **Vault credentials converted to str()** (AnsibleVaultEncryptedUnicode)
- [ ] **None values handled** (convert to "" or omit)
- [ ] **No shell=True** (security risk)
- [ ] **Process cleanup on error**

**Common bugs:**

```python
# ❌ BUG: Vault credentials not converted
cmd = [sys.executable, gateway_config.password]  # TypeError if vaulted!

# ✅ FIX: Convert to string
cmd = [sys.executable, str(gateway_config.password) if gateway_config.password else ""]
```

**2. Socket Management**

```python
# Socket creation and cleanup
socket_path = "/tmp/ansible-platform-<identifier>.sock"
```

**Checklist:**

- [ ] **Socket path unique per manager** (identifier)
- [ ] **Socket removed on cleanup** (not orphaned)
- [ ] **Socket permissions secure** (0600, owner-only)
- [ ] **Socket directory exists and writable**
- [ ] **Old sockets cleaned up** (stale socket detection)
- [ ] **Socket path length < 104 chars** (Unix socket limit)

**3. Process Lifecycle**

**Checklist:**

- [ ] **Process spawned correctly**
- [ ] **Process PID tracked**
- [ ] **Process terminated on cleanup**
- [ ] **Zombie processes prevented** (wait/reap)
- [ ] **Idle timeout works** (manager exits when idle)
- [ ] **Orphan prevention** (subprocess doesn't outlive parent)

**4. Error Handling**

```python
# ✅ GOOD: Handle spawn failures
try:
    process = subprocess.Popen(cmd, ...)
except OSError as e:
    raise AnsibleConnectionFailure(f"Failed to spawn manager: {e}")
finally:
    # Cleanup resources
    if socket_path and os.path.exists(socket_path):
        os.unlink(socket_path)
```

**Checklist:**

- [ ] Spawn failures don't leave orphaned sockets
- [ ] Spawn failures don't leave zombie processes
- [ ] Clear error messages for common failures
- [ ] Resource cleanup in finally blocks

---

### plugins/plugin_utils/manager/platform_manager.py

**Purpose:** PlatformService (runs in subprocess), handles RPC requests

#### Critical Areas

**1. RPC Request Handling**

```python
class PlatformService:
    def execute(self, operation, ansible_instance, ...):
        # This runs in SUBPROCESS
        # Handles requests from action plugins
```

**Checklist:**

- [ ] **RPC protocol unchanged** (or versioned)
- [ ] **All parameters serializable** (pickle/JSON)
- [ ] **Return values serializable**
- [ ] **Exceptions properly caught and returned**
- [ ] **No blocking operations** (with timeout)

**2. HTTP Session Management**

```python
# ✅ GOOD: Session created in subprocess
class PlatformService:
    def __init__(self, gateway_config):
        self.session = self._create_session()  # Created AFTER fork
    
    def _create_session(self):
        session = requests.Session()
        session.verify = self.gateway_config.verify_ssl
        return session
```

**Checklist:**

- [ ] Session created in subprocess (not before fork)
- [ ] Session reused across requests (not recreated)
- [ ] Session properly authenticated
- [ ] SSL verification configurable
- [ ] Session cleanup on exit

**3. API Version Detection**

```python
# Detect Gateway API version
version = self._detect_api_version()
self.registry = Registry(version)
```

**Checklist:**

- [ ] Version detection still works
- [ ] Falls back gracefully if detection fails
- [ ] Works with new Gateway versions
- [ ] Cached (not detected every request)

**4. Error Handling**

**Checklist:**

- [ ] HTTP errors properly caught
- [ ] Errors serialized back to client
- [ ] Stack traces included for debugging
- [ ] No secrets in error messages

---

### plugins/plugin_utils/manager/rpc_client.py

**Purpose:** Client-side RPC communication (action plugin → manager subprocess)

#### Critical Areas

**1. Request/Response Protocol**

```python
# Send request to subprocess
request = {
    "operation": "execute",
    "ansible_instance": ansible_instance,  # Must be serializable!
}

response = self._send_request(request)
```

**Checklist:**

- [ ] **Request format unchanged** (or versioned)
- [ ] **All request data serializable**
- [ ] **Response format unchanged**
- [ ] **Timeouts implemented** (don't hang forever)
- [ ] **Large responses handled** (memory limits)

**2. Socket Communication**

**Checklist:**

- [ ] Socket connection retries (handle transient failures)
- [ ] Socket timeout configured
- [ ] Connection pooling/reuse (if applicable)
- [ ] Proper socket close on error

**3. Error Propagation**

```python
# ✅ GOOD: Preserve original error
if response.get("error"):
    raise AnsibleError(response["error"]["message"])

# ❌ BAD: Loses error context
if response.get("error"):
    raise AnsibleError("Something went wrong")
```

**Checklist:**

- [ ] Errors from subprocess properly raised
- [ ] Error context preserved (stack trace, type)
- [ ] User-friendly error messages
- [ ] No swallowed exceptions

---

### plugins/plugin_utils/platform/base_client.py & direct_client.py

**Purpose:** API client logic (HTTP requests, response handling)

#### Critical Areas

**1. HTTP Request Construction**

```python
def _make_request(self, method, path, data=None):
    url = urljoin(self.base_url, path)
    response = self.session.request(method, url, json=data)
    return response.json()
```

**Checklist:**

- [ ] **URL construction correct** (no double slashes, path joining)
- [ ] **HTTP methods handled** (GET, POST, PATCH, DELETE)
- [ ] **Request data serialization** (JSON encoding)
- [ ] **Headers set correctly** (Content-Type, Accept)
- [ ] **Authentication headers included**

**2. Response Handling**

**Checklist:**

- [ ] HTTP status codes handled (200, 201, 204, 400, 404, 500)
- [ ] JSON parsing errors handled
- [ ] Empty responses handled (204 No Content)
- [ ] Pagination handled (if applicable)
- [ ] Rate limiting handled

**3. Authentication Flow**

```python
# Authenticate with Gateway
def authenticate(self):
    if self.oauth_token:
        self.session.headers["Authorization"] = f"Bearer {self.oauth_token}"
    else:
        self.session.auth = (self.username, self.password)
```

**Checklist:**

- [ ] Username/password auth works
- [ ] OAuth token auth works
- [ ] Token refresh handled (if applicable)
- [ ] Auth failures provide clear messages
- [ ] No credentials in logs

**4. Multi-Service Support**

**Checklist:**

- [ ] Gateway endpoints work (`/api/gateway/v1/`)
- [ ] Controller endpoints work (`/api/controller/v2/`)
- [ ] EDA endpoints work (`/api/eda/v1/`)
- [ ] Hub endpoints work (`/api/hub/v3/`)
- [ ] Service routing logic correct

**5. Name → ID Lookup**

```python
def lookup_resource_id(self, resource_type, name, endpoint):
    # Critical: Used by ALL modules for reference resolution
    result = self._make_request("GET", f"{endpoint}?name={name}")
    return result["results"][0]["id"]
```

**Checklist:**

- [ ] Lookup works for all resource types
- [ ] Handles not found (404) gracefully
- [ ] Handles multiple matches (ambiguous name)
- [ ] Handles special characters in names
- [ ] Caching works (if implemented)

---

### plugins/plugin_utils/platform/registry.py

**Purpose:** Module registry, API version detection, transform mixin loading

#### Critical Areas

**1. Module Registration**

```python
# Modules auto-register on import
REGISTRY.register("organization", OrganizationTransformMixin_v1)
```

**Checklist:**

- [ ] Registration mechanism still works
- [ ] All modules still registered
- [ ] No duplicate registrations
- [ ] Registration happens before use

**2. API Version Detection**

```python
def detect_api_version(self):
    # Detect Gateway API version
    response = self.client.get("/api/gateway/")
    return response["version"]
```

**Checklist:**

- [ ] Version detection for Gateway works
- [ ] Falls back if version endpoint missing
- [ ] Caches version (not detected every time)
- [ ] Works with future versions

**3. Transform Mixin Loading**

```python
def get_mixin(self, module_name, api_version):
    # Load version-specific mixin
    return self.mixins[module_name][api_version]
```

**Checklist:**

- [ ] Loads correct mixin for API version
- [ ] Falls back if version not found
- [ ] Error message clear if module not found

---

## Testing Requirements (CRITICAL)

**Changes to connection/manager MUST have these tests:**

### 1. Unit Tests (Required)

```python
# tests/unit/plugins/plugin_utils/manager/test_<component>.py

def test_backwards_compatibility():
    """Ensure existing behavior still works."""
    # Test old code path

def test_new_functionality():
    """Test the new change."""
    # Test new code path

def test_error_handling():
    """Test error conditions."""
    # Test failures, edge cases
```

**Minimum coverage:**

- [ ] Test changed code path
- [ ] Test unchanged code path (regression)
- [ ] Test error conditions
- [ ] Test both connection modes (if applicable)
- [ ] Mock external dependencies (HTTP, subprocess)

### 2. Integration Tests (Required)

**CRITICAL: Test with MULTIPLE modules**

```yaml
# Test at least 3 different modules
- name: Test organization module
  ansible.platform.organization:
    name: "Test Org"
  register: org_result

- name: Test team module
  ansible.platform.team:
    name: "Test Team"
    organization: "Test Org"
  register: team_result

- name: Test user module
  ansible.platform.user:
    username: "testuser"
  register: user_result

# Verify all work
- assert:
    that:
      - org_result is success
      - team_result is success
      - user_result is success
```

**Why multiple modules:**
- Ensures change doesn't break specific module patterns
- Tests different transform mixin behaviors
- Catches edge cases

### 3. Connection Mode Testing

```bash
# Test persistent mode (default)
ansible-playbook tests/integration/test.yml

# Test direct mode
AAP_CONNECTION_MODE=direct ansible-playbook tests/integration/test.yml

# Both should work!
```

### 4. Vault Credentials Testing

```yaml
# Test with vaulted credentials (common pattern)
# group_vars/all.yml
aap_username: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  ...

# Should still work
```

### 5. Manual Testing Checklist

**Test these scenarios manually:**

- [ ] Fresh manager spawn (first task)
- [ ] Manager reuse (second task, same play)
- [ ] Manager cleanup (end of play)
- [ ] Connection failure recovery
- [ ] Invalid credentials handling
- [ ] Network timeout handling
- [ ] Concurrent playbook runs (multiple manager processes)

---

## Performance Considerations

### 1. Connection Overhead

**Question:** Does this change add latency?

```python
# ❌ BAD: API call for every field
for field in fields:
    lookup_id(field)  # N API calls!

# ✅ GOOD: Batch lookups
lookup_ids(fields)  # 1 API call
```

**Checklist:**

- [ ] No unnecessary API calls added
- [ ] Batching opportunities taken
- [ ] Caching used where appropriate
- [ ] No blocking operations without timeout

### 2. Memory Usage

**Checklist:**

- [ ] No memory leaks (resources freed)
- [ ] Large responses handled (streaming if needed)
- [ ] Session pool doesn't grow unbounded
- [ ] Manager subprocess memory stable

### 3. Idle Timeout

**Check idle timeout still works:**

```python
# Manager should exit after idle timeout
# Default: 30 seconds
```

**Checklist:**

- [ ] Idle timer resets on activity
- [ ] Manager exits cleanly when idle
- [ ] Socket removed on exit
- [ ] New manager spawns on next task

---

## Security Review

### 1. Credential Handling

**CRITICAL: Ensure credentials never logged/exposed**

```python
# ❌ DANGEROUS: Credentials in logs
logger.debug(f"Auth with {username}:{password}")  # LEAKED!

# ✅ SAFE: Mask credentials
logger.debug(f"Auth with {username}:***")

# ✅ SAFE: Use display.vvvv for secrets (hidden by default)
self._display.vvvv(f"Password: {password}")  # Only with -vvvv
```

**Checklist:**

- [ ] No credentials in logs (debug/info/warning)
- [ ] No credentials in error messages
- [ ] No credentials in subprocess arguments (visible in ps)
- [ ] Credentials converted from vault properly
- [ ] Credentials cleared from memory when done

### 2. Subprocess Security

**Checklist:**

- [ ] No shell=True (command injection risk)
- [ ] Arguments properly escaped
- [ ] Environment variables sanitized
- [ ] Working directory secure
- [ ] File permissions correct (sockets, temp files)

### 3. Socket Security

**Checklist:**

- [ ] Socket permissions 0600 (owner-only)
- [ ] Socket in secure directory (/tmp with unique name)
- [ ] No symlink attacks (verify socket is real)
- [ ] Socket removed on cleanup

---

## Documentation Requirements

**For connection/manager changes, update these docs:**

- [ ] `docs/03-sdk-architecture.md` - If architecture changes
- [ ] `docs/11-persistent-manager-idle-timeout.md` - If timeout logic changes
- [ ] CHANGELOG - User-visible changes
- [ ] Inline code comments - Complex logic

**Example good documentation:**

```python
def spawn_manager_process(self, ...):
    """
    Spawn manager subprocess with fork-safe HTTP session.
    
    CRITICAL: All arguments must be str/bytes/Path for subprocess.Popen.
    Vault credentials (AnsibleVaultEncryptedUnicode) must be converted
    to str() before passing, or subprocess will fail with TypeError.
    
    This method spawns the manager in a separate process to work around
    macOS + Python 3.12 fork safety issues with HTTP sessions. The
    session is created AFTER the fork, inside the subprocess.
    
    Args:
        gateway_config: May contain vaulted credentials
        ...
    
    Raises:
        AnsibleConnectionFailure: If subprocess spawn fails
    """
```

---

## Review Output Template

```markdown
## Connection/Manager Review: #<PR_NUMBER>

### Change Summary

**Files Changed:**
- `plugins/connection/http.py` - Connection mode routing
- `plugins/plugin_utils/manager/process_manager.py` - Subprocess spawning

**Change Type:** [Bugfix | Feature | Performance | Refactor]

### Critical Checks

#### Backwards Compatibility
- ✅ Tested with organization, team, user modules
- ✅ Both connection modes work (persistent, direct)
- ✅ All auth methods work (username/password, token)
- ⚠️ Deprecation warning added for old behavior

#### Fork Safety
- ✅ No HTTP session created before fork
- ✅ All resources created in subprocess
- ✅ Tested on macOS + Python 3.12 (if possible)

#### Connection Modes
- ✅ Persistent mode works
- ✅ Direct mode works
- ✅ Fallback logic intact
- ✅ Mode detection unchanged

#### Security
- ✅ No credentials in logs
- ✅ No shell=True usage
- ✅ Socket permissions correct (0600)
- ✅ Vault credentials converted to str()

### Testing

#### Unit Tests
- ✅ `tests/unit/plugins/plugin_utils/manager/test_process_manager.py` - Added
- ✅ Test coverage: 95% of changed code
- ✅ Tests both old and new behavior

#### Integration Tests
- ✅ Tested with 3+ modules (organization, team, user)
- ✅ Both connection modes tested
- ✅ Vault credentials tested
- ✅ All tests passing

#### Manual Testing
- ✅ Fresh manager spawn works
- ✅ Manager reuse works
- ✅ Idle timeout still works
- ✅ Connection failure recovery works

### Performance
- ✅ No additional API calls
- ✅ No memory leaks detected
- ✅ Manager subprocess memory stable

### Documentation
- ✅ Inline comments added for complex logic
- ⚠️ Consider updating `docs/03-sdk-architecture.md`
- ✅ Changelog fragment present

### Blockers

None

### Recommendations

1. ✅ All critical checks passed
2. ⚠️ Consider adding example to architecture docs
3. 💡 Monitor manager subprocess memory in production

### Verdict

✅ **APPROVE** - Ready for `safe to test`

Well-tested change with comprehensive coverage. Backwards compatible, fork-safe, and maintains security guarantees.

**Extra validation:** Will monitor first few integration test runs closely.
```

---

## Red Flags (Request Changes If Found)

**Immediate blockers:**

- ❌ Breaking change without deprecation
- ❌ Not tested with multiple modules
- ❌ Credentials logged or exposed
- ❌ shell=True usage
- ❌ HTTP session created before fork
- ❌ No error handling for subprocess spawn
- ❌ Socket cleanup missing
- ❌ Both connection modes not tested

**Request changes with explanation:**

- ⚠️ Complex logic without comments
- ⚠️ Performance regression (more API calls)
- ⚠️ Missing unit tests for critical path
- ⚠️ Unclear error messages
- ⚠️ Documentation not updated

---

**Last Updated:** 2026-09-11
