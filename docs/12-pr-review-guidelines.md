# PR Review Guidelines

Comprehensive guidelines for reviewing pull requests in the ansible.platform collection.

**Audience:** Maintainers, reviewers, and contributors

**Last Updated:** 2026-09-11

---

## Table of Contents

1. [Review Process Overview](#review-process-overview)
2. [Pre-Merge CI Checks](#pre-merge-ci-checks)
3. [Feature PR Review](#feature-pr-review)
4. [Bugfix PR Review](#bugfix-pr-review)
5. [CI/Workflow PR Review](#ciworkflow-pr-review)
6. [Connection/Manager PR Review](#connectionmanager-pr-review-critical)
7. [Architecture Principles](#architecture-principles)
8. [Code Quality Standards](#code-quality-standards)
9. [Testing Requirements](#testing-requirements)
10. [Common Issues and Fixes](#common-issues-and-fixes)
11. [Getting PRs Merged Faster](#getting-prs-merged-faster)

---

## Review Process Overview

### Workflow Steps

1. **Pre-Merge CI Checks** - Must pass BEFORE `safe to test` label
   - Collection completeness test
   - Unit tests
   - Sanity tests
   - Changelog verification

2. **Code Review** - Route to appropriate checklist:
   - Feature → Seven-file pattern + architecture
   - Bugfix → Regression test + root cause
   - CI/Workflow → Security + secret protection
   - Connection/Manager → Cross-module impact + fork safety

3. **Safe to Test** - Apply label after pre-merge checks pass

4. **Integration Tests** - Triggered by `safe to test` label

5. **Final Review** - 2+ approvals, all checks green

6. **Merge** - Squash and merge to devel

### Priority Checks

| Priority | Check | Blocker? |
|----------|-------|----------|
| 🔴 Critical | Collection completeness test | YES |
| 🔴 Critical | Unit tests | YES |
| 🔴 Critical | Sanity tests | YES |
| 🔴 Critical | Connection/manager changes (if applicable) | YES |
| 🟡 Important | Changelog fragment | YES (if code changes) |
| 🟡 Important | Jira reference | YES (if bugfix) |
| 🟢 Optional | Integration tests | NO (can defer) |

---

## Pre-Merge CI Checks

**These checks run automatically and MUST pass before `safe to test` label.**

### 1. Collection Completeness Test

**What it checks:** All modules extending `ansible.platform.auth` are registered in `meta/runtime.yml`

**Purpose:** Enables `module_defaults` for `group/ansible.platform.gateway`

**Test location:** `tests/test_completeness.py`

**Common failure:**
```
The following items should be added to meta/runtime.yml action-groups.gateway:
    ad_hoc_command
```

**Fix:**
```yaml
# meta/runtime.yml
action_groups:
  gateway:
    - ad_hoc_command  # ← ADD THIS
    - application
    - authenticator
```

**Why it matters:**
- Ensures `module_defaults` work for all modules
- Enforces consistency across collection
- Required CI check (blocks merge)

### 2. Unit Tests

**What they check:** Transform logic, utilities, framework code

**Run locally:**
```bash
pytest tests/unit/ -v

# Run specific test
pytest tests/unit/plugins/plugin_utils/api/v1/test_team.py -v
```

**Common failures:**
- Assertion errors (expected vs actual mismatch)
- Import errors (missing dependencies)
- Mock/fixture issues

### 3. Sanity Tests

**What they check:**
- Documentation format (DOCUMENTATION, EXAMPLES, RETURN)
- Import validation
- PEP8 compliance
- Ansible-specific rules

**Run locally:**
```bash
ansible-test sanity --docker

# Run specific test
ansible-test sanity plugins/modules/organization.py --docker
```

**Common failures:**
- Malformed DOCUMENTATION YAML
- Missing required doc fields
- Import violations
- Formatting issues

### 4. Changelog Fragment

**Required if PR changes:**
- `plugins/**/*.py` → YES
- `tests/**/*.py` → YES
- `docs/**/*.md` → NO
- `.github/**/*.yml` → NO (unless user-visible)

**Location:** `changelogs/fragments/<pr_number>-<short_name>.yml`

**Formats:**

```yaml
# For features
minor_changes:
  - "Add foo module for managing Foo resources (ansible/ansible.platform#123)."

# For bugfixes
bugfixes:
  - "Fix vault credential handling in manager subprocess (ansible/ansible.platform#124)."

# For breaking changes
breaking_changes:
  - "Remove deprecated bar parameter from baz module. Use qux instead (ansible/ansible.platform#125)."

# For deprecations
deprecated_features:
  - "The old_param parameter in foo module is deprecated and will be removed in 3.0.0. Use new_param instead (ansible/ansible.platform#126)."
```

**Validation:**
```bash
# Check if fragment exists
ls changelogs/fragments/ | grep -E "<pr_number>|<feature_name>"

# Validate YAML syntax
ansible-doc-extractor --validate changelogs/fragments/<file>.yml
```

---

## Feature PR Review

**Use for:** New modules, new features, significant refactoring

### Seven-File Pattern Checklist

**For new modules, all files must be present:**

| # | File | Required? | What to Check |
|---|------|-----------|---------------|
| 1 | `plugins/modules/<resource>.py` | ✅ Always | Module stub with DOCUMENTATION + EXAMPLES |
| 2 | `plugins/action/<resource>.py` | ✅ Always | ActionModule class (Pattern A/B/C) |
| 3 | `plugins/plugin_utils/ansible_models/<resource>.py` | ✅ Always | AnsibleFoo dataclass, stable fields |
| 4 | `plugins/plugin_utils/api/v1/<resource>.py` | ✅ Always | APIFoo_v1 + transform mixin |
| 5 | `tests/unit/` | ✅ Always | pytest tests for transform logic |
| 6 | `extensions/molecule/<resource>_mock/` | ✅ Recommended | Mock server tests, idempotency |
| 7 | `tests/integration/targets/<resource>s_test/` | ⚠️ Can defer | Live AAP tests (can add later) |

**Verification commands:**

```bash
# Check all files
for file in \
  "plugins/modules/<resource>.py" \
  "plugins/action/<resource>.py" \
  "plugins/plugin_utils/ansible_models/<resource>.py" \
  "plugins/plugin_utils/api/v1/<resource>.py"; do
  test -f "$file" && echo "✅ $file" || echo "❌ MISSING: $file"
done

# Check tests
find tests/unit -name "*<resource>*" -type f
test -d extensions/molecule/<resource>_mock && echo "✅ Molecule" || echo "⚠️ Molecule missing"
test -d tests/integration/targets/<resource>s_test && echo "✅ Integration" || echo "⚠️ Can add later"
```

### Architecture Compliance

#### 1. Ansible Model Review (`plugins/plugin_utils/ansible_models/<resource>.py`)

**✅ Correct pattern:**

```python
@dataclass
class AnsibleTeam:
    # Required fields first
    name: str
    organization: str  # ✅ String name, NOT integer ID
    
    # Optional fields with defaults
    description: Optional[str] = None
    state: str = "present"
    
    # Read-only fields (from API)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
```

**❌ Common mistakes:**

```python
@dataclass
class AnsibleTeam:
    organization: int  # ❌ WRONG - Should be str
    organization_id: int  # ❌ WRONG - API-specific field
    name: str  # ❌ WRONG - Required after optional
    description: Optional[str] = None
```

**Checklist:**

- [ ] Uses `@dataclass` decorator
- [ ] Class name is `Ansible<Resource>` (PascalCase)
- [ ] Required fields first, optional with defaults after
- [ ] Reference fields use **string names** (not IDs)
- [ ] Read-only fields marked `Optional`
- [ ] `state` field defaults to `"present"`
- [ ] No API-specific fields

#### 2. API Model Review (`plugins/plugin_utils/api/v1/<resource>.py`)

**✅ Correct pattern:**

```python
@dataclass
class APITeam_v1:
    # All fields Optional (wire format)
    name: Optional[str] = None
    organization: Optional[int] = None  # ✅ Integer ID
    description: Optional[str] = None
    
    # Read-only fields
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
```

**❌ Common mistakes:**

```python
@dataclass
class APITeam_v1:
    name: str  # ❌ WRONG - Should be Optional[str] = None
    organization: str  # ❌ WRONG - Should be Optional[int] (ID)
```

**Checklist:**

- [ ] Uses `@dataclass` decorator
- [ ] Class name is `API<Resource>_v1`
- [ ] **All fields are Optional** (wire format)
- [ ] Reference fields use **integer IDs** (not names)
- [ ] Matches Gateway/Controller/EDA/Hub API response
- [ ] Read-only fields included

#### 3. Transform Mixin Review (same file as API model)

**✅ Correct endpoint path declaration:**

```python
class TeamTransformMixin_v1:
    def get_endpoint_operations(self):
        return EndpointOperation(
            path="/api/gateway/v1/teams/",  # ✅ Full path with service prefix
            list_path="/api/gateway/v1/teams/",
            detail_path="/api/gateway/v1/teams/{id}/",
            lookup_field="name",
        )
```

**Service prefix table:**

| Service | Prefix | Example |
|---------|--------|---------|
| Gateway | `/api/gateway/v1/` | `/api/gateway/v1/teams/` |
| Controller | `/api/controller/v2/` | `/api/controller/v2/job_templates/` |
| EDA | `/api/eda/v1/` | `/api/eda/v1/projects/` |
| Hub | `/api/hub/v3/` | `/api/hub/v3/namespaces/` |

**❌ Common mistake:**

```python
# ❌ WRONG: EDA resource with Gateway prefix
path="/api/gateway/v1/projects/"  # Should be: /api/eda/v1/projects/
```

**✅ Correct name→ID resolution:**

```python
@classmethod
def from_ansible_data(cls, ansible_instance, context):
    api_data = {}
    
    # Resolve organization name → ID
    if ansible_instance.organization:
        org_id = context.manager.lookup_resource_id(
            "organization",  # Resource type
            ansible_instance.organization,  # Name from user
            endpoint="/api/gateway/v1/organizations/"  # Lookup endpoint
        )
        api_data["organization"] = org_id  # ID in API
    
    # Pass through non-reference fields
    if ansible_instance.name:
        api_data["name"] = ansible_instance.name
    
    return APITeam_v1(**api_data)
```

**✅ Correct reverse transform:**

```python
@classmethod
def from_api(cls, api_data, context):
    """Map API response back to Ansible model."""
    return AnsibleTeam(
        id=api_data.get("id"),
        name=api_data.get("name"),
        organization=api_data.get("organization"),  # ID→name conversion handled elsewhere
        description=api_data.get("description"),
        # ⚠️ DON'T FORGET: If you add field to from_ansible_data(),
        # also add to from_api() or idempotency breaks!
    )
```

**Checklist:**

- [ ] Endpoint path has correct service prefix
- [ ] All reference fields use `lookup_resource_id()`
- [ ] Non-reference fields pass through directly
- [ ] Write-only fields (passwords) excluded from read
- [ ] Reverse transform (`from_api()`) maps all fields back
- [ ] Multi-endpoint pattern used if fields split across APIs

#### 4. Module Documentation Review (`plugins/modules/<resource>.py`)

**✅ Correct DOCUMENTATION:**

```python
DOCUMENTATION = """
module: team
short_description: Manage teams in AAP
description:
  - Create, update, or delete teams in Ansible Automation Platform.
  - Teams are collections of users with shared permissions.
version_added: "2.7.0"
extends_documentation_fragment:
  - ansible.platform.auth
options:
  name:
    description:
      - The unique name of the team.
    type: str
    required: true
  organization:
    description:
      - The organization name or ID that the team belongs to.
      - Accepts either the organization name (looked up automatically) or integer ID.
    type: str
    required: true
  description:
    description:
      - Optional description of the team.
    type: str
    required: false
  state:
    description:
      - Desired state of the team.
    type: str
    choices: ['present', 'absent', 'exists']
    default: present
author:
  - "Your Name (@github_username)"
"""

EXAMPLES = """
- name: Create engineering team
  ansible.platform.team:
    name: "Engineering"
    organization: "Red Hat"
    description: "Engineering team"
    state: present

- name: Delete team
  ansible.platform.team:
    name: "Engineering"
    organization: "Red Hat"
    state: absent

- name: Check if team exists
  ansible.platform.team:
    name: "Engineering"
    organization: "Red Hat"
    state: exists
  register: result
"""

RETURN = """
id:
  description: The ID of the team
  returned: success
  type: int
  sample: 42
name:
  description: The name of the team
  returned: success
  type: str
  sample: "Engineering"
organization:
  description: The organization ID
  returned: success
  type: int
  sample: 1
"""
```

**Checklist:**

- [ ] `module:` matches filename
- [ ] `short_description` clear and concise
- [ ] All parameters have `description`, `type`, `required`/`default`
- [ ] `extends_documentation_fragment: ansible.platform.auth` present
- [ ] `EXAMPLES` show realistic use cases
- [ ] `RETURN` documents all returned values
- [ ] `version_added` set correctly
- [ ] Valid YAML (test with `python -c "import yaml; yaml.safe_load(DOCUMENTATION)"`)

#### 5. meta/runtime.yml Registration

**Required for all new modules:**

```yaml
# meta/runtime.yml
action_groups:
  gateway:
    - ad_hoc_command
    - application
    - authenticator
    - <new_module>  # ← ADD THIS
    - organization
    - team
```

**Verification:**

```bash
grep "<module_name>" meta/runtime.yml || echo "❌ Missing from runtime.yml"
```

### Test Coverage Requirements

#### Unit Tests (Required)

**Location:** `tests/unit/plugins/plugin_utils/api/v1/test_<resource>.py`

**Minimum tests:**

```python
def test_from_ansible_data_basic():
    """Test basic field mapping."""
    ansible_team = AnsibleTeam(name="test", organization="Red Hat")
    context = create_mock_context()
    
    mixin = TeamTransformMixin_v1()
    api_team = mixin.from_ansible_data(ansible_team, context)
    
    assert api_team.name == "test"
    # ... verify all fields

def test_from_ansible_data_resolves_organization():
    """Test organization name→ID resolution."""
    ansible_team = AnsibleTeam(name="test", organization="Red Hat")
    context = create_mock_context()
    context.manager.lookup_resource_id = Mock(return_value=42)
    
    mixin = TeamTransformMixin_v1()
    api_team = mixin.from_ansible_data(ansible_team, context)
    
    assert api_team.organization == 42
    context.manager.lookup_resource_id.assert_called_once_with(
        "organization", "Red Hat", endpoint="/api/gateway/v1/organizations/"
    )

def test_from_api_maps_all_fields():
    """Test reverse transformation."""
    api_data = {"id": 1, "name": "test", "organization": 42}
    
    mixin = TeamTransformMixin_v1()
    ansible_team = mixin.from_api(api_data, context)
    
    assert ansible_team.id == 1
    assert ansible_team.name == "test"

def test_endpoint_operations_correct_path():
    """Test endpoint path."""
    mixin = TeamTransformMixin_v1()
    ops = mixin.get_endpoint_operations()
    
    assert ops.path == "/api/gateway/v1/teams/"
```

**Run:**
```bash
pytest tests/unit/plugins/plugin_utils/api/v1/test_team.py -v
```

#### Molecule Tests (Recommended)

**Location:** `extensions/molecule/<resource>_mock/converge.yml`

**Required scenarios:**

```yaml
---
# 1. CREATE
- name: Create team
  ansible.platform.team:
    name: "Test Team"
    organization: "Test Org"
    state: present
  register: result

- name: Verify created
  assert:
    that:
      - result.changed
      - result.id is defined

# 2. IDEMPOTENCY
- name: Create team again (idempotent)
  ansible.platform.team:
    name: "Test Team"
    organization: "Test Org"
    state: present
  register: result

- name: Verify no change
  assert:
    that:
      - not result.changed  # ← Idempotent!

# 3. UPDATE
- name: Update team description
  ansible.platform.team:
    name: "Test Team"
    organization: "Test Org"
    description: "Updated"
    state: present
  register: result

- name: Verify updated
  assert:
    that:
      - result.changed
      - result.description == "Updated"

# 4. DELETE
- name: Delete team
  ansible.platform.team:
    name: "Test Team"
    organization: "Test Org"
    state: absent
  register: result

- name: Verify deleted
  assert:
    that:
      - result.changed
```

**Run:**
```bash
molecule test -s team_mock
```

#### Integration Tests (Can Defer)

**Location:** `tests/integration/targets/<resource>s_test/`

**Can add in follow-up PR if:**
- Unit tests comprehensive
- Molecule tests comprehensive
- Follow-up Jira ticket created

---

## Bugfix PR Review

**Use for:** Bug fixes, regressions, defects

### Jira Issue Verification

**Required format in PR title:**
```
[AAP-12345] Fix description
```

**Validation:**
```bash
gh pr view <PR> --json title --jq '.title' | grep -oE 'AAP-[0-9]+'
```

**If missing:**
```markdown
❌ **Blocker:** Missing Jira issue reference in PR title

Please update: [AAP-XXXXX] <description>
```

### Bug Description Requirements

**PR description must include:**

1. **What was broken:** Clear description
2. **How to reproduce:** Step-by-step
3. **Root cause:** Why the bug occurred
4. **What changed:** The fix applied
5. **How verified:** Testing approach

**Example:**

```markdown
## Bug Description

**Issue:** Vaulted aap_username/aap_password cause subprocess.Popen to fail

**Reproduce:**
1. Encrypt credentials with ansible-vault
2. Run any platform module
3. Error: TypeError: expected str, not AnsibleVaultEncryptedUnicode

**Root Cause:**
process_manager.py passes vaulted credentials directly to subprocess.Popen
without converting to strings first.

**Fix:**
Convert gateway_config credentials to str() before passing to Popen.

**Verification:**
- Added unit test with MockAnsibleVaultEncryptedUnicode
- Test verifies str() conversion happens
- Manual test with vaulted group_vars
```

### Regression Test Requirements (CRITICAL)

**Bugfix MUST include test that would have caught the bug.**

**Three options (in order of preference):**

#### Option 1: Unit Test (Preferred)

```python
# tests/unit/plugins/plugin_utils/manager/test_vault_credentials.py

def test_vault_credentials_converted_to_strings():
    """
    Test that vaulted credentials are converted to str before Popen.
    
    Regression test for AAP-XXXXX where vaulted credentials caused:
    TypeError: expected str, not AnsibleVaultEncryptedUnicode
    """
    # Create vaulted credentials
    vaulted_username = MockAnsibleVaultEncryptedUnicode("admin")
    vaulted_password = MockAnsibleVaultEncryptedUnicode("secret")
    
    # Verify type
    assert type(vaulted_username).__name__ != "str"
    
    # Create config with vaulted creds
    gateway_config = GatewayConfig(
        base_url="https://gateway.example.com",
        username=vaulted_username,
        password=vaulted_password,
    )
    
    # Mock subprocess.Popen
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value.pid = 12345
        
        ProcessManager.spawn_manager_process(
            script_path=Path("manager_process.py"),
            socket_path="/tmp/test.sock",
            gateway_config=gateway_config,
        )
        
        # Verify Popen was called
        assert mock_popen.called
        
        # Get cmd argument
        cmd = mock_popen.call_args[0][0]
        
        # ✅ CRITICAL: Verify arguments are plain str, not Vault objects
        for i, arg in enumerate(cmd):
            assert isinstance(arg, (str, bytes)) or hasattr(arg, "__fspath__"), \
                f"cmd[{i}] = {arg!r} is not valid for subprocess"
        
        # Verify credentials converted
        username_arg = cmd[5]
        password_arg = cmd[6]
        
        assert isinstance(username_arg, str) and type(username_arg) == str
        assert isinstance(password_arg, str) and type(password_arg) == str
        assert username_arg == "admin"
        assert password_arg == "secret"
```

**Checklist:**

- [ ] Test reproduces bug conditions
- [ ] Test would FAIL before fix
- [ ] Test PASSES after fix
- [ ] Docstring explains bug (Jira reference)
- [ ] Assertions verify fix, not just "didn't crash"

#### Option 2: Molecule Test

```yaml
# extensions/molecule/organization_mock/converge.yml

- name: Test with vaulted credentials (AAP-XXXXX regression)
  ansible.platform.organization:
    aap_username: "{{ lookup('ansible.builtin.vault', encrypted_username) }}"
    aap_password: "{{ lookup('ansible.builtin.vault', encrypted_password) }}"
    name: "Test Org"
    state: present
  register: result

- name: Verify vault credentials work
  assert:
    that:
      - not result.failed
      - result.changed
```

#### Option 3: Integration Test

```yaml
# tests/integration/targets/organizations_test/tasks/main.yml

- name: Test specific bug scenario (AAP-XXXXX)
  ansible.platform.organization:
    # ... parameters that trigger bug
  register: result

- assert:
    that:
      - result is success
```

### Code Review: The Fix

**✅ Good fix pattern:**

```python
# BEFORE (buggy)
cmd = [
    sys.executable,
    gateway_config.username,  # ❌ Vault object
    gateway_config.password,  # ❌ Vault object
]

# AFTER (fixed)
cmd = [
    sys.executable,
    str(gateway_config.username) if gateway_config.username else "",  # ✅ Converted
    str(gateway_config.password) if gateway_config.password else "",  # ✅ Converted
]
```

**Checklist:**

- [ ] Fix addresses root cause (not just symptoms)
- [ ] Fix is minimal (no unrelated refactoring)
- [ ] No commented-out debug code
- [ ] Backwards compatible
- [ ] No breaking changes

### Check for Similar Bugs

**Scan codebase for same pattern:**

```bash
# Example: If bug was missing str() conversion
grep -r "subprocess.Popen" plugins/ | grep -v "str("

# Example: If bug was missing null check
grep -r "\.get(" plugins/ | grep -v "if .* is not None"
```

**If found:**
```markdown
⚠️ **Note:** Similar pattern found

Found similar usage in:
- plugins/foo/bar.py:123

**Recommendation:**
- Fix in this PR (same root cause) OR
- Create follow-up Jira ticket
```

---

## CI/Workflow PR Review

**Use for:** GitHub Actions workflows, CI configuration, test infrastructure

### Critical Checks for New Workflows

**First, detect if workflow is NEW:**

```bash
# List new workflows
git diff origin/devel --name-status .github/workflows/ | grep '^A'
```

**If NEW workflow, additional checks:**

- [ ] **Purpose justified** - Why new vs modifying existing?
- [ ] **Name descriptive** - Clear what it does
- [ ] **No duplication** - Doesn't replicate existing workflow
- [ ] **Documented in PR** - Explanation of purpose
- [ ] **Minimal scope** - Does one thing well
- [ ] **Tested in fork** - REQUIRED before merge

### Security Review (CRITICAL)

#### 1. Check for Injection Vulnerabilities

**❌ DANGEROUS:**

```yaml
- name: Run command
  run: echo "${{ github.event.issue.title }}"  # Injection risk!
```

**✅ SAFE:**

```yaml
- name: Run command
  env:
    TITLE: ${{ github.event.issue.title }}
  run: echo "$TITLE"
```

#### 2. Secret Protection (CRITICAL)

**Rule 1: Never expose secrets to fork PRs**

**❌ DANGEROUS:**

```yaml
on: pull_request  # Runs for ANY fork!
jobs:
  build:
    steps:
      - run: echo "${{ secrets.AAP_PASSWORD }}"  # LEAKED to fork!
```

**✅ SAFE:**

```yaml
on:
  pull_request:
    types: [labeled]

jobs:
  integration:
    # Only run after manual approval
    if: |
      github.event.label.name == 'safe to test' &&
      github.event.pull_request.author_association == 'MEMBER'
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - env:
          AAP_PASSWORD: ${{ secrets.AAP_PASSWORD }}
        run: ansible-playbook tests/integration/
```

**Rule 2: Secrets in env vars, not inline**

**❌ BAD:**

```yaml
- run: ansible-galaxy publish --token ${{ secrets.GALAXY_TOKEN }}
```

**✅ GOOD:**

```yaml
- env:
    GALAXY_TOKEN: ${{ secrets.GALAXY_TOKEN }}
  run: ansible-galaxy publish --token "$GALAXY_TOKEN"
```

**Secret protection checklist:**

- [ ] No secrets on `pull_request` trigger
- [ ] Label gate (`safe to test`) for secret access
- [ ] Author association check (`MEMBER`, `OWNER`)
- [ ] Secrets in env vars, not inline
- [ ] No secret logging
- [ ] No secrets in artifacts
- [ ] Secrets masked in workflow runs

**Verification commands:**

```bash
# CRITICAL: Find workflows leaking secrets to fork PRs
for f in .github/workflows/*.yml; do
  if grep -q "on: pull_request" "$f" && grep -q "secrets\." "$f"; then
    echo "❌ DANGER: $f exposes secrets to fork PRs!"
  fi
done

# Find safe to test label gates
grep -l "safe to test" .github/workflows/*.yml

# Find author association checks
grep -l "author_association" .github/workflows/*.yml

# Find unsafe inline secret usage
grep -n '\${{ secrets\.' .github/workflows/*.yml | grep -v 'env:'
```

#### 3. Permissions Review

**✅ GOOD:**

```yaml
permissions:
  contents: read
  pull-requests: write  # Only if needed
```

**❌ BAD:**

```yaml
permissions: write-all  # Never use!
```

**Checklist:**

- [ ] Permissions follow least-privilege
- [ ] Only grants what's needed
- [ ] No `write-all` permission

#### 4. Trigger Conditions

**✅ GOOD:**

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]
    paths:
      - 'plugins/**'
      - 'tests/**'
  push:
    branches:
      - devel
      - stable-*
```

**❌ BAD:**

```yaml
on: [push, pull_request]  # Too broad, wastes CI
```

### Fork Testing Requirement

**For new workflows, MUST test in fork:**

```markdown
**Testing request:**

Please test this workflow in your fork:

1. Push this branch to your fork
2. Create PR in your fork
3. Verify workflow runs as expected
4. Share workflow run URL
```

### Quick Reference: Review Commands

```bash
# Check for new workflows
git diff origin/devel --name-status .github/workflows/ | grep '^A'

# Validate YAML syntax
yamllint .github/workflows/<workflow>.yml

# Check GitHub Actions syntax
gh workflow view <workflow-name> --repo ansible/ansible.platform

# Find workflows with write-all (DANGEROUS)
grep -n "write-all" .github/workflows/*.yml

# List all permission declarations
grep -A 5 "permissions:" .github/workflows/*.yml

# Find all pull_request triggers
grep -n "on: pull_request" .github/workflows/*.yml

# Find pull_request_target (verify safety)
grep -n "pull_request_target" .github/workflows/*.yml
```

---

## Connection/Manager PR Review (CRITICAL)

**⚠️ Use when PR changes core infrastructure files:**

```
plugins/connection/http.py
plugins/plugin_utils/manager/*
plugins/plugin_utils/platform/{base_client,direct_client,config,registry}.py
```

**Why critical:** These changes affect **ALL modules** in the collection.

### Detection

```bash
# Auto-detect connection/manager changes
git diff origin/devel --name-only | grep -E \
  'plugins/connection/|plugins/plugin_utils/manager/|plugins/plugin_utils/platform/(base_client|direct_client|config|registry)'
```

**If ANY match → Extra scrutiny required**

### Critical Checks

#### 1. Backwards Compatibility (MUST TEST)

**Test with MULTIPLE modules (minimum 3):**

```yaml
# Test organization, team, AND user modules
- name: Test organization
  ansible.platform.organization:
    name: "Test Org"
  register: org_result

- name: Test team
  ansible.platform.team:
    name: "Test Team"
    organization: "Test Org"
  register: team_result

- name: Test user
  ansible.platform.user:
    username: "testuser"
  register: user_result

- assert:
    that:
      - org_result is success
      - team_result is success
      - user_result is success
```

**Why:** Ensures change doesn't break specific module patterns.

**Checklist:**

- [ ] No breaking changes to RPC protocol
- [ ] All authentication methods work (username/password, token, OAuth)
- [ ] Existing modules still work (test 3+ different modules)
- [ ] Both connection modes work (persistent, direct)

#### 2. Fork Safety (macOS + Python 3.12)

**Python 3.12 on macOS changed fork behavior - HTTP sessions break.**

**❌ WRONG:**

```python
# Session created BEFORE fork
session = requests.Session()

subprocess.Popen(...)  # Fork happens
# Session is now broken on macOS!
```

**✅ CORRECT:**

```python
# Session created AFTER fork in subprocess
def run_in_subprocess():
    session = requests.Session()  # Created in subprocess
```

**Checklist:**

- [ ] No HTTP sessions created before subprocess spawn
- [ ] No shared state between parent and subprocess
- [ ] Manager process creates own HTTP session
- [ ] Tested on macOS + Python 3.12 (if possible)

#### 3. Connection Mode Testing

**Both modes MUST work:**

```bash
# Test persistent mode (default)
ansible-playbook tests/integration/test.yml

# Test direct mode (fallback)
AAP_CONNECTION_MODE=direct ansible-playbook tests/integration/test.yml
```

**Checklist:**

- [ ] Persistent mode works
- [ ] Direct mode works
- [ ] Fallback logic intact
- [ ] Mode detection unchanged

#### 4. Subprocess Spawning Security

**CRITICAL: Vault credentials must be converted to str()**

**❌ BUG:**

```python
cmd = [
    sys.executable,
    gateway_config.password,  # TypeError if vaulted!
]
```

**✅ FIX:**

```python
cmd = [
    sys.executable,
    str(gateway_config.password) if gateway_config.password else "",
]
```

**Checklist:**

- [ ] All cmd arguments are str/bytes/Path
- [ ] Vault credentials → str()
- [ ] None values handled
- [ ] No shell=True (injection risk)
- [ ] Process cleanup on error

#### 5. Socket Management

**Checklist:**

- [ ] Socket path unique per manager (identifier)
- [ ] Socket removed on cleanup
- [ ] Socket permissions secure (0600)
- [ ] Socket directory exists and writable
- [ ] Stale socket detection
- [ ] Socket path < 104 chars (Unix limit)

#### 6. Security Review

**❌ DANGEROUS:**

```python
logger.debug(f"Auth with {username}:{password}")  # LEAKED!
```

**✅ SAFE:**

```python
logger.debug(f"Auth with {username}:***")
```

**Checklist:**

- [ ] No credentials in logs/errors
- [ ] No credentials in subprocess args (visible in `ps`)
- [ ] Credentials converted from vault
- [ ] Socket permissions correct
- [ ] No shell=True

#### 7. Multi-Service Support

**Verify ALL services work:**

```python
# Gateway
path="/api/gateway/v1/teams/"

# Controller
path="/api/controller/v2/job_templates/"

# EDA
path="/api/eda/v1/projects/"

# Hub
path="/api/hub/v3/namespaces/"
```

### Testing Requirements (MANDATORY)

#### Unit Tests

```python
def test_backwards_compatibility():
    """Ensure existing behavior still works."""

def test_new_functionality():
    """Test the change."""

def test_vault_credentials():
    """Test vault string conversion."""
```

#### Integration Tests (Multiple Modules!)

**MUST test 3+ modules:**

```bash
pytest tests/integration/targets/organizations_test/ -v
pytest tests/integration/targets/teams_test/ -v
pytest tests/integration/targets/users_test/ -v
```

#### Connection Mode Testing

```bash
# Both must work
ansible-playbook test.yml
AAP_CONNECTION_MODE=direct ansible-playbook test.yml
```

#### Vault Testing

```yaml
# group_vars/all.yml
aap_username: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  ...

# Must work with vaulted creds
```

---

## Architecture Principles

### Three-Tier Data Model

```
Playbook Parameters (user input)
    ↓
Ansible Model (stable, user-facing, string names)
    ↓
Transform Mixin (name→ID resolution, business logic)
    ↓
API Model (version-specific, wire format, integer IDs)
    ↓
HTTP Request to AAP Gateway
```

**Purpose:**

- **Ansible Model** never changes → User-facing stability
- **API Model** changes with API versions → Isolated in `api/v1/`, `api/v2/`
- **Transform Mixin** adapts between stable and version-specific

**Example:**

```python
# User writes (Ansible Model)
- ansible.platform.team:
    organization: "Red Hat"  # String name

# Transform Mixin resolves
org_id = manager.lookup_resource_id("organization", "Red Hat")
# Returns: 42

# API Model (wire format)
{"organization": 42}  # Integer ID

# HTTP Request
POST /api/gateway/v1/teams/
{"name": "Engineering", "organization": 42}
```

### Endpoint Path Versioning

**CRITICAL:** Folder versioning ≠ Service API versioning

**The `api/v1/`, `api/v2/` folders = collection transform versions**

**Example:**

```python
# File: plugins/plugin_utils/api/v1/organization.py
# This is collection transform v1, NOT service API v1!

# Can contain transforms for:
# - Gateway API v1: /api/gateway/v1/organizations/
# - Controller API v2: /api/controller/v2/organizations/  ← Controller v2 in api/v1/ folder!
```

**Endpoint paths declared in mixin:**

```python
def get_endpoint_operations(self):
    return EndpointOperation(
        path="/api/controller/v2/organizations/",  # Full path
        lookup_field="name",
    )
```

### Service Prefix Table

| Service | Prefix | Example Endpoint |
|---------|--------|-----------------|
| Gateway | `/api/gateway/v1/` | `/api/gateway/v1/teams/` |
| Controller | `/api/controller/v2/` | `/api/controller/v2/job_templates/` |
| EDA | `/api/eda/v1/` | `/api/eda/v1/projects/` |
| Hub | `/api/hub/v3/` | `/api/hub/v3/namespaces/` |

**Mismatched prefix = 404 errors!**

### Single Gateway Authentication

**One set of credentials for ALL services:**

```yaml
# Works for Gateway, Controller, EDA, Hub
aap_hostname: "{{ gateway_url }}"
aap_username: "{{ username }}"
aap_password: "{{ password }}"
```

**Gateway routes internally - no separate credentials needed.**

---

## Code Quality Standards

### Idempotency

**Requirement:** Second run with same parameters returns `changed: false`

**Test pattern:**

```yaml
# Run 1: Should change
- ansible.platform.team:
    name: "Engineering"
    state: present
  register: result1

# Run 2: Should NOT change
- ansible.platform.team:
    name: "Engineering"
    state: present
  register: result2

- assert:
    that:
      - result1.changed
      - not result2.changed  # Idempotent!
```

### Error Handling

**✅ GOOD:**

```python
try:
    org_id = manager.lookup_resource_id("organization", org_name)
except ResourceNotFound:
    module.fail_json(
        msg=f"Organization '{org_name}' not found. "
            f"Create it first or check spelling."
    )
```

**❌ BAD:**

```python
# No error handling, crashes with unclear error
org_id = manager.lookup_resource_id("organization", org_name)
```

### Security

**Sensitive parameters:**

```python
module = AnsibleModule(
    argument_spec=dict(
        password=dict(type='str', no_log=True),  # ✅ Masked
        token=dict(type='str', no_log=True),
        api_key=dict(type='str', no_log=True),
    )
)
```

**No credentials in logs:**

```python
# ✅ SAFE
self._display.vvvv(f"Password: {password}")  # Only with -vvvv

# ❌ DANGEROUS
logger.debug(f"Password: {password}")  # Logged!
```

---

## Testing Requirements

### Test Pyramid

```
        Integration (optional initially)
              /\
             /  \
          Molecule (recommended)
          /      \
       Unit (required)
```

### Unit Tests (Required)

**What to test:**

- Transform logic
- Name→ID resolution
- Optional field handling
- Endpoint path correctness

**Run:**

```bash
pytest tests/unit/ -v
pytest tests/unit/plugins/plugin_utils/api/v1/test_team.py -v
```

### Molecule Tests (Recommended)

**Scenarios:**

1. Create (state: present)
2. Idempotency (second run)
3. Update (change field)
4. Delete (state: absent)

**Run:**

```bash
molecule test -s team_mock
```

### Integration Tests (Can Defer)

**Can add in follow-up PR with Jira ticket**

**Run:**

```bash
# Requires live AAP instance + safe to test label
pytest tests/integration/targets/teams_test/ -v
```

---

## Common Issues and Fixes

### 1. Collection Completeness Test Failure

**Error:**

```
The following items should be added to meta/runtime.yml action-groups.gateway:
    ad_hoc_command
```

**Fix:**

```yaml
# meta/runtime.yml
action_groups:
  gateway:
    - ad_hoc_command
```

### 2. Wrong Service Prefix (404 Errors)

**Symptom:** Integration tests fail with 404

**Cause:**

```python
# ❌ EDA resource with Gateway prefix
path="/api/gateway/v1/projects/"
```

**Fix:**

```python
# ✅ Correct EDA prefix
path="/api/eda/v1/projects/"
```

### 3. Vault Credentials Not Converted

**Error:**

```
TypeError: expected str, bytes or os.PathLike object, not AnsibleVaultEncryptedUnicode
```

**Fix:**

```python
# Convert to string
str(gateway_config.password) if gateway_config.password else ""
```

### 4. Idempotency Broken

**Symptom:** Second run always shows `changed: true`

**Cause:** Field missing in `from_api()` reverse transform

**Fix:**

```python
@classmethod
def from_api(cls, api_data, context):
    return AnsibleFoo(
        opa_query_path=api_data.get("opa_query_path"),  # ← Add this!
    )
```

### 5. Missing Changelog Fragment

**Error:** PR checks fail with "No changelog fragment found"

**Fix:**

```bash
# Create fragment
cat > changelogs/fragments/123-add-foo.yml <<EOF
minor_changes:
  - "Add foo module for managing Foo resources (ansible/ansible.platform#123)."
EOF
```

### 6. Secrets Leaked to Fork PRs

**Error:** Workflow exposes secrets on `pull_request` trigger

**Fix:**

```yaml
# Change from pull_request to label-gated
on:
  pull_request:
    types: [labeled]

jobs:
  integration:
    if: |
      github.event.label.name == 'safe to test' &&
      github.event.pull_request.author_association == 'MEMBER'
```

---

## Getting PRs Merged Faster

### Before Submitting

1. **Run tests locally:**

```bash
# Unit tests
pytest tests/unit/ -v

# Sanity tests
ansible-test sanity --docker

# Molecule tests
molecule test -s <module>_mock

# Check collection completeness
python tests/test_completeness.py
```

2. **Add changelog fragment** (if code changes)

3. **Update meta/runtime.yml** (if new module)

4. **Include Jira reference** (if bugfix)

5. **Test in fork** (if workflow changes)

### During Review

1. **Respond promptly** (within 3-5 business days)

2. **Mark conversations resolved** after addressing

3. **Re-request review** after pushing fixes

4. **Don't force-push** after review (breaks diff viewing)

### Common Delays

| Issue | Typical Delay | Prevention |
|-------|--------------|------------|
| Missing changelog | 2-3 days | Add before submitting |
| Missing meta/runtime.yml | 1 day | Run completeness test locally |
| CI failures | 1-3 days | Run tests locally first |
| Unresolved comments | 3-7 days | Respond within 3 days |
| Missing Jira reference | 1 day | Add to title before submitting |

---

## Review Checklist Summary

### All PRs

- [ ] Pre-merge CI passing (completeness, unit, sanity)
- [ ] Changelog fragment present (if code changes)
- [ ] Jira reference in title (if bugfix)
- [ ] Documentation complete
- [ ] No security issues

### Feature PRs

- [ ] Seven-file pattern complete
- [ ] Ansible Model uses string names
- [ ] API Model uses integer IDs
- [ ] Transform mixin correct
- [ ] Endpoint prefix correct
- [ ] meta/runtime.yml updated
- [ ] Test coverage adequate

### Bugfix PRs

- [ ] Jira referenced
- [ ] Bug description clear
- [ ] Regression test added
- [ ] Root cause addressed
- [ ] Backwards compatible

### CI/Workflow PRs

- [ ] New workflow justified
- [ ] Security reviewed
- [ ] Secret protection (if secrets)
- [ ] Tested in fork
- [ ] Minimal scope

### Connection/Manager PRs

- [ ] Tested with 3+ modules
- [ ] Both connection modes work
- [ ] Fork-safe
- [ ] Backwards compatible
- [ ] Vault credentials handled
- [ ] No credential leaks

---

## Contact

**Questions about PR review?**

- Slack: `#aap-platform-collection` (Red Hat internal)
- GitHub: Comment on PR or open discussion
- Documentation: `docs/` folder

**Report CI issues:**

- GitHub Issues: `ansible/ansible.platform`
- Include: PR number, CI run ID, error logs

---

## Collection-Specific Expectations

### API/Completeness Parity

**Requirement:** New modules should provide comprehensive AAP API coverage.

**When adding a new module:**

1. **Check API capabilities:**
   - Does the API support all CRUD operations?
   - Are there fields we can't expose (write-only, deprecated)?
   - Are there multi-endpoint patterns needed?

2. **Document limitations:**
   ```python
   # In module DOCUMENTATION
   notes:
     - This module requires AAP 2.5 or later
     - The opa_query_path field is read-only via Controller API
     - Organization creation requires Gateway API (AAP 2.5+)
   ```

3. **API version requirements:**
   ```python
   # In transform mixin
   def get_endpoint_operations(self):
       # Document minimum AAP version
       # AAP 2.5+ required for /api/gateway/v1/
       return EndpointOperation(path="/api/gateway/v1/organizations/")
   ```

**Completeness expectations:**

| Coverage | Acceptable? | Notes |
|----------|------------|-------|
| 100% field parity | ✅ Ideal | All API fields exposed |
| 90-99% field parity | ✅ Acceptable | Document missing fields |
| 80-89% field parity | ⚠️ Review needed | Justify missing fields |
| <80% field parity | ❌ Incomplete | Add more fields or explain |

**Fields that can be skipped:**

- Internal API fields (`related`, `summary_fields`)
- Deprecated fields (document in module notes)
- Write-only fields not useful for Ansible (explain why)

### Stable vs Devel/Backport Considerations

**Branch strategy:**

```
devel (main development)
  ↓
stable-2.7 (AAP 2.7 compatible)
  ↓
stable-2.6 (AAP 2.6 compatible)
```

#### Rules for Devel Branch

**New features:**
- ✅ Go to `devel` first
- Must be AAP version-compatible (document minimum version)
- Can use latest API features

**Breaking changes:**
- ⚠️ Allowed in devel (major version bumps)
- Must document migration path
- Add to `breaking_changes:` in changelog

**Example:**
```yaml
# changelogs/fragments/130-breaking-org-field.yml
breaking_changes:
  - "organization module - removed deprecated max_hosts field. Use organization_settings module instead (ansible/ansible.platform#130)."
```

#### Rules for Stable Branch Backports

**What can be backported:**

- ✅ **Bugfixes** - Always backport critical bugs
- ✅ **Security fixes** - Always backport
- ✅ **Minor enhancements** - If backwards compatible
- ❌ **New modules** - Stay in devel
- ❌ **Breaking changes** - Never backport
- ❌ **New required fields** - Breaking, stay in devel

**Backport process:**

1. Merge to `devel` first
2. Create backport PR to `stable-2.X`
3. Label PR with `backport:stable-2.X`
4. Changelog fragment goes in both branches

**Example backport PR title:**
```
[Backport stable-2.7] Fix vault credential handling (AAP-12345)
```

**Backport changelog:**
```yaml
# In devel AND stable-2.7
bugfixes:
  - "Fix vault credential handling in manager subprocess (ansible/ansible.platform#124)."
```

#### Version Compatibility Matrix

| AAP Version | Collection Branch | Python | Ansible Core |
|-------------|------------------|--------|--------------|
| AAP 2.7 | stable-2.7, devel | 3.9+ | 2.15+ |
| AAP 2.6 | stable-2.6 | 3.9+ | 2.14+ |
| AAP 2.5 | stable-2.5 | 3.9+ | 2.14+ |

**Version-specific features:**

```python
# In module DOCUMENTATION
requirements:
  - ansible.platform >= 2.7.0  # For new gateway features
  - AAP >= 2.5.0  # For gateway API support
```

### Changelog/CasC Expectations

#### Changelog Fragment Requirements

**When required:**

- ✅ New module → `minor_changes:`
- ✅ New feature → `minor_changes:`
- ✅ Bugfix → `bugfixes:`
- ✅ Breaking change → `breaking_changes:`
- ✅ Deprecation → `deprecated_features:`
- ❌ Docs-only → No changelog
- ❌ CI-only (internal) → No changelog
- ⚠️ Test changes → Only if user-visible

**Fragment naming:**

```bash
# Format: <pr_number>-<short_description>.yml
changelogs/fragments/123-add-foo-module.yml
changelogs/fragments/124-fix-vault-creds.yml
changelogs/fragments/125-deprecate-bar.yml
```

**Quality standards:**

```yaml
# ✅ GOOD: Clear, user-facing, past tense
minor_changes:
  - "Added foo module for managing Foo resources in AAP (ansible/ansible.platform#123)."

# ❌ BAD: Technical jargon, present tense
minor_changes:
  - "Implements FooTransformMixin_v1 for foo resource endpoint mapping"

# ✅ GOOD: Actionable bugfix description
bugfixes:
  - "Fixed subprocess spawn failure when aap_username or aap_password are vaulted (ansible/ansible.platform#124)."

# ❌ BAD: Vague, no context
bugfixes:
  - "Fixed bug in manager process"
```

#### CasC (Configuration as Code) Team Notification

**When to notify CasC team:**

The CasC team maintains `casc_instance` facts and role integration. Notify them when PR affects:

1. **Return value structure changes:**
   ```python
   # BEFORE
   return {"id": 1, "name": "foo"}
   
   # AFTER (BREAKING - notify CasC!)
   return {"resource": {"id": 1, "name": "foo"}}
   ```

2. **New modules:**
   - CasC may need to add support
   - Notify so they can plan integration

3. **Authentication parameter changes:**
   - New auth methods
   - Changed parameter names
   - OAuth flow changes

4. **State behavior changes:**
   - New states added (`enforced`, `exists`)
   - State semantics changed

**How to notify:**

```bash
# Option 1: GitHub comment
gh pr comment <PR> --repo ansible/ansible.platform \
  --body "@ansible/casc-team FYI - New module added: foo. May need casc_instance fact support."

# Option 2: Add label
gh pr edit <PR> --repo ansible/ansible.platform \
  --add-label "casc-review-needed"

# Option 3: Slack (if urgent)
# Post in #aap-casc channel
```

**CasC review checklist:**

- [ ] Return values documented in RETURN block
- [ ] New modules added to CasC module list
- [ ] Auth changes documented
- [ ] Breaking changes have migration guide

### CI/Test Coverage Expectations

#### Test Coverage Requirements

**Minimum coverage by PR type:**

| PR Type | Unit | Molecule | Integration |
|---------|------|----------|-------------|
| New module | ✅ Required | ✅ Required | ⚠️ Can defer |
| New feature | ✅ Required | ✅ Recommended | ⚠️ Can defer |
| Bugfix | ✅ Required | ⚠️ If applicable | ⚠️ If applicable |
| Refactor | ✅ Required | ✅ Required | ❌ Not needed |
| Docs only | ❌ Not needed | ❌ Not needed | ❌ Not needed |
| CI/workflow | ⚠️ If testing code | ❌ Not needed | ❌ Not needed |

#### Unit Test Coverage Targets

**Target:** 80%+ coverage for new code

**Check coverage:**

```bash
# Run with coverage
pytest tests/unit/ --cov=plugins/plugin_utils --cov-report=html

# View report
open htmlcov/index.html
```

**Coverage expectations:**

- **Transform mixins:** 90%+ coverage (critical path)
- **Utilities:** 80%+ coverage
- **Action plugins:** 70%+ coverage (harder to test)

**Coverage exemptions:**

- Exception handling for "impossible" cases
- Defensive code for future compatibility
- Debug logging statements

#### Molecule Test Scenarios

**Required scenarios for new modules:**

1. ✅ **Create** - `state: present`
2. ✅ **Idempotency** - Run twice, second returns `changed: false`
3. ✅ **Update** - Modify field
4. ✅ **Delete** - `state: absent`

**Optional but recommended:**

5. ⚠️ **Exists** - `state: exists` check
6. ⚠️ **Enforced** - `state: enforced` if supported
7. ⚠️ **Error handling** - Invalid parameters

**Molecule test quality:**

```yaml
# ✅ GOOD: Comprehensive assertions
- name: Create team
  ansible.platform.team:
    name: "Test Team"
    organization: "Test Org"
    state: present
  register: result

- name: Verify all fields
  assert:
    that:
      - result.changed
      - result.id is defined
      - result.name == "Test Team"
      - result.organization is defined

# ❌ BAD: Minimal assertions
- assert:
    that:
      - result.changed  # Not checking actual result!
```

#### Integration Test Deferral Policy

**Can defer integration tests if:**

1. ✅ Unit tests cover transform logic
2. ✅ Molecule tests cover all scenarios
3. ✅ Follow-up Jira ticket created
4. ✅ Documented in PR comments

**Cannot defer if:**

1. ❌ Bug found in production (regression test needed)
2. ❌ Multi-endpoint pattern (needs live API testing)
3. ❌ Complex state machine (molecule mock insufficient)

**Deferral template:**

```markdown
## Integration Test Deferral

**Reason:** Comprehensive unit and molecule coverage

**Follow-up:** Created AAP-XXXXX to track integration tests

**Coverage:**
- ✅ Unit tests: 95% coverage of transform logic
- ✅ Molecule tests: All CRUD scenarios covered
- ⏳ Integration tests: Deferred to AAP-XXXXX
```

#### CI Pipeline Stages

**Pre-merge (runs on all PRs):**

1. **Sanity** - Documentation, imports, PEP8
2. **Unit** - pytest tests
3. **Completeness** - meta/runtime.yml check
4. **Linting** - black, isort, flake8

**Post-label (triggered by `safe to test`):**

5. **Molecule** - Mock server tests
6. **Integration** - Live AAP tests

**Expected run times:**

- Pre-merge: ~5-10 minutes
- Molecule: ~10-15 minutes
- Integration: ~15-30 minutes
- **Total: ~30-55 minutes**

#### CI Failure Investigation

**When CI fails:**

1. **Check logs:**
   ```bash
   gh run view <RUN_ID> --repo ansible/ansible.platform --log
   ```

2. **Categorize failure:**
   - ❌ Real failure → Fix required
   - ⚠️ Transient failure → Re-run
   - ⚠️ Infrastructure issue → Report to maintainers

3. **Common transient failures:**
   - AAP instance connectivity
   - Container pull failures
   - Network timeouts

4. **Re-run transient failures:**
   ```bash
   gh run rerun <RUN_ID> --repo ansible/ansible.platform --failed
   ```

**Failure ownership:**

| Failure Type | Owner | Action |
|-------------|-------|---------|
| Unit test | PR author | Fix code |
| Sanity | PR author | Fix format/docs |
| Completeness | PR author | Update meta/runtime.yml |
| Integration (real) | PR author | Fix code |
| Integration (transient) | Anyone | Re-run |
| CI infrastructure | Maintainers | Report issue |

---

## Related Documentation

- [docs/07-adding-resources.md](07-adding-resources.md) - Seven-file pattern
- [docs/04-data-model-transformation.md](04-data-model-transformation.md) - Three-tier architecture
- [docs/03-sdk-architecture.md](03-sdk-architecture.md) - Manager subprocess
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contributor guide
- `.claude/skills/pr-review/` - Automated review skill (maintainers)

---

**Last Updated:** 2026-09-11
