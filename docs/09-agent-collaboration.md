# Agent Collaboration Guide — AI Agents Working with Developers on `ansible.platform`

This document guides AI agents working with developers on the **`ansible.platform` collection** for Ansible Automation Platform (AAP) Gateway. It defines personas, workflows, quality gates, and coding standards so agents can collaborate effectively without reinventing patterns or skipping critical steps.

**Audience**: AI agents (LLMs, coding assistants) assisting developers

**Related Documents**:
- [01-overview.md](01-overview.md) — Architecture context
- [06-foundation-components.md](06-foundation-components.md) — Foundation implementation spec
- [07-adding-resources.md](07-adding-resources.md) — Adding platform resources
- [05-design-principles.md](05-design-principles.md) — Design rules and quality gates
- [10-case-study-aap-platform.md](10-case-study-aap-platform.md) — Platform module map and examples

---

## SECTION 1: Purpose and Quick Start

### Purpose

When a developer starts working with an AI agent on the `ansible.platform` collection, the agent must:

1. **Determine their role** using Role Identification (Section 2)
2. **Load appropriate implementation guide(s)** based on that role
3. **Follow the persona-specific walkthrough** (Foundation Builder or Feature Developer)
4. **Apply coding standards consistently** (Section 8)

### Quick Start Flow

```
Developer engages agent
        │
        ▼
Agent asks: "What are you working on?" (Role Identification)
        │
        ├── A) Building core framework → Foundation Builder persona
        ├── B) Adding a new platform action plugin → Feature Developer persona
        └── C) Something else → Clarifying questions
        │
        ▼
Agent checks: Does the foundation exist?
        │
        ├── NO → Foundation Builder needed first
        └── YES → Feature Developer can proceed
        │
        ▼
Agent loads required docs (Section 10)
        │
        ▼
Agent follows persona walkthrough (Section 3 or 4)
        │
        ▼
Agent applies coding standards (Section 8) and quality checklist (Section 9)
```

### Key Principle

**Do not assume.** Always verify the developer's role and foundation state before proceeding. A Feature Developer cannot add resources without the foundation; a Foundation Builder should not be guided through resource-specific steps.

---

## SECTION 2: Role Identification

### Question 1: What Are You Working On?

Ask the developer:

> **What are you working on?**

| Answer | Persona | Next Step |
|-------|----------|-----------|
| **A)** Building the core framework (types.py, base_transform.py, registry.py, loader.py, platform_manager.py, rpc_client.py, base_action.py) | **Foundation Builder** | Proceed to Section 3 |
| **B)** Adding a new platform action plugin (user, service_cluster, route, application, etc.) | **Feature Developer** | Proceed to Section 4 |
| **C)** Something else | — | Ask clarifying questions |

### Clarifying Questions for "Something Else"

- "Are you debugging an existing module?"
- "Are you updating the OpenAPI spec or regenerating models?"
- "Are you writing tests for an existing resource?"
- "Are you working on documentation or CI/CD?"

Tailor guidance based on the answer.

### Question 2: Does the Foundation Exist Yet?

Before proceeding as a Feature Developer, the agent **MUST** check for foundation files. Use the filesystem to verify.

**Check for these files:**

| File | Purpose |
|------|---------|
| `plugins/plugin_utils/platform/types.py` | Shared types (EndpointOperation) |
| `plugins/plugin_utils/platform/base_transform.py` | BaseTransformMixin — universal transformation logic |
| `plugins/plugin_utils/manager/platform_manager.py` | PlatformManager and PlatformService |

**Decision logic:**

- **If NO** (any of these missing): Redirect to **Foundation Builder** persona. The developer must build the foundation first.
- **If YES** (all present): **Feature Developer** can proceed.

### Path Conventions

- Collection root: `ansible_collections/ansible/platform/` or project-equivalent
- Ansible models: `plugins/plugin_utils/ansible_models/`
- API models: `plugins/plugin_utils/api/v1/`, `api/v2/`, etc.
- Docs: `docs/`

---

## SECTION 3: Persona 1 — Foundation Builder

### When to Use

- Building the framework from scratch
- Core components (BaseTransformMixin, Manager, Registry, Loader) do not exist yet
- Setting up code generation tools

### Required Context

**Load these documents:**

1. [01-overview.md](01-overview.md) — Architecture context, vision, component overview
2. [06-foundation-components.md](06-foundation-components.md) — Full implementation specification

### Q&A Walkthrough: Phases 1–4

---

#### Phase 1: Verify Architecture Understanding

