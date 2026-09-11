---
name: pr-review
description: >-
  Reviews pull requests in ansible.platform collection as a maintainer.
  Checks CI failures, architecture compliance, and routes to appropriate
  review workflow (feature, bugfix, or CI/workflow).
user-invocable: true
---

# ansible.platform PR Review

Reviews PRs as a collection maintainer following ansible.platform standards.

## Usage

```bash
/pr-review <PR_NUMBER>
```

## Overview

This skill performs a structured PR review with these priorities:

1. **Pre-merge CI checks** (must pass BEFORE `safe to test`)
   - Collection completeness test
   - Unit tests
   - Sanity tests
   
2. **Route to specific review type:**
   - Feature PR → `references/feature-review.md`
   - Bugfix PR → `references/bugfix-review.md`
   - CI/workflow PR → `references/ci-workflow-review.md`

3. **Safe-to-test readiness** (after fixes)

4. **Post-label CI monitoring** (integration tests)

---

## Workflow

### Step 1: Fetch PR Information

```bash
gh pr view <PR_NUMBER> --repo ansible/ansible.platform \
  --json title,body,author,files,statusCheckRollup,labels
```

**Extract:**
- PR type from title: `feat:`, `fix:`, `ci:`, `refactor:`, `docs:`
- Files changed count
- CI check status
- Jira issue reference

---

### Step 2: Pre-Merge CI Checks (BEFORE safe-to-test)

**These must pass before applying `safe to test` label:**

#### 2.1 Collection Completeness Test

**Purpose:** Ensures new modules are registered in `meta/runtime.yml`

```bash
# If failing, get error details
gh run view <RUN_ID> --repo ansible/ansible.platform --log | \
  grep -A 10 "collection completeness"
```

**Common failure:**
```
The following items should be added to meta/runtime.yml action-groups.gateway:
    <module_name>
```

**Fix:**
```diff
# meta/runtime.yml
action_groups:
  gateway:
+   - <module_name>
    - application
```

**Why it matters:** Enables `module_defaults` for `group/ansible.platform.gateway`

#### 2.2 Unit Tests

```bash
# Check unit test failures
gh run view <RUN_ID> --repo ansible/ansible.platform --log | \
  grep -A 20 "pytest"
```

**Review:**
- Assertion failures
- Import errors
- Test coverage for changed code

#### 2.3 Sanity Tests

```bash
# Check sanity test failures
gh run view <RUN_ID> --repo ansible/ansible.platform --log | \
  grep -A 20 "ansible-test sanity"
```

**Common issues:**
- Documentation validation (malformed DOCUMENTATION)
- Import validation
- PEP8 violations

#### 2.4 DVCS Integration (Non-blocking)

**Check:** Jira issue reference in PR title

**Format:** `[AAP-XXXXX]` or `AAP-XXXXX`

**If missing:** Request Jira reference (but not a blocker)

---

### Step 3: Changelog Verification

**Check if changelog needed:**

```bash
# Changed files that require changelog
- plugins/**/*.py → YES
- tests/**/*.py → YES
- docs/**/*.md → NO (docs-only)
- .github/**/*.yml → NO (CI-only)
```

**Verify changelog exists:**
```bash
ls changelogs/fragments/ | grep -E "<pr_number>|<feature_name>"
```

**Validate format:**
```yaml
# For features
minor_changes:
  - "Short description (ansible/ansible.platform#<PR>)."

# For bugfixes
bugfixes:
  - "Fix description (ansible/ansible.platform#<PR>)."
```

---

### Step 4: Route to Specific Review

**FIRST: Check if PR touches core infrastructure (connection/manager):**

```bash
# Check for connection or manager changes
git diff origin/devel --name-only | grep -E \
  'plugins/connection/|plugins/plugin_utils/manager/|plugins/plugin_utils/platform/(base_client|direct_client|config|registry)'
```

**If connection/manager files changed:**
→ **CRITICAL:** Read `references/connection-manager-review.md` FIRST (regardless of PR type)

**Then, based on PR type, read appropriate reference:**

