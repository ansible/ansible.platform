# Bugfix PR Review Guide

Detailed checklist for reviewing bugfix PRs.

## When to Use

- PR title starts with `fix:` or `bug:`
- PR references a Jira issue (AAP-XXXXX)
- PR fixes a regression or defect

---

## ⚠️ CRITICAL: Check for Core Infrastructure Changes

**Before proceeding, check if bugfix touches connection/manager files:**

```bash
git diff origin/devel --name-only | grep -E \
  'plugins/connection/|plugins/plugin_utils/manager/|plugins/plugin_utils/platform/(base_client|direct_client|config|registry)'
```

**If ANY match found:**
→ **STOP:** Read `connection-manager-review.md` FIRST before continuing with this checklist

**Why:** Bugs in connection/manager code affect ALL modules. Extra checks needed:
- Test fix works for ALL modules (not just one)
- Verify both connection modes (persistent, direct)
- Check fork safety not broken
- Ensure no new security issues

---

## Jira Issue Verification

### 1. Check Jira Reference in PR Title

**Required format:**
```
[AAP-12345] Fix description
```

or

```
AAP-12345: Fix description  
```

**Validation:**
```bash
# Extract Jira issue from PR title
gh pr view <PR_NUMBER> --repo ansible/ansible.platform --json title \
  --jq '.title' | grep -oE 'AAP-[0-9]+'
```

**If missing:**
```markdown
❌ **Blocker:** Missing Jira issue reference in PR title

Please update the PR title to include the Jira issue:
[AAP-XXXXX] <description>
```

### 2. Verify Jira Issue Details (If Available)

**Optional checks if you have Jira access:**

- Issue exists and is valid
- Issue describes the bug being fixed
- Issue severity/priority set
- Issue is in correct status (In Progress, In Review)

---

## Bug Description Review

### 1. Read PR Description

**Required information:**

- [ ] **What was broken:** Clear description of the bug
- [ ] **How to reproduce:** Steps to trigger the bug
- [ ] **Root cause:** Why the bug occurred
- [ ] **What changed:** The fix applied
- [ ] **How verified:** Testing approach

**Example good PR description:**

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

### 2. Validate Bug Exists

**Check if you can understand the bug from description:**

- [ ] Bug scenario is clear
- [ ] Root cause makes sense
- [ ] Fix addresses root cause (not just symptoms)

**If unclear:**
```markdown
⚠️ **Question:** Can you provide more details on how to reproduce this bug?

Current description doesn't include clear reproduction steps. This makes it
difficult to verify the fix addresses the root cause.
```

---

## Regression Test Verification

**Critical requirement:** Bugfix MUST include a test that would have caught the bug.

### 1. Check Test Type

**Three options (in order of preference):**

#### Option 1: Unit Test (Preferred)

**When:** Bug is in testable code path (transform logic, utilities, etc.)

**Location:** `tests/unit/`

**Example:**
```python
# tests/unit/plugins/plugin_utils/manager/test_vault_credentials.py

def test_vault_credentials_converted_to_strings():
    """Test that vaulted credentials are converted to str before Popen."""
    
    # Create vaulted credentials
    vaulted_username = MockAnsibleVaultEncryptedUnicode("admin")
    vaulted_password = MockAnsibleVaultEncryptedUnicode("secret")
    
    # ... test that str() is called before Popen
```

**Checklist:**

- [ ] Test file name clearly indicates what it tests
- [ ] Test name starts with `test_` and describes bug scenario
- [ ] Test uses mock/fixture to reproduce bug conditions
- [ ] Test would FAIL on code before fix
- [ ] Test PASSES on code after fix
- [ ] Docstring explains the bug being tested

#### Option 2: Molecule Test Scenario

**When:** Bug requires full module execution with mock server

**Location:** `extensions/molecule/<module>_mock/converge.yml`

**Example:**
```yaml
# New scenario for vault credentials bug
- name: Test with vaulted credentials (regression test for AAP-XXXXX)
  ansible.platform.organization:
    aap_username: "{{ lookup('ansible.builtin.vault', 'admin') }}"
    aap_password: "{{ lookup('ansible.builtin.vault', 'secret') }}"
    name: "Test Org"
    state: present
  register: result

- name: Verify vault credentials work
  assert:
    that:
      - not result.failed
```

**Checklist:**

- [ ] Test scenario added to existing molecule suite
- [ ] Scenario name references Jira issue or bug
- [ ] Test reproduces bug conditions
- [ ] Test passes after fix

#### Option 3: Integration Test

