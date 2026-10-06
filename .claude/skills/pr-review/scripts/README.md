# PR Review Scripts

Reusable validation scripts referenced by PR review skill guides.

## Scripts

### check_workflow_secrets.py

**Purpose:** Detect secret exposure vulnerabilities in GitHub Actions workflows

**Usage:**
```bash
python3 .claude/skills/pr-review/scripts/check_workflow_secrets.py
```

**Checks:**
- Workflows using secrets with `pull_request` trigger without authorization gates
- `pull_request_target` workflows checking out PR code (dangerous!)
- Missing label gates (`safe to test`) or member checks

**Referenced by:**
- `references/ci-workflow-review.md`

---

### check_seven_file_pattern.sh

**Purpose:** Validate that new modules follow the required seven-file pattern

**Usage:**
```bash
.claude/skills/pr-review/scripts/check_seven_file_pattern.sh <module_name>
```

**Example:**
```bash
.claude/skills/pr-review/scripts/check_seven_file_pattern.sh service_cluster
```

**Checks:**
- Module file: `plugins/modules/<resource>.py`
- Ansible model: `plugins/plugin_utils/ansible_models/<resource>.py`
- API model: `plugins/plugin_utils/api/gateway/v1/<resource>.py`
- Action plugin: `plugins/action/<resource>.py`
- Integration test: `tests/integration/targets/<resource>s_test/`
- Molecule mock: `extensions/molecule/<resource>_mock/` (recommended)
- Unit tests: `tests/unit/...` (recommended)

**Referenced by:**
- `references/feature-review.md`
- `references/common-patterns.md`

---

### check_jira_reference.sh

**Purpose:** Extract and validate Jira reference from PR title

**Usage:**
```bash
.claude/skills/pr-review/scripts/check_jira_reference.sh <pr_number>
```

**Example:**
```bash
.claude/skills/pr-review/scripts/check_jira_reference.sh 274
```

**Checks:**
- PR title contains Jira reference in format `AAP-XXXXX`
- Accepts formats: `[AAP-12345]` or `AAP-12345:`

**Referenced by:**
- `references/bugfix-review.md`
- `references/common-patterns.md`

---

## Development Guidelines

### Adding New Scripts

1. **Make scripts executable:**
   ```bash
   chmod +x .claude/skills/pr-review/scripts/<script>.sh
   ```

2. **Add shebang:**
   - Bash: `#!/usr/bin/env bash`
   - Python: `#!/usr/bin/env python3`

3. **Include usage documentation:**
   - Help text when called with no arguments
   - Exit codes documented
   - Example usage

4. **Test before committing:**
   ```bash
   # Test success case
   .claude/skills/pr-review/scripts/check_seven_file_pattern.sh user
   
   # Test failure case
   .claude/skills/pr-review/scripts/check_seven_file_pattern.sh nonexistent_module
   ```

5. **Update this README** with script description and usage

### Script Conventions

- **Exit codes:**
  - `0` - Success (checks passed)
  - `1` - Failure (checks failed or error)

- **Output format:**
  - Use emoji prefixes: ✅ (success), ❌ (error), ⚠️ (warning)
  - Print summary at end
  - Verbose output for debugging

- **Error handling:**
  - Use `set -euo pipefail` in bash scripts
  - Validate inputs (number of arguments, file existence)
  - Provide helpful error messages

## Testing

Run all scripts in CI to ensure they work:

```bash
# Test workflow checker
python3 .claude/skills/pr-review/scripts/check_workflow_secrets.py

# Test seven-file pattern (on existing module)
.claude/skills/pr-review/scripts/check_seven_file_pattern.sh user

# Test Jira checker (on real PR)
.claude/skills/pr-review/scripts/check_jira_reference.sh 246
```
