# Feature PR Review Guide

Concise checklist for feature PRs. See `common-patterns.md` for examples and `docs/07-adding-resources.md` for architecture details.

## When to Use

PR type: `feat:`, `feature:`, or `refactor:`

**FIRST: Read `common-patterns.md` for:**
- Code example references (points to real files)
- Common validation commands
- Standard blocker checklist
- Anti-patterns to flag

---

## ⚠️ CRITICAL: Check Core Infrastructure

**Detection:**
```bash
git diff origin/devel --name-only | grep -E 'plugins/connection/|plugins/plugin_utils/manager/'
```

**If matches → STOP:** Read `connection-manager-review.md` FIRST

---

## Seven-File Pattern (STRICT)

**Required files for new modules:**

| File | Required? | Check |
|------|-----------|-------|
| `plugins/modules/<resource>.py` | ✅ | DOCUMENTATION + EXAMPLES |
| `plugins/action/<resource>.py` | ✅ | ActionModule class |
| `plugins/plugin_utils/ansible_models/<resource>.py` | ✅ | Ansible dataclass |
| `plugins/plugin_utils/api/v1/<resource>.py` | ✅ | API model + mixin |
| `tests/integration/` | ✅ | Integration tests (scaffold generated) |
| `extensions/molecule/` | ⚠️ Recommended | Molecule mock scenario |
| `tests/unit/` tests | ⚠️ Optional | Unit tests (only if complex transforms) |

**Validation:** See `common-patterns.md` for detection commands

---

## Architecture Compliance

**Reference real examples instead of inline code:**
- Ansible model: `plugins/plugin_utils/ansible_models/application.py`
- API model: `plugins/plugin_utils/api/v1/application.py`
- Action plugin: `plugins/action/application.py`
- Architecture docs: `docs/04-data-model-transformation.md`

### 1. Ansible Model Checklist

**File:** `plugins/plugin_utils/ansible_models/<resource>.py`

- [ ] @dataclass decorator
- [ ] Class name: `Ansible<Resource>`
- [ ] **Reference fields use STRING NAMES** (not IDs) ← CRITICAL
- [ ] Required fields before optional fields
- [ ] Read-only fields (id, created, url) marked Optional
- [ ] No API-specific fields (organization_id, etc.)

**Common mistakes:** See `common-patterns.md` anti-patterns section

### 2. API Model Checklist

**File:** `plugins/plugin_utils/api/v1/<resource>.py`

- [ ] @dataclass decorator
- [ ] Class name: `API<Resource>_v1`
- [ ] **All fields Optional**
- [ ] **Reference fields use INTEGER IDs** (not names)
- [ ] Matches actual API response structure

**Verify:** Compare against live API response from AAP

### 3. Transform Mixin Checklist

**File:** `plugins/plugin_utils/api/v1/<resource>.py`

**Reference example:** `plugins/plugin_utils/api/v1/application.py`

- [ ] `get_endpoint_operations()` returns EndpointOperation
- [ ] Endpoint path has correct service prefix:
  - Gateway: `/api/gateway/v1/`
  - Controller: `/api/controller/v2/`
  - EDA: `/api/eda/v1/`
  - Hub: `/api/hub/v3/`
- [ ] `lookup_field` set correctly (usually "name")
- [ ] `from_ansible_data()` method resolves name→ID for references
- [ ] `from_api()` method resolves ID→name for references
- [ ] Both transformations are idempotent

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
            "organizations",  # Endpoint
            "name",  # Lookup field
            ansible_instance.organization  # Lookup value
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
    # ⚠️  NOTE: from_api receives data as-is from API
    # For FK fields, API returns IDs. Ansible models should store these as IDs during from_api,
    # and resolve names during to_api. Reverse lookup is not typically performed.
    
    return AnsibleFoo(
        id=api_data.get("id"),
        name=api_data.get("name"),
        organization=org_name,  # Resolved from ID → name
        description=api_data.get("description"),
    )
