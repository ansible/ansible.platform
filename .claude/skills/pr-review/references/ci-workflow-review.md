# CI/Workflow PR Review Guide

Review checklist for CI, GitHub Actions, and workflow changes.

## When to Use

- PR title starts with `ci:`, `chore:`, or `build:`
- PR modifies `.github/workflows/`
- PR modifies CI configuration files
- PR modifies test infrastructure

---

## Critical Checks (High Priority)

**For NEW workflows:**
1. ✅ **Purpose justified** - Why new vs modifying existing?
2. ✅ **Tested in fork** - MUST be tested before merge
3. ✅ **Secret protection** - If secrets used, proper gates in place

**For ALL workflow changes:**
1. ✅ **Security review** - No injection vulnerabilities
2. ✅ **Secret protection** - Secrets not exposed to untrusted code
3. ✅ **Permissions** - Follow least-privilege principle

**Quick secret protection check:**
```bash
# Does workflow use secrets AND run on pull_request?
grep -l "secrets\." .github/workflows/*.yml | \
  xargs grep -l "on: pull_request" && \
  echo "⚠️ DANGER: Secrets exposed to fork PRs!"

# Should use pull_request_target + label gate instead
grep -l "safe to test" .github/workflows/*.yml
```

---

## Workflow File Changes

### 1. GitHub Actions Workflow Review

**Files to check:**
```
.github/workflows/
├── ci.yml                  # Main CI pipeline
├── integration.yml         # Integration tests (safe to test)
├── release.yml            # Release automation
└── ...
```

**First, check if this is a NEW workflow:**

```bash
# List all workflows before PR
git diff origin/devel --name-only | grep '.github/workflows/'

# Check if file is new (Added)
git diff origin/devel --name-status .github/workflows/ | grep '^A'
```

**If NEW workflow detected, additional checks required:**

- [ ] **Purpose justified** - Why is a new workflow needed vs modifying existing?
- [ ] **Name follows convention** - Descriptive, matches collection patterns
- [ ] **No duplication** - Doesn't replicate existing workflow functionality
- [ ] **Documented in PR** - Clear explanation of what it does and why
- [ ] **Minimal scope** - Does one thing well, not overloaded
- [ ] **Tested in fork** - MUST be tested before merge (see Fork Testing section)

**For each modified or new workflow:**

#### 1.1 Syntax and Structure

```bash
# Validate workflow YAML syntax
yamllint .github/workflows/<workflow>.yml

# Check GitHub Actions syntax
gh workflow view <workflow-name> --repo ansible/ansible.platform
```

**Checklist:**

- [ ] Valid YAML syntax
- [ ] Workflow name is clear and descriptive
- [ ] Trigger conditions are appropriate
- [ ] Jobs are properly defined
- [ ] Steps are in logical order

#### 1.2 Trigger Conditions

**Common triggers:**

```yaml
# ✅ GOOD: Specific, intentional triggers
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

# ❌ BAD: Too broad, wastes CI resources
on: [push, pull_request]  # Runs on every push to any branch
```

**Checklist:**

- [ ] Triggers are specific (not too broad)
- [ ] Path filters used when appropriate
- [ ] Branch filters protect main branches
- [ ] No unnecessary workflow runs

#### 1.3 Permissions

```yaml
# ✅ GOOD: Minimal required permissions
permissions:
  contents: read
  pull-requests: write  # Only if needed

# ❌ BAD: Excessive permissions
permissions: write-all  # Never use this
```

**Checklist:**

- [ ] Permissions follow least-privilege principle
- [ ] Only grants what's needed for the workflow
- [ ] No `write-all` permission

#### 1.4 Security Review

**Check for security issues:**

```yaml
# ❌ DANGEROUS: Untrusted input in shell
- name: Run command
  run: echo "${{ github.event.issue.title }}"  # Injection risk!

# ✅ SAFE: Use environment variables
- name: Run command
  env:
    TITLE: ${{ github.event.issue.title }}
  run: echo "$TITLE"

# ❌ DANGEROUS: pull_request_target with untrusted code
on: pull_request_target  # Runs with repo secrets
# Then:
- uses: actions/checkout@v4
  with:
    ref: ${{ github.event.pull_request.head.sha }}  # Untrusted code!

# ✅ SAFE: Use pull_request or validate first
on: pull_request  # No repo secrets exposed
```

