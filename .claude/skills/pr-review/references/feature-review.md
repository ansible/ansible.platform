# Feature PR Review Guide

Detailed checklist for reviewing feature PRs (new modules, new functionality).

## When to Use

- PR adds a new module
- PR adds new functionality to existing module
- PR refactors code significantly
- PR title starts with `feat:` or `feature:`

---

## ⚠️ CRITICAL: Check for Core Infrastructure Changes

**Before proceeding, check if PR changes connection/manager files:**

```bash
git diff origin/devel --name-only | grep -E \
  'plugins/connection/|plugins/plugin_utils/manager/|plugins/plugin_utils/platform/(base_client|direct_client|config|registry)'
```

**If ANY match found:**
→ **STOP:** Read `connection-manager-review.md` FIRST before continuing with this checklist

**Why:** Connection/manager changes affect ALL modules. They require extra scrutiny for:
- Backwards compatibility
- Fork safety (macOS + Python 3.12)
- Both connection modes (persistent vs direct)
- Security (credential handling, subprocess spawning)

---

## Seven-File Pattern Validation

**For new modules, verify all required files are present:**

| # | File | Required? | What to Check |
|---|------|-----------|---------------|
| 1 | `plugins/modules/<resource>.py` | ✅ Always | Module stub with DOCUMENTATION + EXAMPLES |
| 2 | `plugins/action/<resource>.py` | ✅ Always | ActionModule class (Pattern A/B/C) |
| 3 | `plugins/plugin_utils/ansible_models/<resource>.py` | ✅ Always | AnsibleFoo dataclass with stable fields |
| 4 | `plugins/plugin_utils/api/v1/<resource>.py` | ✅ Always | APIFoo_v1 + transform mixin |
| 5 | `tests/unit/` | ✅ Always | pytest tests for transform logic |
| 6 | `extensions/molecule/<resource>_mock/` | ✅ Recommended | Mock server tests |
| 7 | `tests/integration/targets/<resource>s_test/` | ⚠️ Can defer | Live AAP tests (can add later) |

**Commands to verify:**

```bash
# Check module stub
test -f plugins/modules/<resource>.py && echo "✅ Module stub" || echo "❌ Missing"

# Check action plugin
test -f plugins/action/<resource>.py && echo "✅ Action plugin" || echo "❌ Missing"

# Check Ansible model
test -f plugins/plugin_utils/ansible_models/<resource>.py && echo "✅ Ansible model" || echo "❌ Missing"

# Check API model + mixin
test -f plugins/plugin_utils/api/v1/<resource>.py && echo "✅ API model" || echo "❌ Missing"

# Check unit tests
find tests/unit -name "*<resource>*" -type f | head -1

# Check molecule tests
test -d extensions/molecule/<resource>_mock && echo "✅ Molecule tests" || echo "⚠️ Missing"

# Check integration tests
test -d tests/integration/targets/<resource>s_test && echo "✅ Integration" || echo "⚠️ Can add later"
```

---

## Architecture Compliance

### 1. Ansible Model Review

**File:** `plugins/plugin_utils/ansible_models/<resource>.py`

**Checklist:**

- [ ] Uses `@dataclass` decorator
- [ ] Class name is `Ansible<Resource>` (PascalCase)
- [ ] Required fields first, optional fields with defaults after
- [ ] Reference fields use **string names**, NOT integer IDs
- [ ] Read-only fields (id, created, modified, url) marked Optional
- [ ] `state` field defaults to `"present"`
- [ ] No API-specific fields (those belong in API model)

**Example validation:**

```python
@dataclass
class AnsibleFoo:
    # ✅ CORRECT: String names for references
    name: str
    organization: str  # ✅ String, not int
    
    # ✅ CORRECT: Optional fields with defaults
    description: Optional[str] = None
    state: str = "present"
    
    # ✅ CORRECT: Read-only fields
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
```

**Common mistakes:**

```python
# ❌ WRONG: Using integer IDs in Ansible model
organization: int  # Should be: organization: str

# ❌ WRONG: API-specific fields
organization_id: int  # This belongs in API model only

# ❌ WRONG: Required field after optional
name: str  # ✅ OK
description: Optional[str] = None  # ✅ OK
organization: str  # ❌ WRONG - required after optional
```

---

### 2. API Model Review

**File:** `plugins/plugin_utils/api/v1/<resource>.py`

**Checklist:**