```

**Common mistakes:**
```python
# ❌ WRONG: Assigning ID directly when Ansible expects name
organization=api_data.get("organization")  # Breaks idempotency!
# API returns integer ID (1234), but Ansible expects string name ("Default")
# Next run tries to update 1234 → "Default" → changed=true every time

# ❌ WRONG: Forgetting to map field in reverse transform
# If you add opa_query_path to from_ansible_data() but forget from_api(),
# idempotency breaks (second run always shows changed=true)
```

---

### 4. Module Documentation

**File:** `plugins/modules/<resource>.py`

**Reference example:** `plugins/modules/application.py`

- [ ] DOCUMENTATION block valid YAML
- [ ] module name matches filename
- [ ] All parameters have: description, type, required/default
- [ ] `extends_documentation_fragment: ansible.platform.auth`
- [ ] EXAMPLES block shows realistic use
- [ ] RETURN block documents returned values

**Validation:** `ansible-test sanity --docker` (catches doc issues)

---

### 5. Test Coverage (STRICT)

#### Unit Tests (BLOCKING)

**Reference example:** `tests/unit/plugins/plugin_utils/api/v1/test_application.py`

**Required coverage:**
- [ ] from_ansible_data() - name→ID resolution
- [ ] from_api() - ID→name resolution  
- [ ] Optional field handling
- [ ] Endpoint path verification
- [ ] **All tests passing** ← BLOCKING

**Run:** `pytest tests/unit -v -k <resource>`

#### Molecule Tests (Recommended)

**Reference example:** `extensions/molecule/application_mock/`

**Required scenarios:**
1. Create (state: present)
2. Idempotency (no change on re-run)
3. Update (modify field)
4. Delete (state: absent)
  register: result

**Checklist:**
- [ ] Tests pass: `molecule test -s <resource>_mock`

#### Integration Tests (Optional - Can Defer)

**Location:** `tests/integration/targets/<resource>s_test/`
Can be added in follow-up PR if molecule tests are comprehensive.

---

## meta/runtime.yml Registration (BLOCKING)

**New modules MUST be registered:**

Check: `grep "<module_name>" meta/runtime.yml`

If missing → Add to appropriate action_group (gateway/controller/eda/hub)

**This is checked by "collection completeness" test**

---

## Action Plugin Pattern

**File:** `plugins/action/<resource>.py`

**Reference examples:**
- Pattern A (Simple): `plugins/action/organization.py`
- Pattern B (Hooks): `plugins/action/application.py`
- Pattern C (Custom): `plugins/action/credential.py`

**Checklist:**
- [ ] Inherits from BaseResourceActionPlugin
- [ ] Sets `MODULE_NAME` and `MODEL_CLASS` class attributes
- [ ] Uses simplest pattern that works (prefer A → B → C)

---

## Additional Checks

### Multi-Endpoint Resources
If resource has conditional routing (e.g., organization with opa_query_path):
- [ ] Routing logic clear and documented
- [ ] Tests cover all endpoint paths

### CasC Team Notification
Notify if PR includes:
- New module
- Return value structure changes  
- Authentication changes
- Breaking changes

Add comment: `@ansible/casc-team FYI - <brief description>`

### Documentation Updates (If Applicable)
- [ ] `docs/07-adding-resources.md` - New patterns
- [ ] README examples - User-facing features

---

## Review Summary Template

```markdown
## Feature Review: #<PR_NUMBER>

**Seven-File Pattern:** ✅ Complete / ❌ Missing: [files]
**Architecture:** ✅ Compliant / ❌ Issues: [details]  
**Tests:** ✅ Passing (unit + molecule) / ❌ Failures: [details]
**Linting:** ✅ Zero violations / ❌ [count] violations
**meta/runtime.yml:** ✅ Registered / ❌ Missing

**Verdict:** ✅ APPROVE for safe-to-test / ❌ REQUEST CHANGES

[Detailed findings if blocking]
```

---

**Last Updated:** 2026-09-11