**Agent asks:** "Have you reviewed the architecture? Let me summarize the core components and build order..."

**Agent shows:** The 7 main components and recommended build order:

| Order | Component | Purpose |
|-------|-----------|---------|
| 1 | Shared types (`EndpointOperation`) | `plugins/plugin_utils/platform/types.py` — API endpoint configuration |
| 2 | BaseTransformMixin | `plugins/plugin_utils/platform/base_transform.py` — Bidirectional Ansible ↔ API transformation |
| 3 | APIVersionRegistry | `plugins/plugin_utils/platform/registry.py` — Dynamic version/module discovery |
| 4 | DynamicClassLoader | `plugins/plugin_utils/platform/loader.py` — Load version-specific classes at runtime |
| 5 | PlatformManager | `plugins/plugin_utils/manager/platform_manager.py` — PlatformService + multiprocess manager |
| 6 | ManagerRPCClient | `plugins/plugin_utils/manager/rpc_client.py` — Client-side manager communication |
| 7 | Base Action Plugin pattern | `plugins/action/base_action.py` — Manager spawning, validation, common logic |

**Agent explains:** The flow: Playbook task → Action plugin → Manager (or spawn) → Transform (Ansible→API) → HTTP call → Transform (API→Ansible) → Return.

**Agent asks:** "Does this order make sense? Ready to start with shared types?"

---

#### Phase 2: Build Components in Order

For **each** component:

1. **Agent describes** purpose, features, and file location
2. **Agent asks** for confirmation before implementing
3. **Agent implements** from 06-foundation-components.md spec
4. **Agent shows** key parts (signatures, critical logic)
5. **Agent asks:** "Proceed to next component? Add tests? Refine?"

**Example for BaseTransformMixin:**

> "BaseTransformMixin lives in `plugins/plugin_utils/platform/base_transform.py`. It provides:
> - `from_ansible_data(ansible_instance)` — Ansible Model → API Model
> - `from_api(api_response)` — API Model → Ansible Model
> - Field mapping configuration
> - Endpoint operation declarations
> - Reference field (name↔ID) resolution hooks
>
> Subclasses define field mappings and custom transforms. Shall I implement it from the spec?"

**Build order: types.py → base_transform.py → registry.py → loader.py → platform_manager.py → rpc_client.py → base_action.py**

---

#### Phase 3: Set Up Code Generators

**Agent asks:** "Do you want code generators? These are optional but strongly recommended for scaling to all 22 modules."

**Agent can implement:**

1. **Python dataclass generator** — Parses DOCUMENTATION YAML, generates `AnsibleFoo` dataclasses
2. **OpenAPI-to-dataclass tool** — Wraps `datamodel-code-generator` for API models

---

#### Phase 4: Foundation Testing

**Agent creates** a test script that:

1. Instantiates PlatformService
2. Registers with PlatformManager
3. Starts manager
4. Verifies API version detection and registry discovery

**Agent runs** and verifies output shows manager started, API version detected, supported versions listed.

**Agent asks:** "Test passes? Foundation complete? Ready to move to Feature Developer phase?"

---

## SECTION 4: Persona 2 — Feature Developer

### Prerequisites Check

**Before proceeding**, the agent MUST verify foundation files exist (Section 2). If any are missing, redirect to Foundation Builder.

### Required Context

**Load these documents:**

1. [07-adding-resources.md](07-adding-resources.md) — Main step-by-step guide
2. [05-design-principles.md](05-design-principles.md) — Rules, guardrails, quality gates
3. [10-case-study-aap-platform.md](10-case-study-aap-platform.md) — Platform module map, examples, complexity analysis

### Q&A Walkthrough: Phases 1–7

---

#### Phase 1: Check Foundation Exists

**Agent verifies:** Foundation files present, manager running, registry initialized.

**Agent asks:** "Foundation present and working? Ready to add a new platform action plugin?"

If NO, redirect to Foundation Builder.

---

#### Phase 2: Run the Generator

**Agent runs** `generate_resource.py` against the OpenAPI spec to produce all boilerplate in one pass:

```bash
python tools/generate_resource.py \
  --tag users \
  --spec aap-openapi-specs/2.6/gateway.json \
  --dry-run   # preview output without writing files

# When ready:
python tools/generate_resource.py \
  --tag users \
  --spec aap-openapi-specs/2.6/gateway.json
```