**When:** Bug only appears with live AAP instance

**Location:** `tests/integration/targets/<module>s_test/tasks/`

**Example:**
```yaml
# Add to existing integration test
- name: Test specific bug scenario (AAP-XXXXX regression)
  ansible.platform.foo:
    # ... parameters that trigger the bug
  register: result

- name: Verify bug is fixed
  assert:
    that:
      - result is success
      - result.changed
```

**Checklist:**

- [ ] Integration test can be deferred to follow-up PR
- [ ] If added, references Jira issue
- [ ] Tests specific bug condition

### 2. Verify Test Adequacy

**Questions to ask:**

- [ ] Would this test have FAILED before the fix?
- [ ] Does the test cover the exact bug scenario?
- [ ] Is the test stable (not flaky)?
- [ ] Does the test assertion verify the fix, not just "didn't crash"?

**Red flags:**

```python
# ❌ BAD: Test just checks it doesn't fail
def test_vault_fix():
    result = do_something()
    assert result is not None  # Too vague!

# ✅ GOOD: Test verifies specific behavior
def test_vault_credentials_converted_to_strings():
    # Verify str() conversion happens
    assert isinstance(cmd[5], str)
    assert type(cmd[5]) == str  # Not just str subclass
    assert cmd[5] == "admin"  # Value is correct
```

---

## Code Review: The Fix

### 1. Verify Fix Location

**Check if fix is in correct place:**

