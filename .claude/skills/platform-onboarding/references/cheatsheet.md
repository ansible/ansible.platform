# Platform Collection — Developer Cheatsheet

Quick reference for day-to-day development on `ansible.platform`.

---

## Directory Quick-Find

| I need to... | Look in |
|-------------|---------|
| Add/edit an action plugin | `plugins/action/<resource>.py` |
| See the base class all plugins inherit | `plugins/action/base_action.py` |
| Find/edit the Ansible-facing dataclass | `plugins/plugin_utils/ansible_models/<resource>.py` |
| Find/edit the API model + transform mixin | `plugins/plugin_utils/api/v1/<resource>.py` |
| Find the module documentation stub | `plugins/modules/<resource>.py` |
| Understand connection routing | `plugins/connection/http.py` |
| See how the manager subprocess works | `plugins/plugin_utils/manager/platform_manager.py` |
| See how the RPC client connects | `plugins/plugin_utils/manager/rpc_client.py` |
| See how subprocesses are spawned | `plugins/plugin_utils/manager/process_manager.py` |
| See the subprocess entry point | `plugins/plugin_utils/manager/manager_process.py` |
| Find/add unit tests | `tests/unit/` |
| Find/add integration tests | `tests/integration/targets/<resource>s_test/` |
| Find/add Molecule mock scenarios | `extensions/molecule/<resource>_mock/` |
| Generate boilerplate for a new module | `tools/generate_resource.py` |

---

## Three Plugin Patterns

### Pattern A — Declarative (simplest)

Use when: All fields map 1:1 to the API, no special logic needed.

```python
# plugins/action/organization.py — entire file
from .base_action import BaseResourceActionPlugin


class ActionModule(BaseResourceActionPlugin):
    resource_type = "organization"
```

That's it. Three lines. The base class handles everything.

### Pattern B — Hook-based

Use when: You need side effects (e.g., post-create setup) or extra validation.

```python
class ActionModule(BaseResourceActionPlugin):
    resource_type = "authenticator"

    def _post_create(self, result, ansible_data, api_data):
        # Trigger map sync after creating authenticator
        self._trigger_sync(result)
        return result
```

Available hooks: `_pre_create`, `_post_create`, `_pre_update`, `_post_update`,
`_pre_delete`, `_post_delete`, `_custom_exists`.

### Pattern C — Orchestration-only custom `run()`

Use when: Multi-step Ansible workflows that still delegate all HTTP to the SDK
(for example `user.py`, `role_team_assignment.py`).

**Do not** use Pattern C to add `manager.session` HTTP, association sub-endpoints,
or survey/copy logic — put that in the transform mixin
([05-design-principles.md §3a](../../docs/05-design-principles.md)).

```python
class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "user"
    MODEL_CLASS = AnsibleUser
    _WRITE_ONLY_FIELDS = frozenset({"update_secrets"})

    def run(self, tmp=None, task_vars=None):
        # Orchestrate multiple manager.execute() calls if needed.
        # All HTTP stays in PlatformService — required for MCP (#206) parity.
        return super().run(tmp, task_vars)
```

---

## Seven-File Workflow (New Module)

### Step 1: Generate boilerplate (ALWAYS use the generator)

```bash
# Gateway resources
python tools/generate_resource.py \
    --tag <openapi_tag> \
    --spec ../aap-openapi-specs/2.6/gateway.json \
    --dry-run

# EDA resources (auto-detects /api/eda/v1/ prefix)
python tools/generate_resource.py \
    --tag projects \
    --spec ../aap-openapi-specs/eda.json \
    --dry-run

# List available tags in any spec
python tools/generate_resource.py --spec <spec.json> --list-tags

# Generate for real (remove --dry-run)
python tools/generate_resource.py \
    --tag <openapi_tag> \
    --spec <spec.json>
```

**Do NOT hand-write files from scratch.** The generator ensures correct
endpoint paths, service-specific prefixes, and field classification.

### Step 2: Review generated files

- `plugins/modules/<resource>.py` — Fix DOCUMENTATION, add EXAMPLES
- `plugins/plugin_utils/ansible_models/<resource>.py` — Verify AnsibleFoo fields

### Step 3: Implement the transform mixin

In `plugins/plugin_utils/api/v1/<resource>.py`:

```python
class FooTransformMixin_v1:
    LOOKUP_FIELD = "name"  # Unique identifier
    API_ENDPOINT = "foos"  # Gateway API path fragment

    # Ref fields: Ansible name → API integer ID
    REF_FIELDS = {
        "organization": ("organizations", "name"),
    }

    # Write-only: accepted on create/update, never returned by GET
    WRITE_ONLY_FIELDS = ["password"]

    def to_api(self, ansible_data):
        """AnsibleFoo → APIFoo_v1"""
        ...

    def to_ansible(self, api_data):
        """APIFoo_v1 → AnsibleFoo"""
        ...
```

### Step 4: Choose action plugin pattern

- No custom logic needed → Pattern A (3 lines)
- Need hooks → Pattern B
- Need multi-step orchestration via `manager.execute()` → Pattern C (not HTTP in action plugin)

### Step 5–7: Tests

- Write integration tests in `tests/integration/targets/`
- Create Molecule mock scenario in `extensions/molecule/`
- Add unit tests for complex transform logic

---

## Common Commands

```bash
# Run unit tests
pytest tests/unit/ -v

# Run specific unit test
pytest tests/unit/ -v -k "test_registry"

# Run Molecule mock test
molecule test -s <resource>_mock

# Run linting
ansible-test sanity --docker -v

# Verify action plugins do not call HTTP directly
make check_action_plugin_invariants

# Check registry discovers your module
python -c "
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry \
    import APIVersionRegistry
r = APIVersionRegistry()
modules = r.discover_modules()
print([m for m in modules if '<resource>' in m])
"

# Start mock Gateway server (for Molecule)
python tools/mock_gateway_server.py --port 8080
```

---

## Data Flow Trace (Mental Model)

```
playbook task: ansible.platform.team: name: eng, org: "Red Hat"
    │
    ▼
ActionModule.run()                          # plugins/action/team.py
    │
    ▼
base_action._get_or_spawn_manager()         # plugins/action/base_action.py
    │
    ├─ persistent mode ──► ManagerRPCClient  # rpc_client.py
    │                        │
    │                        ▼ (Unix socket)
    │                      PlatformService   # platform_manager.py
    │
    └─ direct mode ────► DirectHTTPClient    # in-process, no subprocess
                           │
                           ▼
                     Transform Mixin
                     AnsibleTeam("eng", org="Red Hat")
                           │
                           ▼ resolve org name → ID
                     APITeam_v1(name="eng", organization=42)
                           │
                           ▼
                     HTTP POST /api/gateway/v1/teams/
```

---

## Key Concepts to Remember

**Idempotency**: `state: present` checks if the resource exists and matches.
If yes → `changed: false`. If no → create/update → `changed: true`.

**Ref field resolution**: When a playbook says `organization: "Red Hat"`,
the transform mixin automatically resolves `"Red Hat"` → integer ID `42`
by querying the Gateway API.

**Version isolation**: API changes go in new `api/v2/` directory. The Registry
auto-detects. Ansible Models and action plugins never change.

**Persistent manager**: One subprocess per play, shared across all tasks.
Solves Python 3.12 fork-safety issues on macOS. Auto-terminates after idle
timeout (default 3600s).

---

## PR Checklist

- [ ] Jira reference in PR title: `[AAP-XXXXX] Short description`
- [ ] PR template filled completely
- [ ] Unit tests pass: `pytest tests/unit/ -v`
- [ ] Molecule mock tests pass: `molecule test -s <resource>_mock`
- [ ] `safe to test` label applied for integration CI
- [ ] 2+ approvals obtained
- [ ] CasC team tagged if change affects modules, auth, or return values

---

## Glossary (Quick)

| Term | Meaning |
|------|---------|
| Ansible Model | Stable user-facing dataclass (e.g., `AnsibleUser`) |
| API Model | Version-specific Gateway API dataclass (e.g., `APIUser_v1`) |
| Transform Mixin | Maps between Ansible ↔ API models, resolves references |
| PlatformManager | Subprocess that owns the HTTP session |
| PlatformService | HTTP client + transform engine inside the manager |
| ManagerRPCClient | Client stub for talking to PlatformManager via Unix socket |
| Lookup field | Unique ID for a resource (e.g., `username`, `name`) |
| Ref field | Field referencing another resource (name→ID resolution) |
| Write-only field | Accepted on create/update, never returned by API |