**Five files produced:**
1. `plugins/modules/user.py` — DOCUMENTATION stub (module stub, no logic)
2. `plugins/plugin_utils/ansible_models/user.py` — `AnsibleUser` dataclass
3. `plugins/plugin_utils/api/v1/user.py` — `APIUser_v1` dataclass + `UserTransformMixin_v1` skeleton
4. `plugins/action/user.py` — `ActionModule(BaseResourceActionPlugin)` skeleton
5. `tests/integration/test_user.yml` — integration test scaffold

**Agent confirms** the correct `--tag` value from the OpenAPI spec and that the spec path points to the right version.

---

#### Phase 3: Review Generated DOCUMENTATION and AnsibleFoo Dataclass

**Agent reviews** generated output with the developer and verifies:

- **User-friendly names** — snake_case, no vendor camelCase; rename any generated camelCase fields
- **Read-only markers** — `id`, `created`, `modified` present as return-only fields (not in module parameters)
- **Write-only markers** — `password`, `client_secret` marked `no_log: true`, never returned
- **Names over IDs** — `organization: 'Red Hat'` not `organization_id: 1`; reference fields should accept names
- **Required fields** — required vs optional classification matches API semantics
- **`extends_documentation_fragment`** values correct

**Agent iterates** on any fields that need adjustment: "The generator named this `org_id` — should it be `organization` (name-based)? Is `service_cluster` a reference field?"

**Agent does NOT rewrite from scratch** — only corrects what the generator got wrong.

---

#### Phase 4: Complete the Transform Mixin

**Agent opens** the generated `plugins/plugin_utils/api/v1/{resource}.py` and fills in the skeleton.

**What the generator produces (skeleton):**
```python
class UserTransformMixin_v1(BaseTransformMixin):
    _field_mapping = {
        'username': 'username',
        # TODO: review reference fields, rename mappings
    }
    
    def get_endpoint_operations(self):
        return {
            'create': EndpointOperation(method='POST', path='/api/gateway/v1/users/'),
            'update': EndpointOperation(method='PATCH', path='/api/gateway/v1/users/{id}/'),
            'delete': EndpointOperation(method='DELETE', path='/api/gateway/v1/users/{id}/'),
            'get': EndpointOperation(method='GET', path='/api/gateway/v1/users/{id}/'),
            'list': EndpointOperation(method='GET', path='/api/gateway/v1/users/')
        }
    
    def get_lookup_field(self) -> str:
        return 'username'  # TODO: verify correct lookup field
```

**What the developer (or agent) adds:**
- Name→ID resolution for reference fields (`organizations`, `service_cluster`, etc.)
- Field renames where Ansible name differs from API name
- Conditional field logic (e.g., field only sent on create)
- Secondary endpoint declarations (e.g., assign role after create)

**Agent validates assumptions:** "I see the API uses `organizations` list but returns org IDs. I'll add name→ID resolution. Correct?"

---

#### Phase 5: Review Generated ActionModule

**Agent opens** `plugins/action/user.py` and confirms the generated skeleton is correct:

```python
class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = 'user'
```

This is intentionally minimal — `BaseResourceActionPlugin` handles everything else. The agent verifies `MODULE_NAME` matches the module file name and that no extra logic has been added that belongs in the transform mixin instead.

---

#### Phase 6: Write Integration Test

**Agent creates** test playbook in `tests/integration/test_user.yml` following seven phases:
1. Verify setup (connection works)
2. Create resource (`state: present`)
3. Verify creation
4. Update resource
5. Verify update
6. Delete resource (`state: absent`)
7. Verify deletion

**Agent runs** and verifies idempotency: second `state: present` returns `changed: false`.

---

#### Phase 7: Write Molecule Scenario

**Agent creates** mock scenario in `extensions/molecule/{resource}_mock/converge.yml` with the same seven phases.

**Agent runs** `molecule converge` and verifies idempotency against mock server.

---

## SECTION 5: Code Generator Persona

*Optional: If extending or debugging `generate_resource.py`.*

**When to use:** Extending the generator, debugging generation failures, or adding support for new OpenAPI patterns.

**Agent responsibilities:**
- Parse OpenAPI spec (`aap-openapi-specs/<version>/gateway.json`) → all five output files
- Handle edge cases: polymorphic fields, nested objects, `$ref` chains
- Validate generated output against design principles (05-design-principles.md)
- Produce transform mixin skeletons with correct `TODO` markers for human authorship

**Human review required:** Naming choices (Principle 4 from 05-design-principles.md), reference field identification, any business logic in the transform mixin.

---

## SECTION 6: Testing Persona

*Optional: If implementing test infrastructure.*

