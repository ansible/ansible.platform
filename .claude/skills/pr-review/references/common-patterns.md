# Common PR Review Patterns

Shared validation patterns, checklists, and commands used across ALL PR review types (feature, bugfix, CI/workflow).

**Referenced by:** All review guides to ensure consistency

---

## Pre-Merge CI Checks (REQUIRED FOR ALL PRs)

These checks run automatically and **MUST pass before `safe to test` label** regardless of PR type.

### 1. Collection Completeness Test

**What it checks:** All modules extending `ansible.platform.auth` are registered in `meta/runtime.yml`

**Purpose:** Enables `module_defaults` for `group/ansible.platform.gateway`

**Check status:**
```bash
gh run view <RUN_ID> --repo ansible/ansible.platform --log | grep "collection completeness"
```

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
```

**Priority:** 🔴 **BLOCKING**

---

### 2. Unit Tests

**What they check:** Transform logic, utilities, framework code

**Run locally:**
```bash
pytest tests/unit/ -v

# Run specific test
pytest tests/unit/plugins/plugin_utils/api/gateway/v1/test_team.py -v
```

**Check status:**
```bash
gh run view <RUN_ID> --repo ansible/ansible.platform --log | grep "pytest"
```

**Common failures:**
- Assertion errors (expected vs actual mismatch)
- Import errors (missing dependencies)
- Mock/fixture issues

**Priority:** 🔴 **BLOCKING**

---

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

**Check status:**
```bash
gh run view <RUN_ID> --repo ansible/ansible.platform --log | grep "ansible-test sanity"
```

**Common failures:**
- Malformed DOCUMENTATION YAML
- Missing required doc fields
- Import violations
- Formatting issues

**Priority:** 🔴 **BLOCKING**

---

### 4. Linting (Ruff, Yamllint)

**What they check:**
- Code style (PEP8, line length, imports)
- YAML syntax and formatting

**Run locally:**
```bash
# Ruff
ruff check plugins/ tests/
ruff format --check plugins/ tests/

# Yamllint
yamllint .
```

**Check status:**
```bash
gh run view <RUN_ID> --repo ansible/ansible.platform --log | grep -E "ruff|yamllint"
```

**Priority:** 🔴 **BLOCKING** - Zero violations required

---

### 5. Changelog Fragment

**Required if PR changes:**
- Any Python code in `plugins/`
- Module documentation
- Action plugin logic
- Transform mixins

**NOT required if PR only changes:**
- Documentation in `docs/`
- Test files
- CI workflows (unless user-facing)
- README files

**Validation:**
```bash
# Check if changelog exists
ls changelogs/fragments/ | grep -E "$(gh pr view <PR_NUMBER> --json number --jq '.number')"
```

**Create changelog:**
```bash
# Format: <pr_number>-<short_description>.yml
cat > changelogs/fragments/274-api-versioning.yml << 'EOF'
---
minor_changes:
  - "Add per-service API versioning with service-scoped directory layout"
EOF
```

**Priority:** 🟡 **BLOCKING** (if code changes)

---

### 6. Jira Reference (Bugfixes Only)

**Required for:** All bugfix PRs (`fix:`, `bug:` in title)

**Validation script:**
```bash
.claude/skills/pr-review/scripts/check_jira_reference.sh <PR_NUMBER>
```

**Manual check:**
```bash
gh pr view <PR_NUMBER> --json title --jq '.title' | grep -oE 'AAP-[0-9]+'
```

**Required format:**
- `[AAP-12345] Fix description`
- `AAP-12345: Fix description`

**Priority:** 🟡 **BLOCKING** (for bugfixes only)

---

## Architecture Compliance (Feature PRs)

### Seven-File Pattern Check

**Validation script:**
```bash
.claude/skills/pr-review/scripts/check_seven_file_pattern.sh <module_name>
```

**Manual check:**
```bash
# For new module named 'foo'
REQUIRED_FILES=(
  "plugins/modules/foo.py"
  "plugins/plugin_utils/ansible_models/foo.py"
  "plugins/plugin_utils/api/gateway/v1/foo.py"
  "plugins/action/foo.py"
  "tests/integration/targets/foos_test/tasks/main.yml"
  "tests/integration/targets/foos_test/meta/main.yml"
)

MISSING_COUNT=0
echo "Checking seven-file pattern..."
for f in "${REQUIRED_FILES[@]}"; do
  if test -f "$f" || test -d "$f"; then
    echo "✅ $f"
  else
    echo "❌ Missing REQUIRED: $f"
    ((++MISSING_COUNT))
  fi