| PR Type | Reference File | When to Use |
|---------|---------------|-------------|
| `feat:` | `references/feature-review.md` | New module, new feature |
| `fix:` | `references/bugfix-review.md` | Bug fix, regression fix |
| `ci:` | `references/ci-workflow-review.md` | CI, GitHub Actions, workflow changes |
| `refactor:` | `references/feature-review.md` | Code refactoring (use feature checklist) |
| `docs:` | Skip to Step 6 | Documentation only |
| **Connection/Manager** | `references/connection-manager-review.md` | Core infrastructure changes |

**Read the reference file and follow its checklist.**

---

### Step 5: Determine Safe-to-Test Readiness

**Prerequisites for `safe to test` label:**

- ✅ Collection completeness test passing
- ✅ Unit tests passing
- ✅ Sanity tests passing
- ✅ Changelog fragment present (if code changes)
- ✅ Jira issue referenced (recommended)
- ✅ No obvious security issues

**Decision:**

| Status | Action |
|--------|--------|
| All prerequisites met | ✅ **Ready for `safe to test`** |
| Any pre-merge check failing | ❌ **Request fixes first** |
| Docs-only PR | ✅ **Can merge without label** |

---

### Step 6: Post-Label Monitoring (After safe-to-test applied)

**Once `safe to test` label is applied, integration tests run:**

```bash
# Monitor CI
gh pr checks <PR_NUMBER> --repo ansible/ansible.platform --watch
```

**Integration test failures:**
- AAP connectivity issues (transient → re-run)
- Resource creation failures (check required fields)
- Timeout errors (check wait/polling logic)  
- 404 errors (wrong endpoint path in mixin)

**Re-run transient failures:**
```bash
gh run rerun <RUN_ID> --repo ansible/ansible.platform --failed
```

---

### Step 7: Post Review

**Use template based on findings:**

```markdown
## PR Review: #<PR_NUMBER>

**Type:** [Feature|Bugfix|CI/Workflow|Docs]  
**Files Changed:** X files  
**CI Status:** [✅ All Green|❌ N Failing|⏳ Pending]

### Pre-Merge CI Checks

- [x] Collection completeness: ✅ Passing
- [ ] Unit tests: ❌ 2 failures (see details below)
- [x] Sanity tests: ✅ Passing
- [x] Changelog: ✅ Present

### Architecture Review (Features Only)

[See feature-review.md checklist results]

### Blockers

1. **Unit test failures**
   - File: `tests/unit/plugins/plugin_utils/api/v1/test_foo.py:42`
   - Issue: Assertion failed - expected 'bar', got 'baz'
   - Fix: Update test expectation to match implementation

2. **Missing meta/runtime.yml entry**
   ```diff
   action_groups:
     gateway:
   +   - foo
   ```

### Safe-to-Test Status

**Status:** ❌ **NOT READY**

**Reason:** Unit tests failing

**Next Steps:**
1. Fix unit test failures
2. Push changes
3. Re-review
4. Apply `safe to test` label

### Final Verdict

**⚠️ REQUEST CHANGES**

Please address the blockers above. Once fixed, I'll re-review and we can proceed with integration testing.
```

**Post review:**
```bash
# Request changes
gh pr review <PR_NUMBER> --repo ansible/ansible.platform \
  --request-changes --body "$(cat review.md)"

# Approve (after all checks pass)
gh pr review <PR_NUMBER> --repo ansible/ansible.platform \
  --approve --body "LGTM! All checks passing."
```

---

## Quick Reference

### CI Check Priority

1. **Pre-merge (MUST pass before `safe to test`):**
   - Collection completeness ← **Run FIRST**
   - Unit tests
   - Sanity tests
   - Changelog verification

2. **Post-label (triggered BY `safe to test`):**
   - Integration tests (live AAP)

### PR Type Detection

```
feat: → Feature review
fix: → Bugfix review
ci: → CI/workflow review
docs: → Skip to safe-to-test check
refactor: → Feature review (architecture check)
```

### Common Fixes

**Collection completeness failure:**
→ Add module to `meta/runtime.yml`

**Missing changelog:**
→ Create `changelogs/fragments/<pr>-<name>.yml`

**Integration test failures:**
→ Check if transient, re-run if needed

---

## Reference Files

- `references/feature-review.md` - Seven-file pattern, architecture compliance
- `references/bugfix-review.md` - Regression test requirements
- `references/ci-workflow-review.md` - CI/workflow specific checks

---

**Last Updated:** 2026-09-11  
**Based on:** PR #227 review experience