- [ ] Uses `@dataclass` decorator
- [ ] Class name is `API<Resource>_v1`
- [ ] All fields are Optional (API model is wire format)
- [ ] Reference fields use **integer IDs**
- [ ] Matches Gateway/Controller/EDA/Hub API response structure
- [ ] Read-only fields included

**Example validation:**

```python
@dataclass
class APIFoo_v1:
    # ✅ CORRECT: All fields Optional
    name: Optional[str] = None
    
    # ✅ CORRECT: Integer IDs for references
    organization: Optional[int] = None  # ID, not name
    
    # ✅ CORRECT: Optional fields
    description: Optional[str] = None
    
    # ✅ CORRECT: Read-only fields included
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
```

**Common mistakes:**

```python
# ❌ WRONG: Using string names in API model
organization: str  # Should be: organization: Optional[int] = None

# ❌ WRONG: Required fields (all should be Optional)
name: str  # Should be: name: Optional[str] = None
```

---

### 3. Transform Mixin Review

**File:** `plugins/plugin_utils/api/v1/<resource>.py` (same file as API model)

**Critical checks:**

#### 3.1 Endpoint Path Declaration

```python
def get_endpoint_operations(self):
    return EndpointOperation(
        path="/api/<service>/<version>/<resource>s/",  # ← CHECK THIS
        list_path="/api/<service>/<version>/<resource>s/",
        detail_path="/api/<service>/<version>/<resource>s/{id}/",
        lookup_field="name",
    )
```

**Verify correct service prefix:**

| Service | Correct Prefix | Example |
|---------|---------------|---------|
| Gateway | `/api/gateway/v1/` | `/api/gateway/v1/teams/` |
| Controller | `/api/controller/v2/` | `/api/controller/v2/ad_hoc_commands/` |
| EDA | `/api/eda/v1/` | `/api/eda/v1/projects/` |
| Hub | `/api/hub/v3/` | `/api/hub/v3/namespaces/` |

**Common mistake:**
```python
# ❌ WRONG: EDA resource with Gateway prefix
path="/api/gateway/v1/projects/"  # Should be: /api/eda/v1/projects/
```

#### 3.2 Name → ID Resolution

**For reference fields, verify resolution logic:**

```python
@classmethod
def from_ansible_data(cls, ansible_instance, context):
    api_data = {}
    
    # ✅ CORRECT: Resolve organization name → ID
    if ansible_instance.organization:
        org_id = context.manager.lookup_resource_id(
            "organization",  # Resource type
            ansible_instance.organization,  # Name
            endpoint="/api/gateway/v1/organizations/"  # Lookup endpoint
        )
        api_data["organization"] = org_id
    
    # ✅ CORRECT: Pass through non-reference fields
    if ansible_instance.name:
        api_data["name"] = ansible_instance.name
    
    return APIFoo_v1(**api_data)
```

**Checklist:**

- [ ] All reference fields (org, team, credential, etc.) use `lookup_resource_id()`
- [ ] Correct resource type passed to lookup
- [ ] Correct endpoint path for lookup
- [ ] Non-reference fields pass through directly
- [ ] Write-only fields (passwords) excluded from read-back

#### 3.3 Reverse Transform (from_api)

```python
@classmethod
def from_api(cls, api_data, context):
    # ✅ CORRECT: Map API data back to Ansible model
    return AnsibleFoo(
        id=api_data.get("id"),
        name=api_data.get("name"),
        organization=api_data.get("organization"),  # ID in API, name in Ansible
        description=api_data.get("description"),
    )
```

**Common mistake:**
```python
# ❌ WRONG: Forgetting to map field in reverse transform
# If you add opa_query_path to from_ansible_data() but forget from_api(),
# idempotency breaks (second run always shows changed=true)
```

---

### 4. Module Documentation Review

**File:** `plugins/modules/<resource>.py`

**Checklist:**

- [ ] `DOCUMENTATION` block present and valid YAML
- [ ] `module: <name>` matches filename
- [ ] `short_description` clear and concise
- [ ] All parameters documented with:
  - [ ] `description`
  - [ ] `type`
  - [ ] `required` or `default`
- [ ] `extends_documentation_fragment: ansible.platform.auth` present
- [ ] `EXAMPLES` block shows realistic use cases
- [ ] `RETURN` block documents all returned values
- [ ] `version_added` set correctly

**Validation command:**