done

if [ $MISSING_COUNT -gt 0 ]; then
  echo "❌ FAILED: $MISSING_COUNT required file(s) missing"
  exit 1
else
  echo "✅ All required files present"
fi
```

**Priority:** 🔴 **BLOCKING** (for new modules)

---

### Module Registration Check

**What it checks:** New modules are registered in `meta/runtime.yml`

**Validation:**
```bash
# Extract module name from PR files
MODULE_NAME=$(gh pr view <PR_NUMBER> --json files --jq '.files[].path' | grep 'plugins/modules/' | head -1 | xargs basename | sed 's/.py$//')

# Check if registered
grep -q "$MODULE_NAME" meta/runtime.yml && echo "✅ Registered" || echo "❌ Not registered"
```

**Priority:** 🔴 **BLOCKING** (for new modules)

---

## Code Quality Checks

### Import Validation

**Pattern violations to flag:**

```python
# ❌ BAD: HTTP imports in action plugins
# File: plugins/action/foo.py
import requests
session.get(...)

# ❌ BAD: Hardcoded version strings
api_version = "1"

# ❌ BAD: Direct session access in mixin
# File: plugins/plugin_utils/api/gateway/v1/foo.py
def from_ansible_data(self, ansible_instance, context):
    response = requests.get(...)  # NO!

# ✅ GOOD: Use context.manager for HTTP
def from_ansible_data(self, ansible_instance, context):
    org_id = context.manager.lookup_resource_id("organization", org_name)
```

---

### Naming Conventions Check

**Validate against Principle 10:**

| Item | Convention | Example |
|------|-----------|---------|
| Module name | `snake_case` | `service_cluster` |
| Ansible model class | `Ansible<PascalCase>` | `AnsibleServiceCluster` |
| API model class | `API<PascalCase>_v<N>` | `APIServiceCluster_v1` |
| Transform mixin class | `<PascalCase>TransformMixin_v<N>` | `ServiceClusterTransformMixin_v1` |
| Action plugin class | Always `ActionModule` | `ActionModule` |

**Validation:**
```bash
MODULE_NAME="service_cluster"
PASCAL_NAME="ServiceCluster"

# Check Ansible model
grep -q "class Ansible${PASCAL_NAME}" "plugins/plugin_utils/ansible_models/${MODULE_NAME}.py"

# Check API model
grep -q "class API${PASCAL_NAME}_v1" "plugins/plugin_utils/api/gateway/v1/${MODULE_NAME}.py"

# Check mixin
grep -q "class ${PASCAL_NAME}TransformMixin_v1" "plugins/plugin_utils/api/gateway/v1/${MODULE_NAME}.py"
```

---

## Security Review Patterns

### Credential Handling Check

**Flag these patterns:**

```python
# ❌ Credential exposure in logs
print(f"Password: {password}")
logger.info(f"Token: {oauth_token}")

# ❌ Credentials in environment without sanitization
os.environ["PASSWORD"] = password  # Visible in /proc/<pid>/environ

# ❌ Credentials in command line
subprocess.run(["curl", "-u", f"{user}:{pass}", url])  # Visible in ps

# ✅ GOOD: Credentials marked no_log
# DOCUMENTATION:
options:
  password:
    type: str
    no_log: true
