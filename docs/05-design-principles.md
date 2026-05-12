# Design Principles

These principles govern every decision in `ansible.platform`. When you are unsure how
to implement something, check whether the options violate any of these rules.

---

## SECTION 1: Principle 1 — No HTTP Code in Action Plugins

**Rule**: Action plugins (`plugins/action/`) must not contain any HTTP calls, session
objects, or network I/O. All network interaction goes through the manager process.

**Why**: Action plugins run inside Ansible worker processes, which are forked from the
controller. HTTP sessions and file descriptors do not survive `os.fork()` reliably.
Putting HTTP code in the manager process (a separate subprocess that is never forked)
completely avoids this class of bugs. File handle leaks, connection pooling issues, and
session state corruption are impossible when HTTP code runs in a single, long-lived process.

**Test**: If you see `import requests` or `session.get()` in an action plugin, it is
wrong. Search the entire `plugins/action/` directory for these patterns. They should not exist.

**Correct pattern**:
```python
# action plugin — correct
result = manager.execute('create', 'user', ansible_data_dict)

# action plugin — wrong
response = requests.post(f"{host}/api/gateway/v1/users/", json=data)
```

---

## SECTION 2: Principle 2 — Stable Ansible Model Interface

**Rule**: `AnsibleFoo` dataclasses in `ansible_models/` must never have fields renamed,
removed, or have their types changed. New optional fields may be added. Nothing removed.

**Why**: Playbooks are long-lived artifacts. A user who writes a playbook today expects
it to work after an AAP upgrade in 18 months. The Ansible model is the stability
contract between the collection and the playbook author. Changing field names would
break every playbook that uses the old name.

**How API changes are absorbed**: When the Gateway API changes field names or structure,
the transform mixin absorbs the difference. The Ansible model stays the same.

```
AnsibleUser.organizations = ["Red Hat"]          ← never changes
    ↓
UserTransformMixin_v1: organizations → organization_ids: [1]   (v1 API)
UserTransformMixin_v2: organizations → orgs: [1]               (v2 API — different field name)
```

**Test**: If you need to rename a field in `AnsibleFoo`, you're approaching it wrong.
Instead, create the new field, deprecate the old one (document as deprecated in DOCUMENTATION),
and support both in the action plugin for two release cycles.

---

## SECTION 3: Principle 3 — Transform Mixin Is the Only Resource-Specific Code

**Rule**: All resource-specific business logic must live in the transform mixin
(`plugins/plugin_utils/api/v<N>/<resource>.py`). Action plugins, the manager, and
the base classes must be resource-agnostic.

**Why**: Centralising resource logic in the mixin makes it easy to find, test, and
replace. It also makes version upgrades mechanical: add `api/v2/<resource>.py`,
implement the new mixin, done. No framework code changes. No conditional branches
scattered across the action plugin.

