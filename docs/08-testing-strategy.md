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

## Layer 2: Molecule Tests

Layer 2 is split into two sub-tiers that share the same mock Gateway infrastructure:

| Sub-tier | Location | What it tests |
|----------|----------|---------------|
| **Mock smoke tests** | `extensions/molecule/<resource>_mock/` | Basic create/update/delete/gathered across all 3 connection modes |
| **Integration scenarios** | `extensions/molecule/<resource>_integration/` | All 5 states with full `before`/`after` content assertions, multi-resource `overridden`, non-existent resource edge cases |

### Layer 2a: Mock Smoke Tests

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

All mock scenarios follow the resource module pattern. Here is the **actual
`users_mock/converge.yml`** as a reference (simplified):

```yaml
---
- name: Converge — user (mock, connection local)
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    molecule_username: molecule-test-user
    gateway_hostname: "http://127.0.0.1:8000"
    gateway_username: mock
    gateway_password: testpass
    gateway_validate_certs: false

  tasks:
    # ── 1. Create ───────────────────────────────────────────────────────────
    - name: Create user (connection local)
      ansible.platform.users:
        config:
          - username: "{{ molecule_username }}"
            first_name: Molecule
            last_name: TestUser
            email: molecule-test@mock.example.com
            password: MockPass123!
            is_superuser: false
        state: merged
        gateway_hostname: "{{ gateway_hostname }}"
        gateway_username: "{{ gateway_username }}"
        gateway_password: "{{ gateway_password }}"
        gateway_validate_certs: "{{ gateway_validate_certs }}"
      register: create_result

    - name: Assert create changed
      ansible.builtin.assert:
        that:
          - create_result is changed
          - create_result.after | length > 0
          - "'molecule-test-user' in (create_result.after | map(attribute='username') | list)"

    # ── 2. Idempotency (no change) ──────────────────────────────────────────
    - name: Run again idempotency (connection local)
      ansible.platform.users:
        config:
          - username: "{{ molecule_username }}"
            first_name: Molecule
            last_name: TestUser
            email: molecule-test@mock.example.com
            is_superuser: false
        state: merged
        # ... gateway args ...
      register: idem_result

    - name: Assert idempotent run did not change
      ansible.builtin.assert:
        that:
          - idem_result is not changed   # ← key: no PATCH issued

    # ── 3. Update ───────────────────────────────────────────────────────────
    - name: Update user email and last_name (connection local)
      ansible.platform.users:
        config:
          - username: "{{ molecule_username }}"
            last_name: UpdatedUser
            email: molecule-updated@mock.example.com
        state: merged
        # ... gateway args ...
      register: update_result

    - name: Assert update changed
      ansible.builtin.assert:
        that:
          - update_result is changed    # ← PATCH was issued

    # ── 4. Gathered (read-only) ─────────────────────────────────────────────
    - name: Check user exists (state gathered)
      ansible.platform.users:
        config:
          - username: "{{ molecule_username }}"
        state: gathered
        # ... gateway args ...
      register: exists_result

    - name: Assert exists returns correct data
      ansible.builtin.assert:
        that:
          - exists_result is not changed
          - exists_result.gathered | length > 0
          - exists_result.gathered[0].username == molecule_username

    # ── 5. Delete ───────────────────────────────────────────────────────────
    - name: Delete user (connection local)
      ansible.platform.users:
        config:
          - username: "{{ molecule_username }}"
        state: deleted
        # ... gateway args ...
      register: delete_result

    - name: Assert delete changed
      ansible.builtin.assert:
        that:
          - delete_result is changed

    # ── 6. Delete idempotency ───────────────────────────────────────────────
    - name: Delete again (idempotency)
      ansible.platform.users:
        config:
          - username: "{{ molecule_username }}"
        state: deleted
        # ... gateway args ...
      register: delete_idem_result

    - name: Assert second delete is a no-op
      ansible.builtin.assert:
        that:
          - delete_idem_result is not changed
```

### Expected terminal output (passing run)