**Security checklist:**

- [ ] No direct use of `github.event.*` in shell commands
- [ ] `pull_request_target` used carefully (or not at all)
- [ ] Secrets not logged or exposed
- [ ] Third-party actions pinned to SHA (not `@main`)
- [ ] No `curl | sh` or similar dangerous patterns

#### 1.5 Secret Protection

**Critical: Verify secrets are protected from untrusted code**

**Rule 1: Never expose secrets to PRs from forks**

```yaml
# ❌ DANGEROUS: Secrets available to fork PRs
on: pull_request  # From any fork!
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
      - run: |
          echo "${{ secrets.AAP_PASSWORD }}"  # LEAKED to fork!

# ✅ SAFE: Use pull_request_target with label gate
on:
  pull_request:
    types: [labeled]

jobs:
  integration:
    if: |
      github.event.label.name == 'safe to test' &&
      github.event.pull_request.author_association == 'MEMBER'
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - run: |
          echo "Secrets only after manual approval"
        env:
          AAP_PASSWORD: ${{ secrets.AAP_PASSWORD }}
```

**Rule 2: Check secret visibility in workflow runs**

```bash
# Verify secrets are masked in logs
# Check recent workflow runs
gh run view <RUN_ID> --repo ansible/ansible.platform --log | grep -i password
# Should show: ***  (masked)
# Should NOT show: actual password value
```

**Rule 3: Validate secret references**

```yaml
# ✅ GOOD: Secrets in env vars, not inline
- name: Deploy
  env:
    API_TOKEN: ${{ secrets.GALAXY_API_TOKEN }}
  run: ansible-galaxy collection publish --token "$API_TOKEN"

# ❌ BAD: Secret in command (shows in process list)
- name: Deploy
  run: ansible-galaxy collection publish --token ${{ secrets.GALAXY_API_TOKEN }}
```

**Secret protection checklist:**

- [ ] **No secrets on pull_request trigger** (use `pull_request_target` + label gate)
- [ ] **Label gate implemented** - `safe to test` or similar for secret access
- [ ] **Author association check** - Verify `MEMBER`, `COLLABORATOR`, or `OWNER`
- [ ] **Secrets in env vars** - Not directly in shell commands
- [ ] **No secret logging** - Verify secrets are masked in test runs
- [ ] **No secret in artifacts** - Don't upload logs/files containing secrets
- [ ] **Secret rotation documented** - If secrets compromised, how to rotate

**Example: Safe secret usage pattern**

```yaml
name: Integration Tests (Safe to Test)

on:
  pull_request:
    types: [labeled]

jobs:
  check-access:
    # First job: verify access
    if: |
      github.event.label.name == 'safe to test' &&
      (github.event.pull_request.author_association == 'MEMBER' ||
       github.event.pull_request.author_association == 'OWNER')
    runs-on: ubuntu-latest
    outputs:
      approved: ${{ steps.check.outputs.approved }}
    steps:
      - id: check
        run: echo "approved=true" >> $GITHUB_OUTPUT

  integration:
    needs: check-access
    if: needs.check-access.outputs.approved == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      
      - name: Run tests with secrets
        env:
          AAP_HOSTNAME: ${{ secrets.AAP_HOSTNAME }}
          AAP_USERNAME: ${{ secrets.AAP_USERNAME }}
          AAP_PASSWORD: ${{ secrets.AAP_PASSWORD }}
        run: |
          # Secrets are now available, but only after manual approval
          ansible-playbook tests/integration/playbook.yml
```

**Verify secret protection:**

```bash
# 1. Check if workflow runs on pull_request (dangerous)
grep -n "on: pull_request" .github/workflows/*.yml

# 2. Check if secrets used without protection
grep -A 5 "secrets\." .github/workflows/*.yml | grep -v "pull_request_target"

# 3. Check for label gates
grep -n "safe to test" .github/workflows/*.yml
```