- [ ] Fix is in the file identified as root cause
- [ ] Fix is minimal (doesn't refactor unrelated code)
- [ ] Fix doesn't introduce new complexity

**Example review:**

```python
# BEFORE (buggy)
cmd = [
    sys.executable,
    gateway_config.username,  # ❌ Vault object
]

# AFTER (fixed)
cmd = [
    sys.executable,
    str(gateway_config.username),  # ✅ Converted to str
]
```

**Checklist:**

- [ ] Fix addresses root cause
- [ ] No unnecessary changes
- [ ] No commented-out debug code left behind

### 2. Check for Similar Bugs

**Scan for same pattern elsewhere:**

```bash
# Example: If bug was missing str() conversion, search for similar
grep -r "subprocess.Popen" plugins/ | grep -v "str("

# Example: If bug was missing null check, search for similar
grep -r "\.get(" plugins/ | grep -v "if .* is not None"
```

**Ask:**
- [ ] Could this bug exist in other modules?
- [ ] Should we fix them in this PR or create follow-up issues?

**If found:**

```markdown
⚠️ **Note:** Similar pattern found in other files

Found similar subprocess.Popen usage without str() conversion in:
- `plugins/foo/bar.py:123`
- `plugins/baz/qux.py:456`

**Recommendation:** 
- Fix in this PR (same root cause) OR
- Create follow-up Jira issue to track
```

### 3. Backwards Compatibility

**Ensure fix doesn't break existing behavior:**

- [ ] Fix handles both old and new scenarios
- [ ] No breaking changes to public API
- [ ] Existing tests still pass

**Example check:**

```python
# ✅ GOOD: Handles both vaulted and non-vaulted
str(gateway_config.username)  # Works for both str and VaultString

# ❌ BAD: Breaks existing behavior
if isinstance(gateway_config.username, AnsibleVaultEncryptedUnicode):
    username = str(gateway_config.username)
else:
    username = gateway_config.username  # Doesn't handle None!
```

---

## Documentation Updates

### 1. Changelog Fragment

**Required format:**

```yaml
# changelogs/fragments/<pr_number>-<bug_name>.yml
bugfixes:
  - "Fix description of what was broken (ansible/ansible.platform#<PR>)."
```

**Example:**

```yaml
# changelogs/fragments/250-vault-credentials.yml
bugfixes:
  - "Fix subprocess spawn failure when aap_username or aap_password are vaulted (ansible/ansible.platform#250)."
```

**Checklist:**

- [ ] Fragment file exists
- [ ] Uses `bugfixes:` category (not `minor_changes:`)
- [ ] Description is clear and user-facing
- [ ] PR number referenced
- [ ] Past tense ("Fix", not "Fixes")

### 2. Known Issues / Release Notes

**If bug was in a released version:**

```markdown
⚠️ **Note:** This bug affects released versions

**Affected versions:** 2.5.0, 2.6.0  
**Workaround:** Use non-vaulted credentials or `| string` filter

**Recommendation:** Add note to release notes for backport PR
```

### 3. Documentation Clarification

**If bug revealed unclear docs:**

```markdown
💡 **Suggestion:** Update documentation

This bug suggests the documentation about vault support could be clearer.

**Consider adding to docs:**
- Vault is supported for all authentication parameters
- No special configuration needed (fixed in 2.7.0+)
```

---

## Testing Strategy

### 1. Manual Testing (If Applicable)

**For complex bugs, verify manual testing was done:**

```markdown
**Manual testing performed:**
- [ ] Created vaulted group_vars/all.yml
- [ ] Ran playbook with vaulted credentials
- [ ] Verified module execution succeeds
- [ ] Verified no error in logs
```

### 2. CI Test Execution

**Ensure tests pass:**

```bash
# Run unit tests
pytest tests/unit -v -k <test_name>

# Run molecule tests
molecule test -s <scenario>

# Run sanity
ansible-test sanity <changed_file> --docker
```

---

## Review Output Template

```markdown
## Bugfix Review: #<PR_NUMBER>

### Jira Reference

- ✅ Jira issue: AAP-12345
- ✅ Issue in PR title

### Bug Description

**What was broken:** Vaulted credentials cause subprocess failure

**Root cause:** Missing str() conversion before Popen

**Fix applied:** Convert credentials to str()

✅ Bug description is clear and complete

### Regression Test

- ✅ **Test type:** Unit test
- ✅ **Location:** `tests/unit/plugins/plugin_utils/manager/test_vault_credentials.py`
- ✅ **Test coverage:** 
  - Vaulted username
  - Vaulted password
  - Vaulted base_url
  - None values
- ✅ **Test quality:** Would have caught the bug

### Code Review

- ✅ Fix in correct location: `process_manager.py:293-306`
- ✅ Minimal change (only affected lines)
- ✅ No similar bugs found elsewhere
- ✅ Backwards compatible

### Documentation

- ✅ Changelog fragment: `changelogs/fragments/250-vault-fix.yml`
- ✅ Correct category: `bugfixes`
- ✅ Clear description

### Blockers

None

### Recommendations

1. ✅ All requirements met
2. Consider adding note to docs about vault support

### Verdict

✅ **APPROVE** - Ready for `safe to test` label

Well-documented fix with comprehensive regression test. Addresses root cause without introducing new issues.
```

---

## Common Bugfix Patterns

### Pattern 1: Missing Null/None Check

**Bug:**
```python
# Crashes when value is None
result = some_value.upper()
```

**Fix:**
```python
# Safe
result = some_value.upper() if some_value else None
```

**Required test:**
```python
def test_handles_none_value():
    assert handle_value(None) is None  # Doesn't crash
```

### Pattern 2: Type Conversion Missing

**Bug:**
```python
# Fails with AnsibleVaultEncryptedUnicode
subprocess.Popen([sys.executable, password])
```

**Fix:**
```python
# Convert to str first
subprocess.Popen([sys.executable, str(password)])
```

**Required test:**
```python
def test_converts_vault_to_string():
    vault_str = MockAnsibleVaultEncryptedUnicode("secret")
    # Verify str() is called
```

### Pattern 3: Incorrect Conditional Logic

**Bug:**
```python
# Wrong operator
if resource.state == "present" or "enforced":  # Always True!
```

**Fix:**
```python
# Correct
if resource.state in ("present", "enforced"):
```

**Required test:**
```python
def test_state_conditional():
    assert check_state("absent") is False
    assert check_state("present") is True
    assert check_state("enforced") is True
```

### Pattern 4: Missing Error Handling

**Bug:**
```python
# Doesn't handle API errors
result = api_client.get(url)
return result["data"]  # KeyError if error response
```

**Fix:**
```python
# Handle errors
try:
    result = api_client.get(url)
    return result.get("data", [])
except APIError as e:
    module.fail_json(msg=f"API error: {e}")
```

**Required test:**
```python
def test_handles_api_error():
    with pytest.raises(AnsibleFailJson):
        handle_api_response({"error": "Not found"})
```

---

## Red Flags

**Request changes if:**

- ❌ No regression test included
- ❌ Fix doesn't address root cause (just hides symptoms)
- ❌ Fix introduces breaking changes
- ❌ Similar bugs found but not fixed
- ❌ Test wouldn't have caught the bug
- ❌ Missing Jira reference
- ❌ No changelog fragment

**Approve with recommendations if:**

- ✅ All requirements met
- ⚠️ Could add more test coverage (but basic covered)
- ⚠️ Documentation could be clearer (but not wrong)

---

**Last Updated:** 2026-09-11