**When to use:** Writing unit tests, integration tests, Molecule scenarios, mock server responses.

**Agent responsibilities:**
- Generate test playbooks from module spec
- Generate mock server response fixtures
- Write unit test for transform mixin
- Generate coverage reports

**Human review required:** Test assertions, edge cases, idempotency expectations.

---

## SECTION 7: Doc Writer Persona

*Optional: If implementing documentation generation.*

**When to use:** Auto-generating docs from DOCUMENTATION strings, code comments, OpenAPI specs.

**Agent responsibilities:**
- Generate module reference docs
- Generate architecture diagrams
- Generate complexity analysis tables
- Generate coverage matrix

**Human review required:** Content accuracy, completeness, clarity.

---

## SECTION 8: Coding Standards

These standards apply to all agent-generated code. Violations will fail CI.

### Python Standards

**Formatting**: `black` with `line-length = 160`. Run `black --line-length 160 <file>` after every generation.

**Imports**: `isort` with `profile = black`. All imports sorted. Standard library → third-party → local.

**Style**: `flake8` with `max-line-length = 160`. No `E402` in module stubs.

**Docstrings**: Modules must have `DOCUMENTATION` and `EXAMPLES`. Classes and non-trivial methods should have docstrings. Obvious one-liners do not need comments.

**No magic strings**: Version numbers, operation names, and state values must match the exact strings used by the framework:
- Operations: `'create'`, `'update'`, `'delete'`, `'find'`, `'enforced'`
- States: `'present'`, `'absent'`, `'exists'`, `'enforced'`

**Type hints**: All method signatures must have type hints. Return types required.

**Namespace**: Everything in `ansible.platform` namespace. No top-level imports from `requests` in action plugins.

**HTTP in manager**: All HTTP code lives in PlatformService running inside the manager process, NOT in action plugins.

**Snake_case everywhere**: Variable names, function names, field names all snake_case. No camelCase except in API-specific model field names that mirror the Gateway API.

**New module options**: All new options must be registered in `doc_fragments/auth.py` or other appropriate fragment file. Do not hardcode auth/connection options in individual modules.

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

## SECTION 9: Quality Checklist for Agent-Generated Code

Before presenting code for human review, verify every item:

### Python files
- [ ] `black --check --line-length 160` passes
- [ ] `flake8` passes (no unused imports, no undefined names)
- [ ] `isort --check-only --profile black` passes
- [ ] All class names match the naming convention table
- [ ] All method signatures have type hints
- [ ] `from __future__ import annotations` at top of every file
- [ ] `__metaclass__ = type` in action plugins
- [ ] No `import requests` in action plugins
- [ ] All HTTP code in PlatformService (manager process), not action plugins

### Transform mixin
- [ ] `from_ansible_data` handles all optional fields with `if val is not None`
- [ ] `from_api` populates all readable fields from the API response
- [ ] `get_endpoint_operations` returns entries for `create`, `update`, `delete`, `get`, `list`
- [ ] `get_lookup_field` returns the correct unique identifier field
- [ ] Reference fields use `context.manager.lookup_resource_id()` or lookup methods
- [ ] Write-only fields absent from `from_api`
- [ ] API version correctly specified in mixin class name (_v1, _v2, etc.)

### Action plugin
- [ ] `MODULE_NAME` matches the module file name exactly
- [ ] All states handled: `present`, `absent`, `exists`
- [ ] `check_mode` respected for all mutating operations
- [ ] `cleanup()` called in `finally` block
- [ ] No HTTP code, no `import requests`
- [ ] Proper error handling and validation

### YAML files
- [ ] Ends with `...`
- [ ] Task `name:` is always first key
- [ ] `failed_when: false` used (not `ignore_errors: true`) for cleanup tasks
- [ ] Cleanup block uses `always:` tag

---

## SECTION 10: Context Loading Map

Which documents to read for which task:

| Task | Primary doc | Secondary doc |
|------|------------|--------------|
| Adding a new platform action plugin | [07-adding-resources.md](07-adding-resources.md) | [04-data-model-transformation.md](04-data-model-transformation.md) |
| Understanding the framework | [06-foundation-components.md](06-foundation-components.md) | [03-sdk-architecture.md](03-sdk-architecture.md) |
| Understanding the data flow | [04-data-model-transformation.md](04-data-model-transformation.md) | [06-foundation-components.md](06-foundation-components.md) |
| Adding tests | [08-testing-strategy.md](08-testing-strategy.md) | [07-adding-resources.md](07-adding-resources.md) |
| Fixing an idempotency bug | [05-design-principles.md](05-design-principles.md) | [04-data-model-transformation.md](04-data-model-transformation.md) |
| Modifying connection/manager | [03-sdk-architecture.md](03-sdk-architecture.md) | [06-foundation-components.md](06-foundation-components.md) |
| Debugging CI failures | [08-testing-strategy.md](08-testing-strategy.md) | this document |