```bash
# Check DOCUMENTATION is valid YAML
python3 -c "
import yaml
with open('plugins/modules/<resource>.py') as f:
    content = f.read()
    doc_start = content.find('DOCUMENTATION = \"\"\"') + len('DOCUMENTATION = \"\"\"')
    doc_end = content.find('\"\"\"', doc_start)
    yaml.safe_load(content[doc_start:doc_end])
print('✅ DOCUMENTATION valid')
"
```

**Common issues:**

```yaml
# ❌ WRONG: Missing type
organization:
  description: The organization name
  # Missing: type: str

# ❌ WRONG: Missing extends_documentation_fragment
# Should have:
extends_documentation_fragment:
  - ansible.platform.auth

# ❌ WRONG: Vague description
name:
  description: The name
  # Should be: "The unique name of the foo resource."
```

---

### 5. Test Coverage Review

#### 5.1 Unit Tests

**Location:** `tests/unit/plugins/plugin_utils/api/v1/test_<resource>.py`

**Required tests:**

```python
def test_from_ansible_data_basic():
    """Test basic field mapping."""
    ansible_foo = AnsibleFoo(name="test", organization="Red Hat")
    # ... verify transformation

def test_from_ansible_data_with_optional_fields():
    """Test optional fields handled correctly."""
    # ... test with and without optional fields

def test_from_ansible_data_resolves_organization():
    """Test that organization name resolves to ID."""
    # Mock lookup_resource_id
    # Verify it's called correctly
    # Verify ID is in API data

def test_from_api_maps_all_fields():
    """Test reverse transformation."""
    api_data = {"id": 1, "name": "test", "organization": 42}
    # Verify all fields mapped back

def test_endpoint_operations_returns_correct_path():
    """Test endpoint path is correct."""
    # Verify service prefix correct
```

**Checklist:**

- [ ] Tests cover `from_ansible_data()` transformation
- [ ] Tests cover `from_api()` reverse transformation
- [ ] Tests cover name→ID resolution for reference fields
- [ ] Tests cover optional field handling (None values)
- [ ] Tests verify endpoint path is correct
- [ ] All tests pass: `pytest tests/unit -v -k <resource>`

#### 5.2 Molecule Tests

**Location:** `extensions/molecule/<resource>_mock/converge.yml`

**Required scenarios:**

```yaml
# 1. Create (state: present)
- name: Create foo
  ansible.platform.foo:
    name: "Test Foo"
    organization: "Test Org"
    state: present
  register: result

- name: Verify created
  assert:
    that:
      - result.changed
      - result.id is defined

# 2. Idempotency (run again, no change)
- name: Create foo again (idempotent)
  ansible.platform.foo:
    name: "Test Foo"
    organization: "Test Org"
    state: present
  register: result

- name: Verify no change
  assert:
    that:
      - not result.changed

# 3. Update (modify field)
- name: Update foo description
  ansible.platform.foo:
    name: "Test Foo"
    description: "Updated"
    state: present
  register: result

- name: Verify updated
  assert:
    that:
      - result.changed
      - result.description == "Updated"

# 4. Delete (state: absent)
- name: Delete foo
  ansible.platform.foo:
    name: "Test Foo"
    state: absent
  register: result

- name: Verify deleted
  assert:
    that:
      - result.changed
```

**Checklist:**

- [ ] Create scenario present
- [ ] Idempotency test present (run twice, second returns changed: false)
- [ ] Update scenario present
- [ ] Delete scenario present
- [ ] Mock server handles all endpoints (check `mock/prepare.yml`)
- [ ] Tests pass: `molecule test -s <resource>_mock`

#### 5.3 Integration Tests (Can Defer)

**Location:** `tests/integration/targets/<resource>s_test/`

**Note:** Can be added later, not required for initial merge if Molecule tests are comprehensive.

**If present, verify:**

```
tests/integration/targets/<resource>s_test/
├── tasks/
│   └── main.yml          # Test playbook
├── aliases              # CI target groups
└── meta/
    └── main.yml         # Test dependencies
```

---

## meta/runtime.yml Registration

**Must be updated for new modules:**

```yaml
# meta/runtime.yml
action_groups:
  gateway:
    - ad_hoc_command
    - application
    - <new_module>  # ← ADD THIS
```

**Validation:**

```bash
# Check if module is in runtime.yml
grep "<module_name>" meta/runtime.yml || echo "❌ Missing from runtime.yml"
```

---

## Action Plugin Pattern Detection

**File:** `plugins/action/<resource>.py`

**Three patterns:**

