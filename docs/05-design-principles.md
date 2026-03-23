# Design Principles

These principles govern every decision in `ansible.platform`. When you are unsure how
to implement something, check whether the options violate any of these rules.

---

## 1. No HTTP Code in Action Plugins

**Rule**: Action plugins (`plugins/action/`) must not contain any HTTP calls, session
objects, or network I/O. All network interaction goes through the manager process.

**Why**: Action plugins run inside Ansible worker processes, which are forked from the
controller. HTTP sessions and file descriptors do not survive `os.fork()` reliably.
Putting HTTP code in the manager process (a separate subprocess that is never forked)
completely avoids this class of bugs.

**Test**: If you see `import requests` or `session.get()` in an action plugin, it is
wrong.

**Correct pattern**:
```python
# action plugin — correct
result = manager.execute('create', 'user', ansible_data_dict)

# action plugin — wrong
response = requests.post(f"{host}/api/gateway/v1/users/", json=data)
```

---

## 2. Stable Ansible Model Interface

**Rule**: `AnsibleFoo` dataclasses in `ansible_models/` must never have fields renamed,
removed, or have their types changed. New optional fields may be added. Nothing removed.

**Why**: Playbooks are long-lived artifacts. A user who writes a playbook today expects
it to work after an AAP upgrade in 18 months. The Ansible model is the stability
contract between the collection and the playbook author.

**How API changes are absorbed**: When the Gateway API changes field names or structure,
the transform mixin absorbs the difference. The Ansible model stays the same.

```
AnsibleUser.organizations = ["Red Hat"]          ← never changes
    ↓
UserTransformMixin_v1: organizations → organization_ids: [1]   (v1 API)
UserTransformMixin_v2: organizations → orgs: [1]               (v2 API — different field name)
```

---

## 3. Transform Mixin Is the Only Resource-Specific Code

**Rule**: All resource-specific business logic must live in the transform mixin
(`plugins/plugin_utils/api/v<N>/<resource>.py`). Action plugins, the manager, and
the base classes must be resource-agnostic.

**Why**: Centralising resource logic in the mixin makes it easy to find, test, and
replace. It also makes version upgrades mechanical: add `api/v2/<resource>.py`,
implement the new mixin, done.

**What belongs in the mixin**:
- Field name translation (Ansible name → API name)
- Type coercion (name → ID, list → space-separated string)
- Conditional field logic (don't send password on update unless changed)
- Secondary endpoint declarations
- Lookup field definition

**What does NOT belong in the mixin**:
- HTTP calls (use `context.manager.lookup_resource_id()` for secondary lookups)
- `import requests`
- Ansible module result formatting

---

## 4. Registry Auto-Discovery

**Rule**: New API versions are added by creating a new directory `plugins/plugin_utils/api/v<N>/`.
No list of supported versions should ever be hardcoded in the framework.

**Why**: Hardcoded version lists require framework changes for every API update. The
`APIVersionRegistry` scans the filesystem on startup and builds the version index
dynamically. Adding v3 support requires no framework changes.

**Implementation**:
```python
# registry.py — discovers versions by scanning filesystem
for version_dir in Path(api_base_path).iterdir():
    if version_dir.is_dir() and version_dir.name.startswith('v'):
        version_num = version_dir.name[1:]   # 'v1' → '1'
        ...
```

---

## 5. Version Fallback, Never Version Failure

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
4. Raise `ValueError` only if no versions exist at all for the module

---

## 6. Find Before Mutate

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

---

## 7. Reference Fields Must Be Compared by ID

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

---

## 8. check_mode Is Non-Negotiable

**Rule**: Every action plugin must respect `self._task.check_mode`. When `True`, no
API mutations (POST, PATCH, DELETE) may be made. The return value must indicate what
would have changed.

**Why**: Operators use `check_mode` to safely preview changes before applying them to
production platforms. A module that ignores `check_mode` is dangerous.

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
the transform layer is aware of dry-run mode.

---

## 9. Module Stub Pattern

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

---

## 10. Naming Conventions

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

---

## Quality Checklist

Before submitting any new resource module, verify:

- [ ] `AnsibleFoo` dataclass exists in `ansible_models/foo.py`
- [ ] `APIFoo_v1` dataclass exists in `api/v1/foo.py`
- [ ] `FooTransformMixin_v1` implements all required protocol methods
- [ ] Action plugin `ActionModule` extends `BaseResourceActionPlugin`
- [ ] Module stub `plugins/modules/foo.py` has only `DOCUMENTATION` and `EXAMPLES`
- [ ] `DOCUMENTATION` option names match `AnsibleFoo` field names exactly
- [ ] `state: present` is idempotent (second run returns `changed: false`)
- [ ] `state: absent` is idempotent (second run on absent resource is a no-op)
- [ ] `check_mode: true` makes no API calls
- [ ] `ref_fields` compared by ID, not by name string
- [ ] Molecule mock scenario passes idempotency check
- [ ] Integration test target exists in `tests/integration/targets/`
- [ ] `validate-modules` passes (no linting errors in DOCUMENTATION)
- [ ] `flake8` / `black` / `isort` pass

---

## Human-in-the-Loop Triggers

When adding a new resource module, the following situations require human review and
cannot be automated:

1. **The API resource has no stable unique key** — `get_lookup_field()` must return
   a field that identifies the resource uniquely. If no such field exists in the API,
   a composite key strategy must be designed.

2. **The create operation has mandatory secondary endpoints** — e.g., creating an
   application and immediately setting its allowed scopes requires ordering two API calls.
   The dependency and ordering must be explicitly declared in `EndpointOperation`.

3. **The API returns data in a format that differs from what it accepts** — e.g., the
   API accepts a URI list as space-separated string but returns it as a JSON array.
   The forward and reverse transforms must handle both directions.

4. **Idempotency requires comparing nested structures** — e.g., `authenticator_map`
   has fields like `revocation_mappings` that are dicts. Field-by-field comparison
   requires knowing which nested fields are meaningful and which are system-managed.

5. **A field is write-only** — e.g., `password`. The API never returns it, so the
   reverse transform must not try to populate it from the API response. The idempotency
   logic must never compare password fields (always considered "no change" unless a new
   password is explicitly provided).