```

**Validation:**
```bash
# Check for password/token fields with no_log
grep -A 5 "password\|token\|secret" plugins/modules/*.py | grep "no_log: true"
```

---

### Subprocess Safety Check

**Required for any PR using `subprocess`:**

```python
# ❌ BAD: Shell=True with user input
subprocess.run(f"echo {user_input}", shell=True)  # Shell injection!

# ❌ BAD: Passing vaulted strings directly
subprocess.Popen(args, env={"PASSWORD": vaulted_password})  # TypeError

# ✅ GOOD: Convert vaulted strings first
subprocess.Popen(args, env={"PASSWORD": str(vaulted_password)})

# ✅ GOOD: No shell, list of args
subprocess.run(["echo", user_input], shell=False)
```

---

## CI/Workflow Security (CI PRs Only)

### Workflow Secret Exposure Check

**Validation script:**
```bash
python3 .claude/skills/pr-review/scripts/check_workflow_secrets.py
```

**What it checks:**
- Workflows using `secrets.` with `pull_request` trigger
- Missing label gates (`safe to test`) or member checks
- `pull_request_target` checking out PR code

**Priority:** 🔴 **BLOCKING** (for workflow changes)

---

## Integration Test Guidance (Post-Label)

**Triggered by:** `safe to test` label (after pre-merge CI passes)

### When Integration Tests Are BLOCKING

**Integration test failures ARE BLOCKING for:**
- ✅ Reproducible failures (fails on multiple runs)
- ✅ Assertion errors (expected != actual)
- ✅ Resource creation failures (validation errors)
- ✅ Any failure in modified code path

### When Integration Tests Are NOT BLOCKING

**Integration test failures are NOT BLOCKING for:**

1. **Transient Infrastructure Failures:**
   - AAP unreachable (connection timeout)
   - AAP service restart during test run
   - Network issues (DNS, TLS handshake failures)
   - **Action:** Re-run once. If passes → NOT BLOCKING

2. **Known AAP Bugs:**
   - AAP API bug affecting test (with JIRA reference)
   - AAP version mismatch
   - **Action:** Document in PR, skip affected test → NOT BLOCKING

3. **Test Infrastructure Issues:**
   - Test credentials expired
   - Test organization/resources deleted externally
   - **Action:** Fix infrastructure, re-run → NOT BLOCKING

**Re-run transient failures:**
```bash
gh run rerun <RUN_ID> --repo ansible/ansible.platform --failed
```

---

## Code Examples - Reference Real Files

Instead of inline examples, point reviewers to actual code in the repository:

### Ansible Models
**Reference:** `plugins/plugin_utils/ansible_models/application.py`
- Shows proper @dataclass structure
- String names for references (not IDs)
- Optional fields with defaults

### API Models  
**Reference:** `plugins/plugin_utils/api/gateway/v1/application.py`
- APIApplication_v1 dataclass structure
- TransformMixin implementation
- to_api() / from_api() methods

### Action Plugins
**Reference:** `plugins/action/application.py`
- Pattern A: Simple resources (no special behavior)
- Shows BaseResourceActionPlugin inheritance
- MODULE_NAME and MODEL_CLASS pattern

**Reference:** `plugins/action/credential.py`  
- Pattern C: Credentials (special input handling)
- Shows input field transformation

### Unit Tests
**Reference:** `tests/unit/plugins/plugin_utils/api/gateway/v1/test_application.py`
- Transform test structure
- Parametrized test examples

---

## Anti-Patterns to Flag

### 1. Hardcoded Versions
```python
# ❌ BAD
api_path = "/api/v1/users/"

# ✅ GOOD
api_path = f"/api/gateway/v{context.api_version}/users/"
```

### 2. Direct HTTP in Action Plugins
```python
# ❌ BAD (violates Principle 1)
class ActionModule(ActionPlugin):
    def run(self):
        response = requests.post(url, json=data)

# ✅ GOOD
class ActionModule(BaseResourceActionPlugin):
    def run(self):
        result = self.manager.execute("create", "user", data)
```

### 3. Mutable Defaults
```python
# ❌ BAD
@dataclass
class AnsibleFoo:
    tags: list = []  # DANGER: shared across instances

# ✅ GOOD
@dataclass
class AnsibleFoo:
    tags: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
```

### 4. Missing no_log on Secrets
```python
# ❌ BAD
DOCUMENTATION = r"""
options:
  password:
    type: str
    # Missing no_log!
"""

# ✅ GOOD
DOCUMENTATION = r"""
options:
  password:
    type: str
    no_log: true
"""
```

---

## Quick Reference Checklist

Use this for all PR types:

### Pre-Merge CI (BLOCKING)
- [ ] Collection completeness test passing
- [ ] Unit tests passing (100%)
- [ ] Sanity tests passing (ALL checks)
- [ ] Ruff linting (zero violations)
- [ ] Yamllint (zero violations)
- [ ] Changelog fragment present (if code changes)
- [ ] Jira reference in title (if bugfix)

### Architecture (Feature PRs)
- [ ] Seven-file pattern complete
- [ ] Module registered in `meta/runtime.yml`
- [ ] Naming conventions followed
- [ ] No HTTP in action plugins
- [ ] Transform logic in mixin only

### Security (All PRs)
- [ ] Secrets marked `no_log: true`
- [ ] No credentials in logs/environment
- [ ] Subprocess calls sanitized
- [ ] Workflow secrets protected (if CI changes)

### Integration Tests (Post-Label)
- [ ] Tests pass OR transient failure documented
- [ ] Real failures addressed (reproducible)
- [ ] Test coverage adequate for changes

---

## Maintenance Notes

**This file is the canonical reference for validation patterns.**

When updating validation logic:
1. Update the relevant section in this file
2. Reference guides automatically stay synchronized
3. Scripts in `scripts/` may need updates too
4. Test changes locally before committing
