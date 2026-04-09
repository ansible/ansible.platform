# Testing Strategy

`ansible.platform` uses a three-layer testing strategy that validates correctness at
increasing levels of integration:

```
Layer 1: Unit Tests (pytest, no network)
    ↓ fast feedback on framework components
Layer 2: Molecule Mock Tests (mock Gateway server, no live AAP)
    ↓ idempotency and state machine validation
Layer 3: Integration Tests (live AAP instance)
    ↓ end-to-end validation against real Gateway API
```

Each layer catches different classes of bugs. All three must pass before a PR is merged.

---

## Table of Contents

1. [Layer 1: Unit Tests](#section-1-layer-1-unit-tests)
2. [Layer 2: Molecule Mock Tests](#section-2-layer-2-molecule-mock-tests)
3. [Layer 3: Integration Tests](#section-3-layer-3-integration-tests)
4. [Linting Tests](#linting-tests)
5. [Running Tests](#section-4-running-tests)
6. [CI Pipeline](#section-5-ci-pipeline)
7. [Test Coverage Requirements](#section-6-test-coverage-requirements)
8. [What Each Layer Catches](#section-7-what-each-layer-catches)

---

## SECTION 1: Layer 1 — Unit Tests

**Location**: `tests/unit/`  
**Runner**: `pytest tests/unit/ -v`  
**Requires**: `pip install ansible-core pytest`

Unit tests validate framework components in isolation, with no network calls and no
subprocesses. All external dependencies (HTTP sessions, manager processes, filesystem
operations) are mocked with `unittest.mock`.

### Test Coverage

| Test file | What it tests |
|-----------|--------------|
| `tests/unit/modules/test_registry.py` | `APIVersionRegistry` scan + `DynamicClassLoader` routing + `PlatformService` version fallback |
| `tests/unit/plugins/connection/test_http.py` | Connection plugin routing (direct vs persistent), fault tolerance (stale socket, dead manager) |
| `tests/unit/plugins/plugin_utils/platform/test_registry.py` | Registry filesystem scan with fake temporary `api/` directory |

### What Each Test Validates

**`test_registry.py` (modules layer)**:
- Registry correctly discovers all versioned modules from the real `api/` directory
- `DynamicClassLoader` loads the correct `(AnsibleClass, APIClass, MixinClass)` tuple
- Requesting version `"12"` falls back to the highest available (version resilience)
- `PlatformService` falls back to local highest version when Gateway reports unknown future version
- `ValueError` raised (not silent failure) when a module has no versions at all

**`test_http.py` (connection plugin)**:
- `get_client()` routes to `_get_direct_client` when `persistent=False`
- `get_client()` routes to `_get_persistent_client` when `persistent=True`
- All variable sources checked in order: connection option → task vars → hostvars → default
- Direct mode returns `(client, None)` — no facts stored
- Persistent mode returns `(client, facts_dict)` with socket path and authkey
- Stale socket (file exists, `ManagerRPCClient` raises): re-spawn triggered
- Missing socket file: skip reuse attempt, spawn new manager

**`test_registry.py` (platform layer)**:
- Discovery from a temporary fake `api/` directory
- `__init__.py` files ignored, only `.py` module files counted
- Exact version match, closest-lower fallback, unknown module → `None`

### Unit Test File Structure

Each unit test file follows this pattern:

```python
# tests/unit/plugins/plugin_utils/platform/test_registry.py

import pytest
from unittest.mock import MagicMock, patch, mock_open
import tempfile
import os

from ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry import (
    APIVersionRegistry,
    DynamicClassLoader,
)


class TestAPIVersionRegistry:
    """Test suite for APIVersionRegistry."""

    def test_discover_modules_finds_all_versions(self):
        """Registry discovers all module files from api/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake api/v1/ and api/v2/ directories
            os.makedirs(os.path.join(tmpdir, 'api', 'v1'))
            os.makedirs(os.path.join(tmpdir, 'api', 'v2'))
            
            # Create fake module files
            open(os.path.join(tmpdir, 'api', 'v1', 'user.py'), 'w').close()
            open(os.path.join(tmpdir, 'api', 'v2', 'user.py'), 'w').close()
            
            registry = APIVersionRegistry(api_dir=tmpdir)
            modules = registry.discover_modules()
            
            assert 'user' in modules
            assert set(modules['user']) == {'v1', 'v2'}

    def test_version_fallback_to_highest(self):
        """Requesting unknown version falls back to highest available."""
        registry = APIVersionRegistry()
        # Request v99 (doesn't exist); should return v1 (highest available)
        loader = registry.get_loader('user', api_version='99')
        assert loader is not None
        # Verify it loaded the v1 version
        assert loader.api_class.__module__.endswith('v1')

    def test_raises_when_module_has_no_versions(self):
        """ValueError raised for module with zero versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, 'api', 'v1'))
            # Create no modules in the directory
            
            registry = APIVersionRegistry(api_dir=tmpdir)
            with pytest.raises(ValueError, match="no versions available"):
                registry.get_loader('nonexistent_module', api_version='1')


class TestDynamicClassLoader:
    """Test suite for DynamicClassLoader."""

    def test_loads_ansible_api_mixin_classes(self):
        """Loader returns (AnsibleClass, APIClass, MixinClass) tuple."""
        loader = DynamicClassLoader(module_name='user', api_version='1')
        ansible_class, api_class, mixin_class = loader.load()
        
        assert ansible_class.__name__ == 'AnsibleUser'
        assert api_class.__name__ == 'APIUser_v1'
        assert hasattr(mixin_class, 'from_ansible_data')
        assert hasattr(mixin_class, 'from_api')
```

### Running Unit Tests

```bash
# Full unit test suite (from collection root)
pytest tests/unit/ -v

# Single file
pytest tests/unit/plugins/connection/test_http.py -v

# Single test
pytest tests/unit/modules/test_registry.py::TestAPIVersioning::test_platform_service_version_fallback -v

# With coverage
pip install pytest-cov
pytest tests/unit/ --cov=plugins --cov-report=term-missing
```

### CI

Unit tests run in GitHub Actions on every PR and push to `devel`:

```yaml
# .github/workflows/unit.yml
- uses: actions/checkout@v4
  with:
    path: ansible_collections/ansible/platform
- run: pip install ansible-core pytest
- working-directory: ansible_collections/ansible/platform
  run: python -m pytest tests/unit/ -v
```

The checkout path `ansible_collections/ansible/platform` is critical — it creates the
namespace directory structure required for `import ansible_collections.ansible.platform.*`
to resolve correctly.

---

## SECTION 2: Layer 2 — Molecule Mock Tests

**Location**: `extensions/molecule/<resource>_mock/`  
**Runner**: `molecule converge && molecule verify`  
**Requires**: Mock Gateway server, no live AAP

Molecule scenarios test the full action plugin → manager → transform mixin → HTTP round
trip against a **mock Gateway server** that implements the AAP API contract in memory.

### Why Mock Tests

Integration tests against a live AAP instance are slow (minutes), require network
access, and cannot run in standard CI without a provisioned AAP environment. Mock tests:
- Run in 20–60 seconds
- Require no network access
- Are deterministic (no drift from live data)
- Test idempotency rigorously (the mock has a perfect memory)

### Mock Server Architecture

The mock Gateway server (`tools/mock_gateway_server.py`) is a Flask application that:
- Implements `GET`, `POST`, `PATCH`, `DELETE` for all 22 resource types
- Stores state in an in-memory dict (`STORE`)
- Implements realistic responses: 201 Created, 200 OK, 404 Not Found, 400 Bad Request
- Seeds known resources (e.g. a default organization, test user) so tests have a baseline

Starting the mock server:
```bash
python tools/mock_gateway_server.py --port 8080
```

### Molecule Scenario File Structure

Each mock scenario has four files:

```
extensions/molecule/<resource>_mock/
├── molecule.yml      — driver config (local connection, no containers)
├── converge.yml      — the test playbook (create + idempotency + update + delete)
├── verify.yml        — assertions on final state (optional additional checks)
└── cleanup.yml       — ensure test resources are removed after the run
```

**molecule.yml**:

```yaml
---
driver:
  name: default

platforms:
  - name: localhost

ansible:
  executor:
    args:
      ansible_playbook:
        - --inventory=${MOLECULE_SCENARIO_DIRECTORY}/../inventory.yml

provisioner:
  name: ansible
  playbooks:
    converge: converge.yml
    verify: verify.yml
    cleanup: cleanup.yml
  config_options:
    defaults:
      collections_path: "${MOLECULE_SCENARIO_DIRECTORY}/../../../../../../"
      log_verbosity: 4

scenario:
  test_sequence:
    - converge
    - verify
    - cleanup
...
```

### Converge Playbook Pattern

All mock scenarios follow this structure:

**converge.yml**:

```yaml
---
- name: Converge
  hosts: localhost
  gather_facts: false

  pre_tasks:
    - name: Start mock Gateway server
      include_role:
        name: start_mock_server

  tasks:
    # PHASE 1: Create resource on first run
    - name: Create application (first run)
      ansible.platform.application:
        name: test-app
        organization: Engineering
        authorization_grant_type: password
        client_type: public
        state: present
      register: first_run

    - name: Assert first run changed
      assert:
        that:
          - first_run.changed
          - first_run.application.id is defined

    # PHASE 2: Idempotency check — same create again
    - name: Create application (idempotency check)
      ansible.platform.application:
        name: test-app
        organization: Engineering
        authorization_grant_type: password
        client_type: public
        state: present
      register: second_run

    - name: Assert idempotent run did not change
      assert:
        that:
          - not second_run.changed
          - second_run.application.id == first_run.application.id

    # PHASE 3: Exists check (if state: exists is supported)
    - name: Check resource exists
      ansible.platform.application:
        name: test-app
        organization: Engineering
        state: exists
      register: exists_check

    - name: Assert exists check
      assert:
        that:
          - exists_check.exists
          - not exists_check.changed

    # PHASE 4: Update test (if applicable)
    - name: Update application
      ansible.platform.application:
        name: test-app
        organization: Engineering
        authorization_grant_type: authorization-code  # changed
        client_type: confidential  # changed
        state: present
      register: update_run

    - name: Assert update changed
      assert:
        that:
          - update_run.changed
          - update_run.application.authorization_grant_type == 'authorization-code'

    # PHASE 5: Delete resource
    - name: Delete application
      ansible.platform.application:
        name: test-app
        organization: Engineering
        state: absent
      register: delete_run

    - name: Assert delete changed
      assert:
        that:
          - delete_run.changed

    # PHASE 6: Delete idempotency — delete again
    - name: Delete application (idempotency check)
      ansible.platform.application:
        name: test-app
        organization: Engineering
        state: absent
      register: delete_again

    - name: Assert second delete is no-op
      assert:
        that:
          - not delete_again.changed

  always:
    - name: Stop mock server
      include_role:
        name: stop_mock_server
...
```

**verify.yml** (optional, for additional assertions):

```yaml
---
- name: Verify final state
  hosts: localhost
  gather_facts: false

  tasks:
    - name: Verify no test resources remain
      ansible.platform.application:
        name: test-app
        organization: Engineering
        state: exists
      register: final_check

    - name: Assert resource was deleted
      assert:
        that:
          - not final_check.exists
...
```

**cleanup.yml** (ensure test resources removed):

```yaml
---
- name: Cleanup test resources
  hosts: localhost
  gather_facts: false

  tasks:
    - name: Delete test application if exists
      ansible.platform.application:
        name: test-app
        organization: Engineering
        state: absent
      failed_when: false
...
```

### Running Mock Tests

```bash
# Run single scenario
cd extensions/molecule/users_mock
molecule converge
molecule verify
molecule destroy

# Run all mock scenarios at once
cd /path/to/collection
molecule test -s users_mock
molecule test -s organization_mock
# ... etc

# Using the provided Makefile target
make molecule-mock
```

### Coverage

All 22 modules have a corresponding mock scenario:

| Scenario | Module |
|----------|--------|
| `application_mock` | `application` |
| `authenticator_mock` | `authenticator` |
| `authenticator_map_mock` | `authenticator_map` |
| `ca_certificate_mock` | `ca_certificate` |
| `feature_flag_mock` | `feature_flag` |
| `http_port_mock` | `http_port` |
| `organization_mock` | `organization` |
| `role_definition_mock` | `role_definition` |
| `role_team_assignment_mock` | `role_team_assignment` |
| `role_user_assignment_mock` | `role_user_assignment` |
| `route_mock` | `route` |
| `service_cluster_mock` | `service_cluster` |
| `service_key_mock` | `service_key` |
| `service_mock` | `service` |
| `service_node_mock` | `service_node` |
| `service_type_mock` | `service_type` |
| `settings_mock` | `settings` |
| `team_mock` | `team` |
| `token_mock` | `token` |
| `ui_plugin_route_mock` | `ui_plugin_route` |
| `users_mock` | `user` |

---

## SECTION 3: Layer 3 — Integration Tests

**Location**: `tests/integration/targets/`  
**Runner**: `ansible-test integration <target>_test --venv --requirements`  
**Requires**: Live AAP Gateway instance + credentials in `integration_config.yml`

Integration tests run against a real AAP Gateway API. They validate:
- The collection works against the actual API version deployed
- Name-to-ID resolution works against real data
- Multi-step operations (create → associate → verify) work in sequence
- Error paths (create duplicate, update non-existent) are handled correctly

### Prerequisites

```bash
# tests/integration/integration_config.yml
---
gateway_host: https://aap.example.com
gateway_username: admin
gateway_password: secret
gateway_validate_ssl: false
```

### Integration Test Target Structure

```
tests/integration/targets/<resource>s_test/
├── tasks/
│   └── main.yml      — test tasks
├── meta/
│   └── main.yml      — depends on setup_gateway role
└── vars/
    └── main.yml      — test-specific variables (optional)
```

### Test Anatomy — Full Integration Test Phases

Each integration test target follows this 9-phase sequence:

**Phase 1: Generate Unique Test ID**

```yaml
- name: Generate a test ID to avoid conflicts
  set_fact:
    test_id: "{{ lookup('password', '/dev/null length=8 chars=ascii_lowercase') }}"
  when: test_id is not defined
```

The test ID ensures:
- Resource names are unique per run (e.g., `test-app-abc123def`)
- Concurrent test runs don't collide
- Failed runs don't leave orphaned resources with predictable names

**Phase 2: Pre-Cleanup (cleanup from failed runs)**

```yaml
- name: Pre-cleanup — delete any leftover test resources
  ansible.platform.application:
    name: "test-app-{{ test_id }}"
    organization: Engineering
    state: absent
  failed_when: false  # Ignore if resource doesn't exist
```

This ensures:
- Test is idempotent (can be run multiple times safely)
- Leftover resources from previous failed runs don't interfere

**Phase 3: Create + Assert**

```yaml
- name: Create application
  ansible.platform.application:
    name: "test-app-{{ test_id }}"
    organization: Engineering
    authorization_grant_type: password
    client_type: public
    state: present
  register: create_result

- name: Assert create succeeded
  assert:
    that:
      - create_result.changed
      - create_result.application.id is defined
      - create_result.application.name == "test-app-{{ test_id }}"
```

Assertions verify:
- `changed: true` (resource was created)
- `id` field populated (resource has stable identity)
- Name matches what was requested

**Phase 4: Idempotency Check (run same create again)**

```yaml
- name: Create application again (idempotency check)
  ansible.platform.application:
    name: "test-app-{{ test_id }}"
    organization: Engineering
    authorization_grant_type: password
    client_type: public
    state: present
  register: idempotent_result

- name: Assert idempotent run did not change
  assert:
    that:
      - not idempotent_result.changed
      - idempotent_result.application.id == create_result.application.id
```

This critical phase verifies:
- Second run does not change the system (`changed: false`)
- ID remains the same (same resource, not re-created)
- No infinite loops or drift

**Phase 5: Exists Check (if `state: exists` is supported)**

```yaml
- name: Check resource exists
  ansible.platform.application:
    name: "test-app-{{ test_id }}"
    organization: Engineering
    state: exists
  register: exists_result

- name: Assert exists check
  assert:
    that:
      - exists_result.exists
      - not exists_result.changed
```

Verifies:
- `state: exists` returns correct boolean
- Gathering state does not change the system

**Phase 6: Update (if applicable)**

```yaml
- name: Update application redirect URIs
  ansible.platform.application:
    name: "test-app-{{ test_id }}"
    organization: Engineering
    redirect_uris:
      - "https://example.com/callback"  # new value
    state: present
  register: update_result

- name: Assert update changed
  assert:
    that:
      - update_result.changed
      - update_result.application.redirect_uris | join(' ') == "https://example.com/callback"
```

Verifies:
- Update triggers `changed: true`
- Updated field has new value
- Other fields remain unchanged

**Phase 7: Update Idempotency (run same update again)**

```yaml
- name: Update application again (idempotency check)
  ansible.platform.application:
    name: "test-app-{{ test_id }}"
    organization: Engineering
    redirect_uris:
      - "https://example.com/callback"
    state: present
  register: update_again

- name: Assert second update is no-op
  assert:
    that:
      - not update_again.changed
```

Verifies the update operation is also idempotent.

**Phase 8: Delete + Assert**

```yaml
- name: Delete application
  ansible.platform.application:
    name: "test-app-{{ test_id }}"
    organization: Engineering
    state: absent
  register: delete_result

- name: Assert delete succeeded
  assert:
    that:
      - delete_result.changed
```

Verifies:
- Deletion triggers `changed: true`
- Resource is removed

**Phase 9: Always — Cleanup Block**

```yaml
- name: Cleanup phase
  block:
    - name: Final cleanup — delete test resource
      ansible.platform.application:
        name: "test-app-{{ test_id }}"
        organization: Engineering
        state: absent
      failed_when: false
  tags: [always]
```

Critical for test hygiene:
- Runs even if earlier phases fail (`tags: [always]`)
- Uses `failed_when: false` (not `ignore_errors: true`) to match ansible-lint rules
- Ensures test infrastructure is cleaned up

### Important Test Hygiene Rules

**1. Always use `test_id` for unique names**

```yaml
# WRONG — hardcoded name, conflicts on second run
- ansible.platform.application:
    name: test-app
    state: present

# RIGHT — unique per run, safe for concurrent execution
- ansible.platform.application:
    name: "test-app-{{ test_id }}"
    state: present
```

**2. Use `failed_when: false`, NOT `ignore_errors: true`**

```yaml
# WRONG — ansible-lint flag: ignore-errors
- name: Cleanup
  ansible.platform.application:
    name: "test-app-{{ test_id }}"
    state: absent
  ignore_errors: true

# RIGHT — preferred by ansible-lint
- name: Cleanup
  ansible.platform.application:
    name: "test-app-{{ test_id }}"
    state: absent
  failed_when: false
```

**3. Always have an `always:` block for cleanup**

```yaml
block:
  - name: Test phases
    # ... all test tasks ...
  
always:
  - name: Cleanup
    ansible.platform.application:
      name: "test-app-{{ test_id }}"
      state: absent
    failed_when: false
```

### Error Patterns in Tests

**Pattern 1: `ignore_errors: true` vs `failed_when: false`**

| Scenario | Use | Example |
|----------|-----|---------|
| Pre-cleanup, resource might not exist | `failed_when: false` | Delete in pre-cleanup phase |
| Always cleanup block | `failed_when: false` | Final cleanup regardless of failures |
| Expect an error as test case | `ignore_errors: true` | "Try to create duplicate and verify error" |

Preference: `failed_when: false` is cleaner and ansible-lint compliant.

**Pattern 2: Resource Guards for Pre-Existing Resources**

Some system resources (like API Port, HTTP Port) already exist in a fresh AAP instance:

```yaml
- name: Create API Port (may already exist)
  ansible.platform.http_port:
    name: api
    port: 6000
    state: present
  register: api_port_create
  ignore_errors: true  # OK here: we expect it might fail with "already exists"

- name: Continue only if create succeeded
  set_fact:
    api_port_id: "{{ api_port_create.http_port.id }}"
  when: api_port_create is not failed
```

Alternatively, use exists check:

```yaml
- name: Check if API Port exists
  ansible.platform.http_port:
    name: api
    state: exists
  register: api_port_exists

- name: Use existing or create new
  set_fact:
    api_port_id: "{{ (api_port_exists.http_port.id if api_port_exists.exists else create_result.http_port.id) }}"
```

### Running Integration Tests

```bash
# Single target
ansible-test integration applications_test --venv --requirements --color yes -vvv

# All targets (requires live AAP)
ansible-test integration --venv --requirements --color yes

# With verbose output for debugging
ansible-test integration applications_test --venv --requirements -vvv 2>&1 | tee test.log
```

---

## Linting Tests

**Location**: `tox.ini` (envlist: `black`, `flake8`, `isort`)  
**Runner**: `python -m tox -e black,flake8,isort`

```bash
# Run all linters
python -m tox -e black,flake8,isort

# Check formatting only (what CI runs)
black --check --line-length 160 plugins/ tests/

# Auto-fix formatting
black --line-length 160 plugins/ tests/
isort --profile black --line-length 160 plugins/ tests/

# Style check
flake8 plugins/ tests/
```

### Important: `tox.ini` has `skip_install = true`

The `[testenv]` section in `tox.ini` includes `skip_install = true`. This prevents
tox from trying to build and install the collection as a Python package (which would
fail because an Ansible collection is not a Python package). Linting tools do not
need the project installed — they read source files directly.

---

## Ansible-lint

**Runner**: `ansible-lint` (run from collection root)

ansible-lint checks YAML task files, molecule scenarios, and module documentation.
The `.ansible-lint` config file excludes known false-positive paths
(e.g. `extensions/molecule/organization_mock/inventory.yml`).

Key rules enforced:
- `yaml[document-end]`: YAML files and embedded YAML docstrings must end with `...`
- `ignore-errors`: Use `failed_when: false` not `ignore_errors: true` for cleanup tasks
- `key-order[task]`: Task keys must be in the standard order (`name:` first)

---

## SECTION 4: Running Tests

### Quick Reference

```bash
# Full test suite (fastest first, slowest last)
pytest tests/unit/ -v                                  # Unit tests (seconds)
molecule test -s application_mock                      # Single mock scenario (30s)
ansible-test integration applications_test --venv      # Single integration (1-5 min)

# All tests together
make test-all  # If Makefile target exists, or:

pytest tests/unit/ -v && \
  molecule test -s application_mock && \
  ansible-test integration applications_test --venv --requirements
```

### Environment Setup

```bash
# Install test dependencies
pip install ansible-core pytest pytest-cov molecule ansible-lint

# Install collection dependencies
ansible-galaxy collection install -r requirements.yml

# Verify mock server is accessible
python tools/mock_gateway_server.py --port 8080
# In another terminal:
curl http://localhost:8080/api/gateway/v1/organizations/
```

---

## SECTION 5: CI Pipeline

### GitHub Actions Workflows

| Workflow | File | Trigger | What runs |
|----------|------|---------|-----------|
| Unit tests | `.github/workflows/unit.yml` | Every commit | `pytest tests/unit/ -v` |
| Linting | `.github/workflows/lint.yml` | Every commit | `tox + ansible-lint` |
| Molecule mock | `.github/workflows/molecule.yml` | Every commit | All `*_mock` scenarios |
| Integration | `.github/workflows/integration.yml` | Manual or on tag | All `*_test` targets (requires AAP) |

### Execution Order

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Unit Tests (fast, ~2s, no network)                           │
│    MUST PASS before proceeding                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Linting (fast, ~5s)                                          │
│    black, isort, flake8, ansible-lint                           │
│    MUST PASS before proceeding                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Molecule Mock Tests (medium, ~1-2 min for all scenarios)     │
│    All 22 *_mock scenarios run in parallel (if CI allows)       │
│    MUST PASS before proceeding                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Integration Tests (slow, ~5-15 min, requires live AAP)       │
│    Only runs on manual trigger or tagged releases                │
│    Requires valid AAP instance + credentials                    │
└─────────────────────────────────────────────────────────────────┘
```

### Example GitHub Actions Workflow

```yaml
# .github/workflows/molecule.yml
name: Molecule Mock Tests

on:
  push:
    branches: [devel, main]
  pull_request:

jobs:
  molecule:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        scenario: [
          application_mock,
          organization_mock,
          users_mock,
          # ... all 22 scenarios
        ]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install molecule ansible-core
          ansible-galaxy collection install -r requirements.yml
      
      - name: Run Molecule scenario
        run: |
          cd extensions/molecule/${{ matrix.scenario }}
          molecule converge
          molecule verify
        env:
          MOCK_SERVER_URL: http://localhost:8080
```

---

## SECTION 6: Test Coverage Requirements

### Which Tests Cover Which Scenarios

| Scenario | Unit | Molecule | Integration | Notes |
|----------|------|----------|-------------|-------|
| **Create resource** | — | ✅ | ✅ | First run, `changed: true` |
| **Create idempotency** | — | ✅ | ✅ | Second run same params, `changed: false` |
| **Read (exists)** | — | ✅ | ✅ | `state: exists` check |
| **Update field** | — | ✅ | ✅ | Change one field, `changed: true` |
| **Update idempotency** | — | ✅ | ✅ | Second update same params, `changed: false` |
| **Delete resource** | — | ✅ | ✅ | `state: absent`, `changed: true` |
| **Delete idempotency** | — | ✅ | ✅ | Delete non-existent, `changed: false` |
| **Ref field resolution** | ✅ | ✅ | ✅ | Name → ID lookup, ID → Name reverse |
| **Transform mixin** | ✅ | ✅ | — | Ansible model ↔ API model roundtrip |
| **Registry discovery** | ✅ | — | — | Module found by APIVersionRegistry |
| **Version fallback** | ✅ | — | — | Requesting v99 falls back to v1 |
| **check_mode** | — | ✅ | ✅ | No API calls, correct `changed` |
| **Error handling** | ✅ | — | ✅ | Invalid input, not-found, permission error |
| **Write-only fields** | ✅ | ✅ | ✅ | Password never in output |
| **Read-only fields** | — | ✅ | ✅ | `id`, `created` in output |

### Test Requirements Per Module

For any new platform action plugin, these tests MUST exist:

| Layer | Test Type | File | Required? |
|-------|-----------|------|-----------|
| 1 (Unit) | Transform roundtrip | `tests/unit/...test_<resource>.py` | Recommended |
| 2 (Mock) | Full CRUD lifecycle | `extensions/molecule/<resource>_mock/` | **Yes** |
| 3 (Integration) | Live API test | `tests/integration/targets/<resource>s_test/` | **Yes** |

### Before Merging

```
Layer 1 (Unit):      ✅ PASSING
Layer 2 (Mock):      ✅ PASSING
Layer 3 (Integration): ✅ PASSING (or N/A if live AAP unavailable)
Linting:             ✅ PASSING (black, isort, flake8, ansible-lint)
```

---

## SECTION 7: What Each Layer Catches

| Bug Category | Unit | Molecule Mock | Integration |
|-------------|------|--------------|-------------|
| Registry/loader logic error | ✅ | — | — |
| Connection plugin routing bug | ✅ | — | — |
| Transform mixin field mapping error | ✅ | ✅ | ✅ |
| Idempotency logic failure | — | ✅ | ✅ |
| check_mode violation | — | ✅ | ✅ |
| Ref field ID comparison bug | — | ✅ | ✅ |
| API version incompatibility | — | — | ✅ |
| Secondary endpoint ordering bug | — | ✅ | ✅ |
| Real API schema mismatch | — | — | ✅ |
| Name-to-ID resolution failure | ✅ | ✅ | ✅ |
| Manager process lifecycle bug | ✅ | — | — |
| Write-only field leak (password) | ✅ | ✅ | ✅ |
| Module not discovered by registry | ✅ | — | — |
| Type mismatch (int vs str) in comparison | ✅ | ✅ | ✅ |
| Always block cleanup failure | — | ✅ | ✅ |
| Test ID collision (concurrent runs) | — | ✅ | ✅ |