```
PLAY [Converge — user (mock, connection local)] ***********************

TASK [Create user (connection local)] *********************************
changed: [localhost]

TASK [Assert create changed] ******************************************
ok: [localhost]

TASK [Run again idempotency (connection local)] ***********************
ok: [localhost]           ← 'ok' (not 'changed') = idempotency confirmed

TASK [Assert idempotent run did not change (connection local)] ********
ok: [localhost]

TASK [Update user email and last_name (connection local)] *************
changed: [localhost]      ← 'changed' = PATCH was issued

TASK [Assert update changed] ******************************************
ok: [localhost]

TASK [Run update again idempotency (connection local)] ****************
ok: [localhost]           ← idempotency on update confirmed

TASK [Check user exists (state gathered, connection local)] ***********
ok: [localhost]

TASK [Assert exists returns correct data] *****************************
ok: [localhost]

TASK [Delete user (connection local)] *********************************
changed: [localhost]      ← 'changed' = DELETE was issued

TASK [Assert delete changed] ******************************************
ok: [localhost]

TASK [Delete again (idempotency, connection local)] *******************
ok: [localhost]           ← 'ok' = no DELETE on absent resource

TASK [Assert second delete is a no-op] ********************************
ok: [localhost]

PLAY RECAP ************************************************************
localhost : ok=13  changed=3  unreachable=0  failed=0  skipped=0

                          ↑
       Exactly 3 changed: create + update + delete — correct.
       0 failed: all assertions passed.
```

### Common failure signatures

| Symptom | Root cause | Fix |
|---------|-----------|-----|
| `changed=true` on 2nd merged run | `_config_matches` returns False | Check if field types differ (str vs int) |
| `failed: [localhost]: FAILED! => assertion failed` on idempotency | Module re-creates or re-PATCHes | Add debug task to print `before`/`after` |
| `changed=false` on create | User already exists in mock store from a failed previous run | Run `molecule cleanup` then retry |
| `HTTPError 404` on PATCH | `SYSTEM_KEY` not being resolved to `id` | Check `CANONICAL_KEY` and `SYSTEM_KEY` on `AnsibleUser` |

### Running Mock Smoke Tests

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

### Layer 2b: Integration Scenarios

**Location**: `extensions/molecule/<resource>_integration/`
**Runner**: `molecule test -s organization_integration`
**Requires**: Mock Gateway server (same as mock smoke tests)

Integration scenarios go further than smoke tests. Each one covers **all 5 resource-module
states** in a single sequential `converge.yml`, and every assertion checks the **content**
of `before` and `after`, not just whether `changed` was true or false.

#### What integration scenarios add over mock smoke tests

| Capability | Mock smoke test | Integration scenario |
|-----------|----------------|---------------------|
| `merged` (create/update) | ✅ (changed/not-changed) | ✅ + before/after content assertions |
| `replaced` | ❌ | ✅ |
| `overridden` | ❌ | ✅ (seeds extras that must be deleted) |
| `gathered` (all / specific / missing) | partial | ✅ all 3 cases |
| `deleted` (delete / idempotent / non-existent) | partial | ✅ all 3 cases |
| before/after content verified | ❌ | ✅ |
| Multi-resource overridden proof | ❌ | ✅ |

#### Scenario structure

Each scenario has the same 4-file layout as a mock scenario:

```
extensions/molecule/<resource>_integration/
├── molecule.yml      — driver config (same as _mock)
├── inventory.yml     — gateway vars (same as _mock)
├── converge.yml      — 6 sequential plays (setup + merged + replaced + overridden + gathered + deleted)
├── verify.yml        — confirm final state (only r1 remains, r0 is gone)
└── cleanup.yml       — idempotent deletion of all test resources
```

#### converge.yml play structure

```
Play 0: Setup    — wait for mock Gateway, create survive flag
Play 1: merged   — CREATE r0 + r1, assert before=[], after has both
                   UPDATE r0 only, assert before.field == v1, after.field == v2
                   Idempotent: assert not changed
Play 2: replaced — REPLACE r0 (full object), r1 untouched
                   Assert before vs after diff, idempotent
Play 3: overridden — SEED r2 + r3 extras, then override to [r0, r1] only
                    Assert before has 4, after has exactly 2, r2/r3 absent
                    Idempotent: assert not changed
Play 4: gathered — A) gather all → count, B) gather r0 by key → length==1
                   C) gather non-existent → length==0, not failed
Play 5: deleted  — A) delete r0 → before has it, after doesn't
                   B) delete r0 again → not changed
                   C) delete never-existed → not changed, not failed
```

#### Example: organization integration assertions

The before/after assertions look like this (as opposed to mock tests that only check `is changed`):

```yaml
# merged: assert before captured OLD description
- name: "merged | Assert before captured old description"
  ansible.builtin.assert:
    that:
      - (update_result.before | selectattr('name','equalto','int-org-alpha') | first).description == 'Alpha initial'

# merged: assert after shows NEW description
- name: "merged | Assert after shows new description"
  ansible.builtin.assert:
    that:
      - (update_result.after | selectattr('name','equalto','int-org-alpha') | first).description == 'Alpha updated'

# overridden: the critical set-equality proof
- name: "overridden | Assert after contains ONLY the 2 desired orgs"
  ansible.builtin.assert:
    that:
      - overridden_result.after | selectattr('name','equalto','int-org-gamma') | list | length == 0
      - overridden_result.after | selectattr('name','equalto','int-org-delta') | list | length == 0
      - overridden_result.after | selectattr('name','search','^int-org-') | list | length == 2
```