### Pattern A: Declarative (Simplest)

```python
class ActionModule(ActionPlatformGenericResource):
    module_name = "foo"
    ansible_model_class = AnsibleFoo
```

**Only 3 lines. Use when:**
- Standard CRUD operations only
- No custom logic needed
- Fields map 1:1 to API

**Example:** `organization.py`

### Pattern B: Hook-Based

```python
class ActionModule(ActionPlatformGenericResource):
    module_name = "foo"
    ansible_model_class = AnsibleFoo
    
    def _pre_create(self, ansible_instance, api_instance):
        # Custom logic before create
        pass
    
    def _post_update(self, result, ansible_instance):
        # Custom logic after update
        pass
```

**Use when:**
- Need side effects (create related resources)
- Need validation beyond API
- Need to modify result

### Pattern C: Fully Custom

```python
class ActionModule(ActionPlatformGenericResource):
    def execute(self, ansible_instance):
        # Completely custom implementation
        pass
```

**Use when:**
- Non-standard workflow (e.g., launch and wait)
- Multiple endpoint orchestration
- Write-only fields need special handling

**Example:** `user.py` (has password write-only field)

**Review checklist:**

- [ ] Pattern choice is appropriate for complexity
- [ ] If Pattern C, justify why A/B won't work
- [ ] Custom logic is tested

---

## Multi-Endpoint Pattern

**When needed:** Resource uses different endpoints for different operations.

**Example:** `opa_query_path` field only on Controller API, not Gateway API

```python
def get_endpoint_operations(self):
    # Route based on which fields are present
    if self.opa_query_path is not None:
        # Use Controller API when opa_query_path present
        return EndpointOperation(
            path="/api/controller/v2/organizations/",
            lookup_field="name",
        )
    
    # Default: Gateway API
    return EndpointOperation(
        path="/api/gateway/v1/organizations/",
        lookup_field="name",
    )
```

**Review checklist:**

- [ ] Routing logic is clear and documented
- [ ] Both endpoints return compatible data
- [ ] Tests cover both code paths

---

## Documentation Updates

**Check if these need updating:**

- [ ] `docs/07-adding-resources.md` - If new pattern introduced
- [ ] `docs/10-case-study-aap-platform.md` - If new resource category
- [ ] README examples - If user-facing feature

---

## CasC Team Notification

**Notify CasC team if PR affects:**

- Return value structure changes
- New module (they may need to add support)
- Authentication parameter changes
- Breaking changes to existing modules

**How to notify:**

```bash
# Add comment to PR
gh pr comment <PR_NUMBER> --repo ansible/ansible.platform \
  --body "@ansible/casc-team FYI - this PR adds a new module: <module_name>"
```

**Or add label:**
```bash
gh pr edit <PR_NUMBER> --repo ansible/ansible.platform --add-label "casc-review-needed"
```

---

## Review Output Template

```markdown
## Feature Review: #<PR_NUMBER>

### Seven-File Pattern

| File | Status | Notes |
|------|--------|-------|
| Module stub | ✅ | Complete |
| Action plugin | ✅ | Pattern A (appropriate) |
| Ansible model | ✅ | Uses string names |
| API model | ✅ | Uses integer IDs |
| Transform mixin | ✅ | Correct endpoint path |
| Unit tests | ✅ | 95% coverage |
| Molecule tests | ✅ | All scenarios covered |
| Integration tests | ⚠️ | Can add later |

### Architecture Compliance

- ✅ Ansible Model uses string names for references
- ✅ API Model uses integer IDs
- ✅ Transform mixin resolves names → IDs correctly
- ✅ Endpoint path has correct service prefix: `/api/gateway/v1/`
- ✅ meta/runtime.yml updated

### Test Coverage

- ✅ Unit tests: 12 tests, all passing
- ✅ Molecule tests: Create, update, delete, idempotency - all passing
- ⚠️ Integration tests: Can add later (molecule tests are comprehensive)

### Documentation

- ✅ DOCUMENTATION complete and valid
- ✅ EXAMPLES show realistic use cases
- ✅ RETURN values documented
- ✅ Changelog fragment present

### Blockers

None

### Recommendations

1. Consider adding integration tests in follow-up PR
2. CasC team notification recommended (new module)

### Verdict

✅ **APPROVE** - Ready for `safe to test` label

All pre-merge checks passed. Architecture compliant. Comprehensive test coverage.
```

---

**Last Updated:** 2026-09-11