#### 1.6 Dependencies and Actions

```yaml
# ✅ GOOD: Pinned to specific version
- uses: actions/checkout@8e5e7e5ab8b370d6c329ec480221332ada57f0ab  # v3.5.2

# ⚠️ ACCEPTABLE: Pinned to major version (with auto-updates)
- uses: actions/checkout@v4

# ❌ BAD: Unpinned, can break anytime
- uses: actions/checkout@main
```

**Checklist:**

- [ ] Actions pinned to SHA or major version
- [ ] No deprecated actions
- [ ] Dependencies are maintained/trustworthy
- [ ] Version comments included for pinned SHAs

---

### 2. Test Infrastructure Changes

**Files:**
```
tests/
├── test_completeness.py   # Collection completeness test
├── unit/                  # Unit test framework
├── integration/           # Integration test framework
└── ...
```

#### 2.1 Test Script Changes

**For `tests/test_completeness.py` or similar:**

**Checklist:**

- [ ] Changes maintain test intent
- [ ] New checks are justified and documented
- [ ] Test still catches real issues (not just passes blindly)
- [ ] Error messages are clear and actionable

**Example review:**

```python
# ❌ BAD: Makes test too permissive
if module_name.startswith("_"):
    continue  # Skip without justification

# ✅ GOOD: Clear intent, documented exception
if module_name in EXEMPTED_MODULES:
    # These modules are exempt because [reason]
    continue
```

#### 2.2 Molecule Test Infrastructure

**Files:**
```
extensions/molecule/
├── default/               # Shared molecule config
│   └── molecule.yml
└── <module>_mock/         # Per-module scenarios
```

**Checklist:**

- [ ] `molecule.yml` syntax valid
- [ ] Platform/driver configuration appropriate
- [ ] Dependency declarations correct
- [ ] No hardcoded secrets or credentials

#### 2.3 Integration Test Infrastructure

**Files:**
```
tests/integration/
├── integration_config.yml  # Test configuration
└── targets/
```

**Checklist:**

- [ ] Changes don't break existing tests
- [ ] New configuration is documented
- [ ] Secrets handling is secure

---

### 3. CI Configuration Files

#### 3.1 Requirements Files

**Files:**
```
requirements.txt           # Python dependencies
meta/ee-requirements.txt   # Execution environment deps
test-requirements.txt      # Test dependencies
```

**Checklist:**

- [ ] Version pins are intentional (not accidental)
- [ ] Dependencies are needed (no unused deps)
- [ ] Licenses are compatible
- [ ] Security vulnerabilities addressed

**Version pinning review:**

```txt
# ✅ GOOD: Pinned with reason
requests==2.28.1  # Later versions break X

# ⚠️ ACCEPTABLE: Minimum version
requests>=2.28.0  # Need feature X from this version

# ❌ BAD: Unintentionally too restrictive
requests==2.28.1  # Why this exact version?
```

#### 3.2 Ansible Configuration

**Files:**
```
ansible.cfg
.ansible-lint
pyproject.toml
```

**Checklist:**

- [ ] Changes are documented
- [ ] Doesn't break existing functionality
- [ ] Compatible with supported Ansible versions

---

### 4. Documentation for CI Changes

**Ensure these are updated if needed:**

- [ ] `CONTRIBUTING.md` - If workflow process changed
- [ ] `README.md` - If badges/CI status affected
- [ ] Inline comments - If workflow logic is complex
- [ ] Changelog fragment - For user-visible CI changes

**Example good documentation:**

```yaml
# This workflow runs on PRs labeled 'safe to test' to avoid
# exposing secrets to untrusted code. It runs integration tests
# against a live AAP instance provisioned in CI.
name: Integration Tests (Safe to Test)

on:
  pull_request:
    types: [labeled]

jobs:
  check-label:
    if: github.event.label.name == 'safe to test'
    # ... rest of workflow
```

