# Agent Collaboration Guide

This document defines how AI agents (Cursor, Copilot, Claude, or any code-generation
assistant) should work within the `ansible.platform` codebase. It covers role
identification, development phases, coding standards, quality gates, and
human-in-the-loop boundaries.

**Read this document before using an AI agent to add a resource, fix a bug, or
modify the framework.**

---

## Quick Start

1. Load **this document** to understand the rules.
2. Load [06-foundation-components.md](06-foundation-components.md) to understand the framework.
3. Load [07-adding-resources.md](07-adding-resources.md) for the step-by-step workflow.
4. Work one step at a time. Confirm each deliverable before proceeding.

---

## Role Identification

Before starting any task, identify which role applies:

### Persona A: Framework Developer

**Scope**: Changes to `plugins/plugin_utils/platform/`, `plugins/plugin_utils/manager/`,
`plugins/action/base_action.py`, `plugins/connection/http.py`.

**Characteristics**:
- Touches components shared by all 22 modules
- Changes here affect every resource module
- Requires deep understanding of `multiprocessing.managers` and Ansible's fork model
- Higher risk — a bug here breaks the entire collection

**When to invoke**: New base class capability, manager lifecycle change, connection
plugin improvement, registry/loader enhancement.

**Human review required**: Always. Framework changes must be reviewed by a human
before merging, regardless of test results.

### Persona B: Feature Developer

**Scope**: Adding a new resource module (7 files as described in
[07-adding-resources.md](07-adding-resources.md)).

**Characteristics**:
- Self-contained: changes are isolated to the new resource's files
- Low risk to existing modules
- Highly mechanical: follows a defined pattern
- Well-suited for AI-assisted generation from `DOCUMENTATION` strings

**When to invoke**: New module, new API version for existing module, mock scenario,
integration test.

**Human review required**: Transform mixin business logic, reference field handling,
write-only field treatment.

---

## Phase-by-Phase Guidance

### Feature Developer Workflow

The 7-step workflow from [07-adding-resources.md](07-adding-resources.md) maps to agent
phases:

**Phase 1 — Write DOCUMENTATION** *(human-led)*

The human writes the `DOCUMENTATION` string. This is the contract. Do not generate it —
the module interface is a product decision, not a mechanical output.

Agent role: Validate the YAML structure, check required keys, verify `extends_documentation_fragment` values.

**Phase 2 — Generate Ansible Model** *(agent-safe)*

Mechanically translate `DOCUMENTATION.options` to `@dataclass` fields. The mapping is:

```
type: str, required: true   →   field_name: str
type: str, required: false  →   field_name: Optional[str] = None
type: bool                  →   field_name: Optional[bool] = None
type: int                   →   field_name: Optional[int] = None
type: list                  →   field_name: Optional[List[str]] = None
type: dict                  →   field_name: Optional[Dict[str, Any]] = None
reference to another resource  →  field_name: Optional[Union[str, int]] = None
```

Always add `state: str = 'present'` and the read-only fields:
`id: Optional[int] = None`, `created: Optional[str] = None`,
`modified: Optional[str] = None`.

**Phase 3 — Generate API Model skeleton** *(agent-safe)*

Copy the Ansible model fields, rename reference fields to use integer IDs:
- `organization: Optional[str]` → `organization: Optional[int]`
- `service_cluster: Optional[str]` → `service_cluster: Optional[int]`

Class name convention: `API<PascalCase>_v1`.

**Phase 4 — Implement Transform Mixin** *(human review required)*

The agent can generate the skeleton and handle simple 1:1 fields. The human must review:
- Reference field name-to-ID resolution calls
- Conditional field logic (write-only fields, enforced state nulls)
- Secondary endpoint declarations
- Lookup field and query params

**Phase 5 — Create Action Plugin** *(agent-safe for standard resources)*

Copy the standard `ActionModule` template from [07-adding-resources.md](07-adding-resources.md).
Replace `MODULE_NAME`. The `_is_idempotent` method may need customisation for resources
with reference fields (see Design Principle 7).

**Phase 6 — Write Integration Test** *(agent-safe)*

Copy the standard integration test template. Replace resource name and primary key.
Follow the seven-phase pattern exactly.

**Phase 7 — Write Mock Scenario** *(agent-safe)*