#### Generating integration scenarios

Integration scenarios are generated from `tools/generate_integration_tests.py` using
per-module fixture data (resource names, field values, extra seeds):

```bash
# Generate for one module
python tools/generate_integration_tests.py team

# Generate for all modules (skips hand-crafted organization + user)
python tools/generate_integration_tests.py --all

# Overwrite an existing generated scenario
python tools/generate_integration_tests.py team --force

# Dry-run (print converge.yml to stdout without writing)
python tools/generate_integration_tests.py team --dry-run

# List modules that have fixture definitions
python tools/generate_integration_tests.py --list
```

To add a new module's integration scenario, add its fixture to the `FIXTURES` dict in
`generate_integration_tests.py`:

```python
"my_module": ModuleFixture(
    canonical_field="name",
    prefix="int-mym-",
    resources=[
        {"name": "int-mym-alpha", "description": "Alpha"},
        {"name": "int-mym-beta",  "description": "Beta"},
    ],
    update_config={"name": "int-mym-alpha", "description": "Alpha updated"},
    replaced_config={"name": "int-mym-alpha", "description": "Alpha replaced"},
    extra_seeds=[{"name": "int-mym-gamma", "description": "Seed"}],
),
```

Modules automatically skipped (require manual scenarios):
- `settings` — singleton (`CANONICAL_KEY=None`), no list, uses GET+PATCH `/settings/all/`
- `role_team_assignment`, `role_user_assignment` — category C (content-matched, no name key)
- `feature_flag`, `authenticator_user` — `SUPPORTS_DELETE=False`, limited state set

#### Coverage

17 modules have generated integration scenarios (all 5 states):

```
application_integration         authenticator_integration
authenticator_map_integration   ca_certificate_integration
http_port_integration           organization_integration
role_definition_integration     route_integration
service_integration             service_cluster_integration
service_key_integration         service_node_integration
service_type_integration        team_integration
token_integration               ui_plugin_route_integration
user_integration
```

#### Running integration scenarios

```bash
# Run single integration scenario
molecule test -s organization_integration

# Run all integration scenarios
for s in extensions/molecule/*_integration; do
    scenario=$(basename "$s")
    echo "=== $scenario ==="
    molecule test -s "$scenario"
done

# Run just converge phase (skip cleanup for debugging)
molecule converge -s organization_integration
molecule verify  -s organization_integration
```

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
     ansible.platform.users:
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

| Bug Category | Unit | Mock smoke | Integration scenario | Live AAP |
|-------------|------|-----------|---------------------|----------|
| Registry/loader logic error | ✅ | — | — | — |
| Connection plugin routing bug | ✅ | — | — | — |
| Transform mixin field mapping error | — | ✅ | ✅ | ✅ |
| Idempotency logic failure (merged) | — | ✅ | ✅ | ✅ |
| replaced does not delete unlisted items | — | — | ✅ | ✅ |
| overridden deletes extras correctly | — | — | ✅ | ✅ |
| before/after content correctness | — | — | ✅ | ✅ |
| gathered empty-list on missing resource | — | partial | ✅ | ✅ |
| delete of non-existent is no-op | — | partial | ✅ | ✅ |
| check_mode violation | — | ✅ | ✅ | ✅ |
| API version incompatibility | — | — | — | ✅ |
| Real API schema mismatch | — | — | — | ✅ |
| Name-to-ID resolution failure | — | ✅ | ✅ | ✅ |
| Manager process lifecycle bug | ✅ | — | — | — |
| Write-only field leak (password) | — | — | ✅ | ✅ |

---

## Adding Tests for a New Module

When adding a new resource module (see [07-adding-resources.md](07-adding-resources.md)):

1. **Molecule mock scenario** (required, fastest validation):
   - Copy `extensions/molecule/users_mock/` to `extensions/molecule/<resource>_mock/`
   - Update `converge.yml` with the new module name and its parameters

2. **Molecule integration scenario** (required, full state coverage):
   - Add a `ModuleFixture` entry to `tools/generate_integration_tests.py`
   - Run `python tools/generate_integration_tests.py <resource>`
   - Review the generated `converge.yml` and customise if needed

3. **Integration test target** (required):
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
| Molecule integration | `.github/workflows/molecule.yml` | All `*_integration` scenarios |
| Integration | `.github/workflows/integration.yml` | All `*_test` targets (requires live AAP) |
