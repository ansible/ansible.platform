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

## Layer 1: Unit Tests

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
to resolve correctly. See [conftest.py](../conftest.py).

---

## Layer 2: Molecule Mock Tests

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

### Scenario Structure

Each mock scenario has four files:

```
extensions/molecule/<resource>_mock/
├── molecule.yml      — driver config (local connection, no containers)
├── converge.yml      — the test playbook (create + idempotency + update + delete)
├── verify.yml        — assertions on final state (optional additional checks)
└── cleanup.yml       — ensure test resources are removed after the run
```

### Standard converge.yml Pattern

All mock scenarios follow this pattern:

```yaml
---
- name: Converge
  hosts: localhost
  gather_facts: false

  tasks:
    - name: Run create (first time)
      ansible.platform.<resource>:
        <primary_key>: test-value
        state: present
      register: first_run

    - name: Assert first run changed
      assert:
        that:
          - first_run.changed
          - first_run.id is defined

    - name: Run again (idempotency check)
      ansible.platform.<resource>:
        <primary_key>: test-value
        state: present
      register: second_run

    - name: Assert idempotent run did not change
      assert:
        that:
          - not second_run.changed

    - name: Verify exists check
      ansible.platform.<resource>:
        <primary_key>: test-value
        state: exists
      register: exists_check

    - name: Assert exists
      assert:
        that:
          - exists_check.exists

    - name: Delete the resource
      ansible.platform.<resource>:
        <primary_key>: test-value
        state: absent
      register: delete_run

    - name: Assert deletion changed
      assert:
        that:
          - delete_run.changed

    - name: Delete again (idempotency)
      ansible.platform.<resource>:
        <primary_key>: test-value
        state: absent
      register: delete_again

    - name: Assert second delete is no-op
      assert:
        that:
          - not delete_again.changed
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

## Layer 3: Integration Tests

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
gateway_verify_ssl: false
```

### Running Integration Tests

```bash
# Single target
ansible-test integration users_test --venv --requirements --color yes -vvv

# All targets
ansible-test integration --venv --requirements --color yes

# With verbose output for debugging
ansible-test integration users_test --venv --requirements -vvv 2>&1 | tee test.log
```

### Target Structure

```
tests/integration/targets/users_test/
├── tasks/
│   └── main.yml      — test tasks
├── meta/
│   └── main.yml      — depends on setup_gateway role
└── vars/
    └── main.yml      — test-specific variables (optional)
```

### Test Phases in Each Target

Each integration test target follows this sequence:

1. **Pre-cleanup**: Delete any resources left over from previous failed runs
   ```yaml
   - name: Delete test user if exists (pre-cleanup)
     ansible.platform.user:
       username: "test-{{ test_id }}"
       state: absent
     failed_when: false
   ```

2. **Create + assert**: Verify resource creation
3. **Idempotency**: Run create again, assert `changed: false`
4. **Update**: Modify a field, assert `changed: true`
5. **Update idempotency**: Same update again, assert `changed: false`
6. **exists check**: Verify `state: exists` works
7. **Delete + assert**: Verify deletion
8. **Delete idempotency**: Delete again, assert `changed: false`
9. **Always cleanup**: `failed_when: false` in a `block: ... always:` construct

### Important Test Hygiene Rules

- Use `set_fact: test_id: "{{ lookup('password', ...) }}"` to generate unique resource
  names per run — prevents conflicts with existing data and between concurrent runs.
- **Never** use `ignore_errors: true` for cleanup. Use `failed_when: false` instead
  (ansible-lint enforces this — `ignore-errors` is flagged).
- Always have an `always:` cleanup block so failed tests don't leave orphaned resources.

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

## What Each Layer Catches

| Bug Category | Unit | Molecule Mock | Integration |
|-------------|------|--------------|-------------|
| Registry/loader logic error | ✅ | — | — |
| Connection plugin routing bug | ✅ | — | — |
| Transform mixin field mapping error | — | ✅ | ✅ |
| Idempotency logic failure | — | ✅ | ✅ |
| check_mode violation | — | ✅ | ✅ |
| Ref field ID comparison bug | — | ✅ | ✅ |
| API version incompatibility | — | — | ✅ |
| Secondary endpoint ordering bug | — | ✅ | ✅ |
| Real API schema mismatch | — | — | ✅ |
| Name-to-ID resolution failure | — | ✅ | ✅ |
| Manager process lifecycle bug | ✅ | — | — |
| Write-only field leak (password) | — | ✅ | ✅ |

---

## Adding Tests for a New Module

When adding a new resource module (see [07-adding-resources.md](07-adding-resources.md)):

1. **Molecule mock scenario** (required, fastest validation):
   - Copy `extensions/molecule/users_mock/` to `extensions/molecule/<resource>_mock/`
   - Update `converge.yml` with the new module name and its parameters

2. **Integration test target** (required):
   - Create `tests/integration/targets/<resource>s_test/tasks/main.yml`
   - Follow the seven-phase pattern above

3. **Unit test** (optional but recommended for complex transform logic):
   - Add `tests/unit/plugins/plugin_utils/api/v1/test_<resource>.py`
   - Mock `TransformContext` and verify `from_ansible_data` and `from_api` round-trips

---

## CI Workflows

| Workflow | File | What runs |
|----------|------|-----------|
| Unit tests | `.github/workflows/unit.yml` | `pytest tests/unit/ -v` |
| Linting | `.github/workflows/lint.yml` | `tox -e black,flake8,isort` + `ansible-lint` |
| Molecule mock | `.github/workflows/molecule.yml` | All `*_mock` scenarios |
| Integration | `.github/workflows/integration.yml` | All `*_test` targets (requires AAP) |
