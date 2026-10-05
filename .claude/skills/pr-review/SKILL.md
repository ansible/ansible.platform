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

## Workflow

### 1. Fetch PR Info

```bash
gh pr view <PR_NUMBER> --repo ansible/ansible.platform \
  --json title,body,author,files,statusCheckRollup,labels
```

Extract: PR type, files changed, CI status, JIRA reference

### 2. Pre-Merge CI Checks (STRICT - Must Pass BEFORE safe-to-test)

**ALL must pass:**
- ✅ Collection completeness test
- ✅ Unit tests  
- ✅ Sanity tests (ALL checks)
- ✅ Ruff linting (zero violations)
- ✅ Yamllint (zero violations)
- ✅ Changelog (if code changes)
- ✅ JIRA reference (MANDATORY for bugfixes)

**Check status:**
```bash
gh run view <RUN_ID> --repo ansible/ansible.platform --log | grep -A 10 "collection completeness\|pytest\|ansible-test sanity\|ruff check"
```

**If ANY fail:** ❌ BLOCK - Request fixes before proceeding

### 3. Route to Specific Review

**Check for core infrastructure changes FIRST:**
```bash
git diff origin/devel --name-only | grep -E \
  'plugins/connection/|plugins/plugin_utils/manager/|plugins/plugin_utils/platform/(base_client|direct_client|config|registry)'
```

**If match:** Read `references/connection-manager-review.md` FIRST

**Then route by PR type:**

| Type | Reference | Trigger |
|------|-----------|---------|
| Feature | `references/feature-review.md` | `feat:`, new module |
| Bugfix | `references/bugfix-review.md` | `fix:`, JIRA AAP-* |
| CI/Workflow | `references/ci-workflow-review.md` | `ci:`, `.github/workflows/` |
| Docs-only | Skip to Step 4 | Only `docs/**/*.md` changed |

### 4. Safe-to-Test Readiness

**Prerequisites (ALL must pass):**
- ✅ All pre-merge CI checks passing
- ✅ JIRA referenced (if bugfix)
- ✅ Changelog present (if code changes)
- ✅ No security issues

**Decision:**
- All pass → ✅ Ready for `safe to test`
- ANY fail → ❌ BLOCK - Request fixes

### 5. Ask for Test Guidance (Before Applying Label)

```markdown
## ✅ Pre-merge Checks Passed

Before applying `safe to test` label:

**Test guidance needed:**
1. Which modules/resources should be tested?
2. Expected integration test results?
3. Known failures (if any)?

**Local testing (optional):**
\`\`\`bash
export AAP_HOSTNAME=your-instance
export AAP_USERNAME=your-user
export AAP_PASSWORD=your-pass
make collection-test CONNECTION_MODE=http-persistent
\`\`\`

Confirm and I'll apply the label.
```

**Wait for contributor response before applying label.**

### 6. Monitor Integration Tests

After label applied:
```bash
gh pr checks <PR_NUMBER> --repo ansible/ansible.platform --watch
```

**Common failures:**
- AAP connectivity (transient → re-run)
- Resource creation (check required fields)
- Timeout (check polling logic)

**Re-run transient:**
```bash
gh run rerun <RUN_ID> --repo ansible/ansible.platform --failed
```

### 7. Post Review

**Template:**
```markdown
## PR Review: #<PR_NUMBER>

**Type:** [Feature|Bugfix|CI|Docs]  
**CI Status:** [✅ All Green|❌ N Failing]

### Pre-Merge Checks
- [x] Collection completeness: ✅
- [x] Unit tests: ✅
- [x] Sanity tests: ✅
- [x] Changelog: ✅
- [x] JIRA: ✅ AAP-XXXXX

### [Type]-Specific Review
[See reference file findings]

### Safe-to-Test Status
**Status:** [✅ Ready | ❌ Blocked]
**Reason:** [Details]

### Final Verdict
[✅ LGTM | ⚠️ REQUEST CHANGES | ❌ BLOCK]
```

**Submit:**
```bash
# Approve
gh pr review <PR> --repo ansible/ansible.platform --approve --body "LGTM!"

# Request changes
gh pr review <PR> --repo ansible/ansible.platform --request-changes --body "$(cat review.md)"
```

---

## Quick Reference

### Pre-Merge CI Priority
1. Collection completeness (BLOCKING)
2. Unit tests (BLOCKING)
3. Sanity tests - ALL checks (BLOCKING)
4. Linting - zero violations (BLOCKING)
5. Changelog (BLOCKING if code changes)
6. JIRA (BLOCKING for bugfixes)

### Common Fixes
- Collection completeness → Add to `meta/runtime.yml`
- Missing changelog → Create `changelogs/fragments/<pr>-<name>.yml`
- Integration test failures → Check if transient, re-run

### Reference Files

**Core infrastructure (CRITICAL):**
- `references/connection-manager-review.md`

**PR type specific:**
- `references/feature-review.md` - Seven-file pattern, architecture
- `references/bugfix-review.md` - Regression tests, JIRA
- `references/ci-workflow-review.md` - Workflow security

**Shared patterns:**
- `references/common-patterns.md` - Validation commands, checklists
