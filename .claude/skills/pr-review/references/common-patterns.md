# Common PR Review Patterns

Shared validation patterns, checklists, and code references to reduce duplication across review guides.

## Code Examples - Reference Real Files

Instead of inline examples, point reviewers to actual code in the repository:

### Ansible Models
**Reference:** `plugins/plugin_utils/ansible_models/application.py`
- Shows proper @dataclass structure
- String names for references (not IDs)
- Optional fields with defaults

### API Models  
**Reference:** `plugins/plugin_utils/api/v1/application.py`
- APIApplication_v1 dataclass structure
- TransformMixin implementation
- to_api() / from_api() methods

### Action Plugins
**Reference:** `plugins/action/application.py`
- Pattern A: Simple resources (no special behavior)
- Shows ActionBase inheritance
- Proper arg_spec usage

**Reference:** `plugins/action/credential.py`  
- Pattern C: Credentials (special input handling)
- Shows input field transformation

### Unit Tests
**Reference:** `tests/unit/plugins/plugin_utils/api/v1/test_application.py`
- Transform test structure
- Parametrized test examples

## Common Validation Commands

### Check Seven-File Pattern
```bash
# For new module named 'foo'
# See docs/07-adding-resources.md for details
REQUIRED_FILES=(
  "plugins/modules/foo.py"                                    # 1. Module
  "plugins/plugin_utils/ansible_models/foo.py"                # 2. Ansible model
  "plugins/plugin_utils/api/v1/foo.py"                        # 3. Transform mixin
  "plugins/action/foo.py"                                     # 4. Action plugin
  "tests/integration/targets/foos_test/tasks/main.yml"        # 5. Integration tests (note plural 'foos')
)

OPTIONAL_FILES=(
  "extensions/molecule/foo_mock/"                             # 6. Molecule mock (recommended)
  "tests/unit/plugins/plugin_utils/api/v1/test_foo.py"       # 7. Unit tests (if complex transforms)
)

MISSING=0
for f in "${REQUIRED_FILES[@]}"; do
  if test -f "$f" || test -d "$f"; then
    echo "✅ $f"
  else
    echo "❌ Missing: $f"
    MISSING=1
  fi
done

for f in "${OPTIONAL_FILES[@]}"; do
  if test -f "$f" || test -d "$f"; then
    echo "✅ $f"
  else
    echo "⚠️  Recommended: $f"
  fi
done

exit $MISSING
```

### Check Linting (STRICT)
```bash
# Run locally
ruff check plugins/ tests/
ruff format --check plugins/ tests/
yamllint .

# Zero violations required
```

### Check Sanity Tests
```bash
# Run locally  
ansible-test sanity --docker

# All checks must pass
```

## Common Blockers Checklist

Use this for all PR types:

### Pre-Merge CI (BLOCKING)
- [ ] Collection completeness passing
- [ ] Unit tests passing (100%)
- [ ] Sanity tests passing (ALL checks)
- [ ] Ruff linting: zero violations
- [ ] Yamllint: zero violations
- [ ] Changelog present (if code changes)
- [ ] JIRA referenced (MANDATORY for bugfixes)

### Security (BLOCKING - ALL must pass)
- [ ] **Credentials:** No hardcoded credentials in code
- [ ] **Workflows:** No secrets in workflow outputs or fork-accessible triggers
- [ ] **Logging:** No credential logging (not even at -vvvv)
- [ ] **Subprocess:** No plaintext passwords in subprocess args
- [ ] **Input validation:** User input sanitized (no command/code injection)
- [ ] **URL encoding:** API URLs properly encoded (use urlencode)
- [ ] **Error messages:** No secrets in error messages or return values
- [ ] **Defaults:** Secure defaults (verify_ssl=True, not False)
- [ ] **Vault handling:** Vault credentials converted to str() before use

### Testing (BLOCKING - apply based on PR type)
- [ ] Unit tests for new code (if plugins/**/*.py changed)
- [ ] Transform tests (to_api/from_api) - ONLY if transform logic changed
- [ ] Regression test for bugfixes (bugfix PRs only)
- [ ] Workflow validation (CI/workflow PRs only - use actionlint)