**What belongs in the mixin**:
- Field name translation (Ansible name → API name)
- Type coercion (name → ID, list → space-separated string)
- Conditional field logic (don't send password on update unless changed)
- Secondary endpoint declarations
- Lookup field definition
- Null-out field logic (`get_fields_to_null_for_update`)

**What does NOT belong in the mixin**:
- HTTP calls (use `context.manager.lookup_resource_id()` for secondary lookups)
- `import requests`
- Ansible module result formatting
- Action plugin logic (state machines, idempotency checks)

**Test**: If the mixin is importing anything other than dataclasses, types, and local models, review it.

---

## SECTION 4: Principle 4 — Registry Auto-Discovery

**Rule**: New API versions are added by creating a new directory `plugins/plugin_utils/api/v<N>/`.
No list of supported versions should ever be hardcoded in the framework.

**Why**: Hardcoded version lists require framework changes for every API update. The
`APIVersionRegistry` scans the filesystem on startup and builds the version index
dynamically. Adding v3 support requires no framework changes—just create the new directory
and implement the mixin.

**Implementation**:
```python
# registry.py — discovers versions by scanning filesystem
for version_dir in Path(api_base_path).iterdir():
    if version_dir.is_dir() and version_dir.name.startswith('v'):
        version_num = version_dir.name[1:]   # 'v1' → '1'
        # Load and register...
```

**Test**: To verify the registry works, add a new `api/v9/` directory with a stub mixin
and confirm the framework loads it without any code changes.

---

## SECTION 5: Principle 5 — Version Fallback, Never Version Failure

**Rule**: If a resource does not have an implementation for the requested API version,
fall back to the closest available version rather than raising an error. Log a warning
for diagnostics.

**Why**: AAP deployments run at different patch levels. A collection update may add
support for v2 of a resource while the customer's AAP is still on v1. The fallback
ensures the collection still works — it just uses the best available implementation.

**Fallback order**:
1. Exact version match (preferred)
2. Closest lower version (backward compatible — safe default)
3. Closest higher version (forward compatible — with a warning)
4. Raise `ValueError` only if no versions exist at all for the resource

**Example**:
```python
# Available: v1 and v3 of a resource
# Requested: v2
# Result: Use v1 (closest lower) with a warning
LOGGER.warning(
    "Resource 'user' has no v2 implementation. "
    "Falling back to v1. Upgrade AAP or this collection to use v2."
)
```

**Test**: Create a resource with `v1` and `v3` implementations only. Request `v2` and verify
fallback to `v1` with warning logged.

---

## SECTION 6: Principle 6 — Find Before Mutate

**Rule**: `state: present`, `state: enforced`, and `state: absent` operations must
always read the current resource state before making any changes.

**Why**: Idempotency. Without reading first, the module cannot determine whether the
desired state already matches the current state. Without this check, every run of
`state: present` would call PATCH even when nothing changed.

**Pattern**:
```python
# Always: find first
find_result = manager.execute('find', 'user', {'username': 'alice'})

if state == 'absent':
    if not find_result:
        return dict(changed=False)    # already absent
    manager.execute('delete', 'user', {'id': find_result['id']})
    return dict(changed=True)

if state == 'present':
    if find_result and fields_match(desired, find_result):
        return dict(changed=False)    # already correct
    if find_result:
        manager.execute('update', 'user', {**desired, 'id': find_result['id']})
    else:
        manager.execute('create', 'user', desired)
    return dict(changed=True)
```

**Test**: Run a module twice with `state: present` and same input. First run should report
`changed: true`. Second run should report `changed: false`.

---

## SECTION 7: Principle 7 — Reference Fields Must Be Compared by ID

**Rule**: When checking idempotency for fields that accept either a name (str) or an ID
(int/str), the comparison must resolve names to IDs before comparing. Never compare
a name string against an ID integer directly.

**Why**: If a resource stores `service_cluster: 42` (ID) and the playbook specifies
`service_cluster: my-cluster` (name), a naive string comparison would always report
`changed: true` even when `my-cluster` resolves to ID 42.

**Pattern**:
```python
if isinstance(desired_cluster, str):
    desired_cluster_id = context.manager.lookup_resource_id(
        'service_cluster', desired_cluster
    )
else:
    desired_cluster_id = int(desired_cluster)

if desired_cluster_id == existing['service_cluster']:
    # no change needed for this field
```

This pattern applies to all `ref_fields` (fields that reference another resource).

**Test**: Create a service_node with a reference to a cluster by name. Update the playbook
to specify the same cluster but use the ID instead of the name. Verify `changed: false`.

---

## SECTION 8: Principle 8 — check_mode Is Non-Negotiable

**Rule**: Every action plugin must respect `self._task.check_mode`. When `True`, no
API mutations (POST, PATCH, DELETE) may be made. The return value must indicate what
would have changed.

**Why**: Operators use `check_mode` to safely preview changes before applying them to
production platforms. A module that ignores `check_mode` is dangerous and violates
Ansible's contract.

**Implementation**:
```python
if self._task.check_mode:
    return dict(
        changed=would_have_changed,
        check_mode=True,
        msg="check_mode: no changes made"
    )
```

The framework's `TransformContext.check_mode` flag is passed to the manager so even
the transform layer is aware of dry-run mode and can avoid side-effect operations.

**Test**: Run a module with `check_mode: true`. Verify no API calls are made. Then run
without check_mode and verify calls are made.

---

## SECTION 9: Principle 9 — Module Stub Pattern

**Rule**: `plugins/modules/<resource>.py` must contain only `DOCUMENTATION` and
`EXAMPLES` strings. No executable code. All logic lives in the corresponding
`plugins/action/<resource>.py`.

**Why**:
1. Ansible's `DOCUMENTATION` parsing and `ansible-doc` introspection require the
   docstring to live in the module file.
2. The actual execution goes through the action plugin, which Ansible invokes
   automatically when a module and action plugin share the same name.
3. Keeping the module stub thin avoids any confusion about where the code path is.

**Module stub template**:
```python
# plugins/modules/foo.py
DOCUMENTATION = r"""
---
module: foo
short_description: Manage foo resources
...
"""

EXAMPLES = r"""
- name: Create a foo
  ansible.platform.foo:
    name: my-foo
    state: present
...
"""
```

**Test**: Run `ansible-doc ansible.platform.foo` and verify DOCUMENTATION is parsed.

---

## SECTION 10: Principle 10 — Naming Conventions

**Rule**: Follow these naming conventions consistently throughout the codebase.

| Item | Convention | Example |
|------|-----------|---------|
| Module name | `snake_case` | `service_cluster` |
| Ansible model class | `Ansible<PascalCase>` | `AnsibleServiceCluster` |
| API model class | `API<PascalCase>_v<N>` | `APIServiceCluster_v1` |
| Transform mixin class | `<PascalCase>TransformMixin_v<N>` | `ServiceClusterTransformMixin_v1` |
| Action plugin class | Always `ActionModule` | `ActionModule` |
| Module file | `<snake_case>.py` | `service_cluster.py` |
| API version directory | `v<integer>` | `v1`, `v2` |
| Molecule scenario | `<snake_case>_mock` | `service_cluster_mock` |
| Integration test target | `<snake_case>s_test` | `service_clusters_test` |

**Why**: Consistent naming allows code generators and AI agents to derive class names
from module names mechanically, without reference lookups.

**Test**: Run a code generator on a new resource and verify it produces files with
the correct names and class names.

---

## SECTION 11: Principle 11 — All Module Options Must Be Discoverable via ansible-doc

**Rule**: Any new option that users can configure (including connection-level options
like `gateway_idle_timeout`) must be declared in `doc_fragments/auth.py` so it appears
in `ansible-doc` output. Options hidden from `ansible-doc` are effectively undiscoverable.

**Why**: Users rely on `ansible-doc ansible.platform.<module>` to discover available
options. If an option is not in DOCUMENTATION, it doesn't exist from the user's perspective.
This applies equally to authentication options, connection timeouts, and module-specific
parameters.

**Implementation**:
```python
# doc_fragments/auth.py
DOCUMENTATION = {
    'options': {
        'gateway_idle_timeout': {
            'description': 'Idle timeout for Gateway connections in seconds.',
            'type': 'int',
            'default': 300,
            'env': [{'name': 'AAP_GATEWAY_TIMEOUT'}],
        },
        'validate_certs': {
            'description': 'Whether to validate TLS certificates.',
            'type': 'bool',
            'default': True,
        },
    }
}
```

Then include this fragment in the module's DOCUMENTATION:

```python
# plugins/modules/foo.py
DOCUMENTATION = r"""
---
module: foo
doc_fragments:
  - ansible.platform.auth
  
options:
  name:
    description: Resource name.
    type: str
    required: true
"""
```

**Test**: Run `ansible-doc ansible.platform.<module>` and verify every documented option appears,
including connection options like `gateway_idle_timeout` and `validate_certs`.

---

## SECTION 12: Principle 12 — Env Var Overrides Must Accept the Same Type as the Config Field

**Rule**: When an environment variable is used to override a configuration value, the
parsing code must accept the same range of values as the config field. Example: if the
config field is `float`, the env var parser must use `int(float(value))` not `int(value)` —
otherwise "2.5" crashes but "2" works, creating inconsistent behavior.

**Why**: Environment variables are always strings. Parsing them requires type conversion.
If the config file accepts a float but the env var parser only accepts integers, users
experience inconsistent behavior depending on how they configure. This violates the
principle of least surprise.

**Example**:
```python
# Config field (from ansible_models/auth.py)
gateway_idle_timeout: Optional[float] = None  # Can be 2.5 or 30

# Environment variable parser (config/env.py)
def parse_gateway_idle_timeout(value: str) -> float:
    # CORRECT: Accept same types as config field (float)
    return float(value)  # "2.5" → 2.5, "30" → 30.0
    
    # WRONG: Only accept integers
    # return int(value)  # "30" → 30, but "2.5" → ValueError
```

**Pattern**: For each configurable field, define a parser that mirrors the field's type:

```python
# If config field is int: use int()
if config_field_type == int:
    return int(env_value)

# If config field is float: use float()
elif config_field_type == float:
    return float(env_value)  # Handles both "2.5" and "30"

# If config field is bool: use bool_parser()
elif config_field_type == bool:
    return bool_parser(env_value)  # Handle "true", "false", "1", "0"

# If config field is str: use str directly
elif config_field_type == str:
    return str(env_value)
```

**Test**: If a config field is `float`, set the env var to "2.5" and verify no crash. Then
test with "30" and "0.5". All should parse successfully. Compare against the config file
behavior: if the config file accepts it, the env var must too.

---

## SECTION 13: Quality Checklist

Before submitting any new platform action plugin, verify:

- [ ] `AnsibleFoo` dataclass exists in `ansible_models/foo.py`
- [ ] `APIFoo_v1` dataclass exists in `api/v1/foo.py`
- [ ] `FooTransformMixin_v1` implements all required protocol methods
- [ ] Action plugin `ActionModule` extends `BaseResourceActionPlugin`
- [ ] Module stub `plugins/modules/foo.py` has only `DOCUMENTATION` and `EXAMPLES`
- [ ] `DOCUMENTATION` option names match `AnsibleFoo` field names exactly
- [ ] **All options appear in `ansible-doc` output** (Principle 11)
- [ ] **Env var parsers accept same types as config fields** (Principle 12)
- [ ] `state: present` is idempotent (second run returns `changed: false`)
- [ ] `state: absent` is idempotent (second run on absent resource is a no-op)
- [ ] `check_mode: true` makes no API calls
- [ ] `ref_fields` compared by ID, not by name string
- [ ] Write-only fields (e.g., `password`) are never returned or compared
- [ ] Conditional fields nulled correctly on state transitions
- [ ] Molecule mock scenario passes idempotency check
- [ ] Integration test target exists in `tests/integration/targets/`
- [ ] `validate-modules` passes (no linting errors in DOCUMENTATION)
- [ ] `flake8` / `black` / `isort` pass

---

## SECTION 14: Human-in-the-Loop Triggers

When adding a new platform action plugin, the following situations require human review and
cannot be automated:

### 1. The API Resource Has No Stable Unique Key

`get_lookup_field()` must return a field that identifies the resource uniquely.
If no such field exists in the API, a composite key strategy must be designed.

**Example:** An API returns events with `timestamp` and `message` but no `id` field.
The human must define how to uniquely identify an event (e.g., `timestamp + message_hash`).

---

### 2. The Create Operation Has Mandatory Secondary Endpoints

Creating an application and immediately setting its allowed scopes requires ordering
two API calls. The dependency and ordering must be explicitly declared in `EndpointOperation`.

**Example:** Create user → set organizations → associate authenticators. Each step
depends on the previous, and the order matters.

---

### 3. The API Returns Data in a Format That Differs From What It Accepts

The API accepts a URI list as space-separated string but returns it as a JSON array.
The forward and reverse transforms must handle both directions.

**Example:** Input is `["https://a.com", "https://b.com"]` → API accepts `"https://a.com https://b.com"` →
API returns `["https://a.com", "https://b.com"]`.

---

### 4. Idempotency Requires Comparing Nested Structures

The `authenticator_map` has fields like `revocation_mappings` that are dicts. Field-by-field
comparison requires knowing which nested fields are meaningful and which are system-managed.

**Example:** Do we compare the full dict, or just certain keys? Are there fields the API
auto-populates that should be ignored in idempotency checks?

---

### 5. A Field Is Write-Only

The API never returns `password`, so the reverse transform must not try to populate it
from the API response. The idempotency logic must never compare password fields
(always considered "no change" unless a new password is explicitly provided).

---

### 6. A Field's Validity Depends on Another Field's Value

When `map_type` changes from SAML to LDAP, certain fields must be explicitly set to null
in the PATCH. The `get_fields_to_null_for_update()` classmethod must be carefully designed
to cover all valid transitions.

---

### 7. The Module Has Conditional Dependencies

`auth_mode: psk` requires `psk` field; `auth_mode: radius` requires `radius_servers`.
These dependency chains need human validation. The agent cannot infer business rules
from the schema alone.

---

### 8. The Resource Lacks a Clear Canonical Key

The resource has no human-meaningful unique identifier. Content-based or positional
matching must be designed. (See: Principle 2 in `04-data-model-transformation.md`.)

---

## Summary Table

| Principle | One-Line Rule | Focus |
|-----------|---------------|-------|
| 1. No HTTP in action plugins | HTTP only in manager process | Architecture |
| 2. Stable Ansible model | Never rename/remove fields | User contract |
| 3. Transform mixin as resource code | All resource logic in mixin | Maintainability |
| 4. Registry auto-discovery | Scan filesystem for versions | Scalability |
| 5. Version fallback | No version failure; always fallback | Robustness |
| 6. Find before mutate | Read state before changing | Idempotency |
| 7. Reference fields by ID | Resolve names to IDs for comparison | Correctness |
| 8. check_mode non-negotiable | Dry-run mode always works | Safety |
| 9. Module stub pattern | DOCUMENTATION in module, logic in action | Clarity |
| 10. Naming conventions | Consistent mechanical derivation | Code generation |
| 11. Discoverable options | All options in ansible-doc | Discoverability |
| 12. Consistent env var types | Env vars accept same types as config | User experience |
| 13. Quality checklist | Verify all items before merge | Consistency |
| 14. Human-in-the-loop | Stop on key/secondary/nested/conditional fields | Safety |

---