---

## SECTION 11: Do Not — Anti-Patterns to Avoid

Stop the agent immediately if it attempts any of these:

### 1. Do not add HTTP code to action plugins

**Wrong:**
```python
# plugins/action/user.py
import requests

def run(self):
    response = requests.post('http://...')  # NO!
```

**Right:** All HTTP lives in PlatformService inside the manager process. Action plugins call `manager.execute()` only.

---

### 2. Do not hardcode version lists

**Wrong:**
```python
SUPPORTED_VERSIONS = ['1', '2']
```

**Right:** Use the APIVersionRegistry to auto-discover versions from api/v*/ directories.

---

### 3. Do not skip doc_fragments for new options

**Wrong:**
```python
# plugins/action/user.py adds a new 'connection' option
# ... but doesn't register it in doc_fragments/
```

**Right:** All new module options that are shared (auth, connection, validation) go in `doc_fragments/auth.py` or similar, and `extends_documentation_fragment: ['ansible.platform.auth']` in module DOCUMENTATION.

---

### 4. Do not use `int()` directly on environment variables

**Wrong:**
```python
timeout = int(os.environ.get('IDLE_TIMEOUT'))  # Crashes if unset
```

**Right:**
```python
timeout = int(float(os.environ.get('IDLE_TIMEOUT', '3600')))
```

The float intermediary prevents `int()` from choking on scientific notation or edge cases.

---

### 5. Do not compare names to IDs for reference fields

**Wrong:**
```python
# In transform mixin
if ansible_instance.organization == api_response['organizationId']:  # Name vs ID!
    changed = False
```

**Right:**
```python
# Resolve name to ID first, then compare IDs
org_id = context.manager.lookup_resource_id('organization', ansible_instance.organization)
if org_id == api_response['organizationId']:
    changed = False
```

See Design Principle 7.

---

### 6. Do not forget write-only fields in idempotency

**Wrong:**
```python
# password is compare in _is_idempotent
if ansible_instance.password != api_response.get('password'):
    changed = True
```

**Right:**
```python
# password is write-only — never compare it
# If the user provides a password, always treat as needing update
if ansible_instance.password is not None:
    changed = True
```

---

### 7. Do not use `fields_to_null` without understanding AAP semantics

**Wrong:**
```python
# Setting fields_to_null: ['password'] unconditionally
context.manager.update(..., fields_to_null=['password'])
```

**Right:**
```python
# Only null fields during specific transitions (e.g., map_type change for authenticator_map)
if api_instance.map_type != ansible_instance.map_type:
    context.manager.update(..., fields_to_null=['password'])
```

See case study for `authenticator_map` example.

---

## Troubleshooting Common Agent Mistakes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: No module named 'ansible_collections'` | Running pytest without proper path setup | Run from collection root with root `conftest.py` active |
| `changed: true` on second run of `state: present` | Idempotency logic compares name vs ID for a ref field | Apply Section 11 Anti-Pattern #5: resolve name to ID before comparing |
| `AttributeError: 'ManagerRPCClient' has no attribute 'api_version'` | Action plugin directly accessing manager internals | Use `manager.execute()` and `manager.lookup_resource_id()` only |
| `PackageDiscoveryError: Multiple top-level packages` | `pyproject.toml` triggers setuptools in tox linting envs | `tox.ini` has `[testenv] skip_install = true` — do not remove this |
| Molecule `Assert idempotent run did not change` fails | Mock server returns slightly different data on second GET | Check if `from_api` transform returns all fields consistently |
| `validate-modules` errors in DOCUMENTATION | Missing required keys or invalid YAML | Run `ansible-doc -t module ansible.platform.<name>` to validate |

---

## Example Agent Conversations

### Good: Asking before implementing

```
Agent: I'm about to implement the transform mixin for `role_user_assignment`.
       The module assigns a role to a user. I see the API uses a composite key:
       (role_definition_id, user_id, object_id).
       I plan to implement get_lookup_field() to return this tuple.
       Is this the correct approach for composite keys?
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

### Bad: Adding HTTP to action plugin

```
# Wrong — do not do this
Agent: [adds `import requests` to action plugin and makes direct HTTP call]
```