## Common Code Smells

### Anti-Patterns to Flag

**1. Using IDs instead of names in Ansible models:**
```python
# ❌ WRONG
organization: int  # API-specific

# ✅ CORRECT  
organization: str  # User-facing name
```

**2. Hardcoded endpoints:**
```python
# ❌ WRONG
url = f"/api/v2/applications/{id}/"

# ✅ CORRECT
# Use mixin methods that handle versioning
```

**3. Missing error handling:**
```python
# ❌ WRONG  
result = api.get(...)['results'][0]

# ✅ CORRECT
results = api.get(...)['results']
if len(results) != 1:
    raise ValueError(f"Expected 1 result, got {len(results)}")
```

**4. Credential leakage:**
```python
# ❌ WRONG
self._display.vvvv(f"Password: {password}")
subprocess.Popen([..., f"--password={password}"])

# ✅ CORRECT  
self._display.vvvv("Authentication configured")
# Pass credentials via secure IPC
```

## Action Plugin Base Class Usage

**All action plugins MUST inherit from `BaseResourceActionPlugin`**

### Required Class Attributes

```python
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.foo import AnsibleFoo

class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "foo"        # REQUIRED: Resource name (matches module filename)
    MODEL_CLASS = AnsibleFoo   # REQUIRED: Ansible dataclass type
    LOOKUP_FIELD = "name"      # OPTIONAL: Default is "name"
```

### Three Patterns (Prefer A → B → C)

**Pattern A (Simple Resources):**
- Define MODULE_NAME and MODEL_CLASS only
- Inherit run() method from base class
- No custom logic needed
- **Example:** `plugins/action/organization.py`

**Pattern B (Resources with Hooks):**
- Define MODULE_NAME and MODEL_CLASS
- Override pre/post hooks for orchestration
- Don't override run() entirely
- **Example:** `plugins/action/application.py`

