# PR Review Skill

Comprehensive PR review workflow for ansible.platform collection maintainers.

## Structure

```
pr-review/
├── skill.md                          # Main skill file (ENTRY POINT)
├── README.md                         # This file
└── references/
    ├── feature-review.md             # Feature PR detailed checklist
    ├── bugfix-review.md              # Bugfix PR detailed checklist
    ├── ci-workflow-review.md         # CI/workflow PR checklist
    └── connection-manager-review.md  # Core infrastructure (CRITICAL)
```

## Usage

```bash
/pr-review <PR_NUMBER>
```

## Workflow Overview

The main skill file (`skill.md`) routes to appropriate reference guides:

### Step 1: Pre-Merge CI Checks (BEFORE safe-to-test)
- Collection completeness test
- Unit tests
- Sanity tests
- Changelog verification

### Step 2: Route to Specific Review
- `feat:` → `references/feature-review.md`
- `fix:` → `references/bugfix-review.md`
- `ci:` → `references/ci-workflow-review.md`

### Step 3: Safe-to-Test Readiness
- Determine if ready for `safe to test` label

### Step 4: Post-Label Monitoring
- Watch integration test results
- Re-run transient failures

## Reference Guides

### connection-manager-review.md ⚠️ CRITICAL
**Use for:** Changes to connection plugin, manager process, RPC layer, base clients

**ALWAYS check if PR touches these files:**
- `plugins/connection/http.py`
- `plugins/plugin_utils/manager/*`
- `plugins/plugin_utils/platform/{base_client,direct_client,config,registry}.py`

**Covers:**
- Backwards compatibility (affects ALL modules)
- Fork safety (macOS + Python 3.12)
- Connection modes (persistent vs direct)
- Subprocess spawning (vault credentials, security)
- Socket management (cleanup, permissions)
- RPC protocol changes
- HTTP session management
- Multi-service support (Gateway/Controller/EDA/Hub)
- Security (credential handling, subprocess safety)
- Performance (manager lifecycle, idle timeout)
- Testing requirements (MUST test multiple modules)

**Why critical:** These changes affect every module in the collection. Bugs here are hard to debug and impact all users.

### feature-review.md
**Use for:** New modules, new features, refactoring

**Covers:**
- Seven-file pattern validation
- Architecture compliance (Ansible Model vs API Model)
- Endpoint path verification (service prefixes)
- Transform mixin review (name→ID resolution)
- Test coverage requirements
- meta/runtime.yml registration

### bugfix-review.md
**Use for:** Bug fixes, regressions

**Covers:**
- Jira issue verification
- Bug description adequacy
- Regression test requirements
- Fix validation (addresses root cause)
- Similar bug scanning
- Backwards compatibility

### ci-workflow-review.md
**Use for:** CI, GitHub Actions, workflow changes

**Covers:**
- New workflow detection and justification
- Workflow security review
- Secret protection (label gates, author checks)
- Trigger condition validation
- Permission review (least-privilege)
- Test infrastructure changes
- Dependency updates
- Fork testing requirements

## Key Principles

1. **Collection completeness test runs BEFORE safe-to-test**
   - Must pass before label can be applied
   - Ensures meta/runtime.yml registration

2. **Pre-merge vs Post-label checks**
   - Pre-merge: completeness, unit, sanity, changelog
   - Post-label: integration tests (live AAP)

3. **Review routing**
   - Skill determines PR type
   - Routes to appropriate checklist
   - Prevents missing critical checks

## Review Output

Each review produces structured output:
- Summary
- Pre-merge CI status
- Architecture review (features)
- Blockers
- Safe-to-test readiness
- Final verdict

## Maintenance

Update these files when:
- Collection architecture changes
- New CI checks added
- Review requirements change
- New patterns discovered

## Based On

- PR #227 review experience (saved in `.claude/PR_REVIEW_CONTEXT_227.md`)
- ansible-community/ai-forge pr-review skill (base structure)
- ansible.platform collection standards

**Last Updated:** 2026-09-11