---

## Review Checklist by Change Type

### Change Type: New Workflow Added

- [ ] Workflow name is descriptive
- [ ] Purpose documented (inline or in PR)
- [ ] Justified (doesn't duplicate existing workflow)
- [ ] Triggers are appropriate
- [ ] Permissions follow least-privilege
- [ ] **No security issues** (injection, untrusted input)
- [ ] **Secret protection implemented** (if secrets used)
  - [ ] No secrets on `pull_request` trigger
  - [ ] Label gate (`safe to test`) for secret access
  - [ ] Author association check
  - [ ] Secrets in env vars, not inline
- [ ] Tested in fork or with dry-run
- [ ] Monitoring plan for first few runs

### Change Type: Workflow Modified

- [ ] Change is minimal (focused)
- [ ] Doesn't break existing functionality
- [ ] Backwards compatible (or breaking change justified)
- [ ] Comments explain complex logic

### Change Type: Workflow Removed

- [ ] Removal is justified
- [ ] No dependencies on removed workflow
- [ ] Documented in changelog if user-visible

### Change Type: Test Infrastructure

- [ ] Tests still pass
- [ ] Test coverage maintained or improved
- [ ] No tests disabled without justification
- [ ] Test matrix appropriate (not too broad/narrow)

### Change Type: Dependency Update

- [ ] Security vulnerability fixed OR
- [ ] Feature needed OR
- [ ] Bug fixed
- [ ] Breaking changes documented
- [ ] Tests verify compatibility

---

## Common CI/Workflow Patterns

### Pattern 1: Safe to Test Workflow

**Purpose:** Run integration tests only after manual approval

**Key elements:**

```yaml
on:
  pull_request:
    types: [labeled]

jobs:
  integration:
    if: github.event.label.name == 'safe to test'
    runs-on: ubuntu-latest
    steps:
      # ...
```

**Review checklist:**

- [ ] Label name is correct
- [ ] Only runs when label present
- [ ] Removes label after run (or on failure)

### Pattern 2: Matrix Testing

**Purpose:** Test across multiple Python/Ansible versions

```yaml
strategy:
  matrix:
    python-version: ['3.9', '3.10', '3.11']
    ansible-version: ['2.14', '2.15', '2.16']
```

**Review checklist:**

- [ ] Matrix is necessary (not excessive)
- [ ] Versions are supported combinations
- [ ] Fast-fail appropriate (`fail-fast: false` if needed)

### Pattern 3: Conditional Steps

```yaml
- name: Run only on devel
  if: github.ref == 'refs/heads/devel'
  run: echo "Devel only"

- name: Run only on PR
  if: github.event_name == 'pull_request'
  run: echo "PR only"
```

**Review checklist:**

- [ ] Conditions are correct
- [ ] Logic is clear and documented
- [ ] No unintended side effects

---

## Testing CI Changes

### 1. Fork Testing

**Before approving:**

```markdown
**Testing request:**

Please test this workflow in your fork:

1. Push this branch to your fork
2. Create a PR in your fork
3. Verify workflow runs as expected
4. Share workflow run URL
```

### 2. Dry-Run Testing

```bash
# For workflow changes, can use act locally
act pull_request -W .github/workflows/<workflow>.yml

# Or review with GitHub CLI
gh workflow view <workflow> --repo ansible/ansible.platform
```

### 3. Incremental Rollout

**For risky changes:**

```markdown
**Recommendation:** Incremental rollout

1. Merge this PR to enable workflow
2. Monitor first few runs
3. If issues, can quickly disable with follow-up PR
4. Add monitoring/alerting if critical workflow
```

---

## Review Output Template

```markdown
## CI/Workflow Review: #<PR_NUMBER>

### Change Summary

**Type:** [New Workflow | Workflow Modification | Dependency Update | Test Infrastructure]

**Files Modified:**
- `.github/workflows/ci.yml` - Added Python 3.12 to matrix
- `requirements.txt` - Updated requests to 2.31.0

### Security Review

- ✅ No untrusted input in shell commands
- ✅ Permissions follow least-privilege
- ✅ Actions pinned to versions
- ✅ No secret exposure risk

### Functionality Review

- ✅ Workflow triggers appropriate
- ✅ Test matrix reasonable (Python 3.9-3.12)
- ✅ Backwards compatible
- ✅ Error handling adequate

### Testing

- ✅ Tested in fork: https://github.com/user/repo/actions/runs/123
- ✅ Workflow syntax valid
- ⚠️ Recommend monitoring first few runs after merge

### Documentation

- ✅ Inline comments explain complex logic
- ⚠️ Consider updating CONTRIBUTING.md with new Python version

### Blockers

None

### Recommendations

1. ✅ Changes look good
2. ⚠️ Monitor first runs after merge
3. 💡 Consider adding workflow_dispatch for manual testing

### Verdict

✅ **APPROVE** - Safe to merge

Security reviewed, tested in fork, no issues found.
```

---

## Red Flags

**Request changes if:**

- ❌ Security issues (untrusted input, excessive permissions)
- ❌ Workflow will waste CI resources (too broad triggers)
- ❌ Breaking change without justification
- ❌ Not tested in fork
- ❌ Removes critical tests without replacement

**Approve with warnings if:**

- ✅ Functionally correct
- ⚠️ Could be more efficient (but works)
- ⚠️ Documentation could be better (but not wrong)
- ⚠️ Needs monitoring (but safe to try)

---

## Post-Merge Monitoring

**For approved CI changes:**

```markdown
## Post-Merge Checklist

After this PR merges, monitor:

1. **First workflow run:** Check logs for unexpected errors
2. **CI dashboard:** Ensure no increase in failure rate
3. **Performance:** Check if CI time increased significantly
4. **Costs:** Monitor GitHub Actions minutes usage

**If issues found:**
- Revert quickly if critical
- File follow-up issue if minor
- Adjust workflow if efficiency problem
```

---

## Quick Reference: Review Commands

### Check for New Workflows

```bash
# List new workflow files in PR
git diff origin/devel --name-status .github/workflows/ | grep '^A'

# Show new workflow content
git diff origin/devel .github/workflows/<new-workflow>.yml
```

### Secret Protection Audit

```bash
# CRITICAL: Find workflows with secrets on pull_request trigger
echo "=== DANGEROUS: Secrets exposed to pull_request ==="
for f in .github/workflows/*.yml; do
  if grep -q "on: pull_request" "$f" && grep -q "secrets\." "$f"; then
    echo "❌ $f - Secrets exposed to fork PRs!"
  fi
done

# Find workflows with safe to test label gate
echo "=== SAFE: Label-gated workflows ==="
grep -l "safe to test" .github/workflows/*.yml

# Check for author association checks
echo "=== Author association protection ==="
grep -l "author_association" .github/workflows/*.yml

# Verify secrets are in env vars, not inline
echo "=== Secrets in commands (UNSAFE) ==="
grep -n '\${{ secrets\.' .github/workflows/*.yml | grep -v 'env:'
```

### Workflow Validation

```bash
# Validate YAML syntax
yamllint .github/workflows/<workflow>.yml

# Check GitHub Actions syntax (requires gh CLI)
gh workflow view <workflow-name> --repo ansible/ansible.platform

# Test locally with act (if available)
act pull_request -W .github/workflows/<workflow>.yml --dryrun
```

### Permission Review

```bash
# Find workflows with write-all (DANGEROUS)
grep -n "write-all" .github/workflows/*.yml

# List all permission declarations
grep -A 5 "permissions:" .github/workflows/*.yml
```

### Trigger Review

```bash
# Find all pull_request triggers (check if secrets used)
grep -n "on: pull_request" .github/workflows/*.yml

# Find all pull_request_target triggers (verify safety)
grep -n "pull_request_target" .github/workflows/*.yml

# Check for workflow_dispatch (manual triggers)
grep -n "workflow_dispatch" .github/workflows/*.yml
```

---

**Last Updated:** 2026-09-11