Copy the standard `converge.yml` template. Replace module name and primary key.

---

## Coding Standards

These standards apply to all agent-generated code. Violations will fail CI.

### Python Standards

**Formatting**: `black` with `line-length = 160`. Run `black --line-length 160 <file>` after every generation.

**Imports**: `isort` with `profile = black`. All imports sorted. Standard library → third-party → local.

**Style**: `flake8` with `max-line-length = 160`. No `E402` in module stubs.

**Docstrings**: Modules must have `DOCUMENTATION` and `EXAMPLES`. Classes and non-trivial
methods should have docstrings. Obvious one-liners do not need comments.

**No magic strings**: Version numbers, operation names, and state values must match
the exact strings used by the framework:
- Operations: `'create'`, `'update'`, `'delete'`, `'find'`, `'enforced'`
- States: `'present'`, `'absent'`, `'exists'`, `'enforced'`, `'merged'`

**Type hints**: All method signatures must have type hints. Return types required.

**No `ignore_errors: true`**: Use `failed_when: false` in YAML files.

### YAML Standards

**Document end marker**: All YAML files must end with `...` on the last line.
This includes `molecule.yml`, `converge.yml`, `verify.yml`, `cleanup.yml`,
and all integration test `main.yml` files.

**Key order in tasks**:
```yaml
- name: Task name     # FIRST
  when: condition     # SECOND (if present)
  block:              # THEN other keys
    ...
```

**Embedded YAML in Python docstrings**: The `EXAMPLES` string must also end with `...`
before the closing `"""`.

### Naming Conventions

| Item | Pattern | Example |
|------|---------|---------|
| Module | `snake_case` | `service_cluster` |
| Ansible model | `Ansible<PascalCase>` | `AnsibleServiceCluster` |
| API model | `API<PascalCase>_v<N>` | `APIServiceCluster_v1` |
| Transform mixin | `<PascalCase>TransformMixin_v<N>` | `ServiceClusterTransformMixin_v1` |
| Action plugin class | Always `ActionModule` | `ActionModule` |
| Integration target | `<resource>s_test` | `service_clusters_test` |
| Molecule scenario | `<resource>_mock` | `service_cluster_mock` |

---

## Human-in-the-Loop Triggers

Stop and ask a human when you encounter any of these situations:

### 1. No clear unique lookup field

The resource has no single field that uniquely identifies it. Examples:
- `role_user_assignment` — identified by composite `(role_definition, user)`
- `authenticator_map` — no stable unique name field

**Action**: Do not guess. Ask the human: "What field (or combination of fields) uniquely
identifies this resource for idempotency purposes?"

### 2. Write-only or sensitive fields

Fields that the API accepts on write but never returns on read (e.g., `password`,
`client_secret`, API tokens).

**Action**: Mark in the mixin that these are write-only. Never include them in `from_api`.
For idempotency: never compare them (always treat as "no change" unless explicitly provided).

### 3. Nested structures requiring deep comparison

Fields that are dicts or lists where partial updates behave differently from full
replacements.

**Action**: Ask the human: "Does updating this field replace it entirely (PUT semantics)
or merge into it (PATCH semantics)? Are there nested fields the API manages automatically?"

### 4. Multi-step create with ordering constraints

The resource requires calls to multiple endpoints in a specific order, with data from
earlier calls feeding into later ones.

**Action**: Document the dependency graph. Ask the human to verify endpoint paths and
field substitutions before implementing `EndpointOperation` declarations.

### 5. API version ambiguity

The documentation or OpenAPI spec shows different behavior for the same endpoint
depending on subtle version differences.

**Action**: Do not guess about API behavior. Ask the human to provide the authoritative
API documentation or test the behavior against a real instance.

### 6. Existing tests break

If implementing a change causes any existing unit tests, mock scenarios, or integration
tests to fail.

**Action**: Report the failures before attempting any fix. Do not silently change
test assertions to make failing tests pass.

---

## Example Agent Conversations

### Good: Asking before implementing

```
Agent: I'm about to implement the transform mixin for `notification_profile`.
       The module has an `organization` field that accepts a name. I plan to resolve
       this to an integer ID using:
         context.manager.lookup_resource_id('organization', ansible_instance.organization)

       Is this the correct resource type name to pass to lookup_resource_id?
```
### Good: Confirming before mutating tests

