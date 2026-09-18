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

#### 2.3 Sanity Tests (**STRICT** - Must Pass)

```bash
# Check sanity test failures
gh run view <RUN_ID> --repo ansible/ansible.platform --log | \
  grep -A 20 "ansible-test sanity"
```

**Common issues (ALL BLOCKING):**
- Documentation validation (malformed DOCUMENTATION)
- Import validation (unused imports, missing __init__.py)
- PEP8 violations (line length, indentation)
- ansible-lint violations
- yamllint violations
- pep8 formatting issues

**STRICT ENFORCEMENT:**
- ❌ **BLOCK** PR if ANY sanity test fails
- ❌ **BLOCK** PR if ruff linting fails
- ❌ **BLOCK** PR if yamllint fails
- Request specific fixes with line numbers and exact errors

#### 2.4 Linting Checks (**STRICT** - Must Pass)

```bash
# Check ruff linting
gh run view <RUN_ID> --repo ansible/ansible.platform --log | \
  grep -A 20 "ruff check"

# Check yamllint
gh run view <RUN_ID> --repo ansible/ansible.platform --log | \
  grep -A 20 "yamllint"
```

**STRICT ENFORCEMENT:**
- ❌ **BLOCK** PR for unused imports
- ❌ **BLOCK** PR for undefined names
- ❌ **BLOCK** PR for formatting issues (use `ruff format`)
- ❌ **BLOCK** PR for YAML syntax errors
- Provide exact file:line references for each violation

#### 2.5 JIRA Integration

**Check:** Jira issue reference in PR title or body

**Format:** `[AAP-XXXXX]` or `AAP-XXXXX` or `ANSTRAT-XXXXX`

**ENFORCEMENT:**
- ❌ **BLOCKING for bugfix PRs** (`fix:`) - JIRA is **MANDATORY**
- ⚠️ **Recommended for feature PRs** (`feat:`) - Request but don't block
- ✅ **Optional for docs/CI PRs**

**If missing on bugfix:**
```markdown
❌ **BLOCKER: Missing JIRA reference**

Bugfix PRs must reference a JIRA issue (AAP-XXXXX or ANSTRAT-XXXXX).
Please add the JIRA reference to the PR title or description.
```

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

**STRICT Prerequisites for `safe to test` label (ALL MUST PASS):**

- ✅ Collection completeness test passing (**BLOCKING**)
- ✅ Unit tests passing (**BLOCKING**)
- ✅ Sanity tests passing - ALL checks (**BLOCKING**)
- ✅ Ruff linting passing - zero violations (**BLOCKING**)
- ✅ Yamllint passing - zero violations (**BLOCKING**)
- ✅ Changelog fragment present (if code changes) (**BLOCKING**)
- ✅ JIRA issue referenced (**BLOCKING for bugfixes**, recommended for features)
- ✅ No security issues (**BLOCKING**)

**Decision:**

| Status | Action |
|--------|--------|
| All prerequisites met | ✅ **Ready for `safe to test`** |
| **ANY** pre-merge check failing | ❌ **BLOCK - Request fixes** |
| Linting violations present | ❌ **BLOCK - Must be zero violations** |
| Sanity test failures | ❌ **BLOCK - All must pass** |
| Bugfix missing JIRA | ❌ **BLOCK - JIRA mandatory** |
| Docs-only PR (no code changes) | ✅ **Can merge without label** |

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

### Pre-Merge CI Checks (STRICT - All Must Pass)

- [x] Collection completeness: ✅ Passing
- [ ] Unit tests: ❌ 2 failures (see details below) **BLOCKING**
- [x] Sanity tests: ✅ Passing
- [x] Ruff linting: ✅ Zero violations
- [x] Yamllint: ✅ Zero violations  
- [x] Changelog: ✅ Present
- [x] JIRA reference: ✅ AAP-12345 (required for bugfixes)

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

**Start here:** `references/common-patterns.md` - Shared validation patterns and code references

**PR-type specific:**
- `references/feature-review.md` - Seven-file pattern, architecture compliance
- `references/bugfix-review.md` - Regression test requirements
- `references/ci-workflow-review.md` - CI/workflow specific checks
- `references/connection-manager-review.md` - Core infrastructure (CRITICAL)

---

**Last Updated:** 2026-09-17
**Changes:**
- Added strict linting and sanity enforcement
- Made JIRA mandatory for bugfixes
- Added common-patterns.md to reduce context consumption
- Refactored references to point to real code examples