**Pattern C (Complex Custom Logic):**
- Override run() method
- Still call base class methods (don't reimplement)
- Use ONLY when A/B patterns insufficient
- **Example:** `plugins/action/credential.py`

### Checklist for Action Plugin Review

- [ ] **Inherits from BaseResourceActionPlugin** (not ActionBase directly)
- [ ] **MODULE_NAME set** (matches module filename)
- [ ] **MODEL_CLASS set** (correct Ansible dataclass)
- [ ] **Uses simplest pattern** (prefer A over B over C)
- [ ] **No HTTP calls in action plugin** (use manager.execute() only)
- [ ] **No hardcoded API URLs** (belong in transform mixin)
- [ ] **No wait/poll loops** (belong in PlatformService.execute())

### Common Violations

**❌ WRONG: Custom run() that reimplements base logic**
```python
class ActionModule(BaseResourceActionPlugin):
    def run(self, tmp=None, task_vars=None):
        # Reimplements argument parsing, manager spawning, etc.
        # This duplicates base class logic!
```

**✅ CORRECT: Minimal Pattern A**
```python
class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "foo"
    MODEL_CLASS = AnsibleFoo
    # Inherits run() from base - no custom code needed
```

**❌ WRONG: HTTP calls in action plugin**
```python
class ActionModule(BaseResourceActionPlugin):
    def run(self, tmp=None, task_vars=None):
        response = requests.post(...)  # Violates SDK invariant #2!
```

**✅ CORRECT: Use manager.execute()**
```python
class ActionModule(BaseResourceActionPlugin):
    def run(self, tmp=None, task_vars=None):
        manager = self._get_or_spawn_manager(task_vars)
        result = manager.execute(operation="create", ...)  # SDK-compliant
```

**Reference:** `docs/09-agent-collaboration.md` Section 10 (SDK Execution Invariants)

---

## Architecture Principles Reference

Point to these docs instead of repeating content:

- **Three-tier model:** `docs/04-data-model-transformation.md`
- **Seven-file pattern:** `docs/07-adding-resources.md`  
- **SDK architecture:** `docs/03-sdk-architecture.md`
- **Connection modes:** `docs/06-connection-plugin-architecture.md`
- **Action plugin patterns:** `plugins/action/base_action.py` (docstring)

## Quick Detection Commands

### Check for Connection/Manager Changes (CRITICAL)
```bash
git diff origin/devel --name-only | grep -E \
  'plugins/connection/|plugins/plugin_utils/manager/|plugins/plugin_utils/platform/(base_client|direct_client|config|registry)'
```

If matches → Read `connection-manager-review.md` FIRST

### Check for Workflow Changes  
```bash
git diff origin/devel --name-only | grep '.github/workflows/'
```

If matches → Read `ci-workflow-review.md`

### Check PR Type
```bash
# From PR title
gh pr view <NUM> --json title --jq '.title' | grep -E '^(feat|fix|ci|docs|refactor):'
```

## Testing Requirements by Type

### Features
- Unit tests for transform logic
- Molecule tests (recommended)
- Integration tests (can defer to follow-up)

### Bugfixes  
- **MANDATORY:** Regression test that fails without fix
- Unit test coverage for changed code

### CI/Workflow
- Local validation with `actionlint` or `act --dryrun`
- Security review for secret exposure

## Merge Readiness Decision Tree

```
┌─ All linting passing? ─ NO ─→ BLOCK (request fixes)
└─ YES
   ┌─ All sanity passing? ─ NO ─→ BLOCK (request fixes)
   └─ YES
      ┌─ Unit tests passing? ─ NO ─→ BLOCK (request fixes)
      └─ YES
         ┌─ Is bugfix? ─ YES ─┬─ JIRA referenced? ─ NO ─→ BLOCK
         │                    └─ YES → Continue
         └─ NO → Continue
            ┌─ Changelog present? ─ NO ─→ BLOCK (if code changes)
            └─ YES
               ┌─ Security issues? ─ YES ─→ BLOCK
               └─ NO
                  └─→ ✅ READY for safe-to-test
```

## Response Templates

### Request Linting Fixes
```markdown
❌ **BLOCKER: Linting violations**

The following linting issues must be fixed:

**Ruff violations:**
- `file.py:42`: F401 Unused import 'os'
- `file.py:89`: E501 Line too long (120 > 100)

**Fix:**
```bash
ruff check --fix plugins/ tests/
ruff format plugins/ tests/
```

Re-run CI after fixes.
```

### Request Missing JIRA
```markdown
❌ **BLOCKER: Missing JIRA reference**

Bugfix PRs must reference a JIRA issue.

**Required format:**
- PR title: `fix: [AAP-12345] Description`
- Or PR body must mention: AAP-12345 or ANSTRAT-12345

**Why:** Ensures traceability and customer ticket tracking.
```

### Request Sanity Fixes
```markdown
❌ **BLOCKER: Sanity test failures**

The following sanity checks failed:

- `validate-modules`: DOCUMENTATION field missing required keys
- `import`: Unused import in `plugins/modules/foo.py`
- `pep8`: Line 45 exceeds 160 characters

**Fix locally:**
```bash
ansible-test sanity --docker
```

All checks must pass before `safe-to-test`.
```

## Common Review Questions

### "Is this a breaking change?"
- Does it change Ansible model field names?
- Does it change required vs optional fields?
- Does it change module behavior without new parameter?

If YES → Requires major version bump or deprecation

### "Does this need backporting?"
- Is it a bugfix in stable branches?
- Check `.github/workflows/backport.yml` for target branches

### "Is coverage sufficient?"
Ask:
- Do unit tests cover new code paths?
- Does bugfix have regression test?
- Are edge cases tested?

## Notes

- **Keep examples short**: Point to real files instead of pasting code
- **Don't repeat architecture docs**: Link to existing documentation
- **Focus on validation**: What to check, not how to implement
- **Make blockers clear**: Use ❌ and "BLOCKING" labels

**Last Updated:** 2026-09-17