```
Agent: My change to the service_node action plugin causes
       test_service_node_idempotency to fail. The test expects `changed: false`
       on the second run but now gets `changed: true`.

       Before I investigate, can you confirm whether the test expectation is
       correct or whether the idempotency logic needs to be fixed?
```

### Bad: Silent test modification

```
# Wrong — never do this
Agent: [silently changes assertion from `not result.changed` to `result.changed`
        to make a failing test pass]
```

### Bad: Inventing API behavior

```
# Wrong — do not guess
Agent: [implements a secondary endpoint with a path /api/gateway/v1/users/{id}/orgs/
        without verifying this endpoint exists in the actual Gateway API]
```

---

## Quality Checklist for Agent-Generated Code

Before presenting code for human review, verify every item:

### Python files
- [ ] `black --check --line-length 160` passes
- [ ] `flake8` passes (no unused imports, no undefined names)
- [ ] `isort --check-only --profile black` passes
- [ ] All class names match the naming convention table
- [ ] All method signatures have type hints
- [ ] `from __future__ import annotations` at top of every file
- [ ] `__metaclass__ = type` in action plugins

### Transform mixin
- [ ] `from_ansible_data` handles all optional fields with `if val is not None`
- [ ] `from_api` populates all readable fields from the API response
- [ ] `get_endpoint_operations` returns entries for `create`, `update`, `delete`, `get`, `list`
- [ ] `get_lookup_field` returns the correct unique identifier field
- [ ] Reference fields use `context.manager.lookup_resource_id()`
- [ ] Write-only fields absent from `from_api`

### Action plugin
- [ ] `MODULE_NAME` matches the module file name exactly
- [ ] All states handled: `present`, `absent`, `exists`
- [ ] `check_mode` respected for all mutating operations
- [ ] `cleanup()` called in `finally` block
- [ ] No HTTP code, no `import requests`

### YAML files
- [ ] Ends with `...`
- [ ] Task `name:` is always first key
- [ ] `failed_when: false` used (not `ignore_errors: true`) for cleanup tasks
- [ ] Cleanup block uses `always:` tag

---

## Which Document to Load for Each Task

| Task | Primary doc | Secondary doc |
|------|------------|--------------|
| Adding a new resource module | [07-adding-resources.md](07-adding-resources.md) | [04-data-model-transformation.md](04-data-model-transformation.md) |
| Understanding the framework | [06-foundation-components.md](06-foundation-components.md) | [03-sdk-architecture.md](03-sdk-architecture.md) |
| Understanding the data flow | [04-data-model-transformation.md](04-data-model-transformation.md) | [06-foundation-components.md](06-foundation-components.md) |
| Adding tests | [08-testing-strategy.md](08-testing-strategy.md) | [07-adding-resources.md](07-adding-resources.md) |
| Fixing an idempotency bug | [05-design-principles.md](05-design-principles.md) | [04-data-model-transformation.md](04-data-model-transformation.md) |
| Modifying connection/manager | [03-sdk-architecture.md](03-sdk-architecture.md) | [06-foundation-components.md](06-foundation-components.md) |
| Debugging CI failures | [08-testing-strategy.md](08-testing-strategy.md) | this document |

---

## Troubleshooting Common Agent Mistakes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: No module named 'ansible_collections'` | Running pytest without proper path setup | Run from collection root with root `conftest.py` active |
| `changed: true` on second run of `state: present` | Idempotency logic compares name vs ID for a ref field | Apply Design Principle 7: resolve name to ID before comparing |
| `AttributeError: 'ManagerRPCClient' has no attribute 'api_version'` | Action plugin directly accessing manager internals | Use `manager.execute()` and `manager.lookup_resource_id()` only |
| `PackageDiscoveryError: Multiple top-level packages` | `pyproject.toml` triggers setuptools in tox linting envs | `tox.ini` has `[testenv] skip_install = true` — do not remove this |
| Molecule `Assert idempotent run did not change` fails | Mock server returns slightly different data on second GET | Check if `from_api` transform returns all fields consistently |
| `validate-modules` errors in DOCUMENTATION | Missing required keys or invalid YAML | Run `ansible-doc -t module ansible.platform.<name>` to validate |
