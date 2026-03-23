# Resource Module Pattern

## What a Resource Module Is

A **resource module** manages the full lifecycle of a configuration entity. It is not a
wrapper around a single API endpoint. It is an abstraction over one logical resource —
a user, an organization, an HTTP port — regardless of how many API calls are required
to create, read, update, or delete that resource.

The key properties of every `ansible.platform` resource module:

1. **Entity-centric**: The module interface mirrors the logical entity, not the API structure.
2. **Idempotent**: Running the same task twice produces `changed: false` on the second run.
3. **State-driven**: The module accepts a `state` parameter that drives what action is taken.
4. **check_mode aware**: `check_mode: true` returns what would change without touching the platform.
5. **Version-transparent**: The same task YAML works across AAP Gateway versions.

## States

Every `ansible.platform` resource module supports a subset of the following states.
The exact set supported by each module is declared in its `DOCUMENTATION` string.

### `state: present`

Ensure the resource exists with the given properties. If the resource does not exist,
create it. If it already exists, check whether the specified properties match the
current state. If they match, return `changed: false`. If they differ, update only
the provided fields and return `changed: true`.

```yaml
- name: Ensure user exists
  ansible.platform.user:
    username: alice
    email: alice@example.com
    state: present
```

**Formal definition**: Let `D` be the desired state (fields specified in the task).
Let `E` be the existing state. If `E` is ∅ (resource does not exist), create resource
with fields `D`. If `E` is not ∅ and `D ⊆ E` (all specified fields match), no-op.
If `D ⊄ E`, patch resource with fields where `D ≠ E`.

### `state: absent`

Ensure the resource does not exist. If it does not exist, return `changed: false`.
If it exists, delete it and return `changed: true`.

```yaml
- name: Remove a stale HTTP port
  ansible.platform.http_port:
    port: 8080
    state: absent
```

**Formal definition**: If `E` is ∅, no-op. If `E` is not ∅, delete resource.

### `state: exists`

Check whether the resource exists. Never creates, updates, or deletes anything.
Returns `exists: true/false` and, when `true`, populates the resource fields in the
return value. Useful for conditional tasks and facts gathering.

```yaml
- name: Check if organization exists
  ansible.platform.organization:
    name: "Red Hat"
    state: exists
  register: org_check

- name: Print result
  debug:
    msg: "org exists: {{ org_check.exists }}"
```

**Formal definition**: Returns `{ exists: E ≠ ∅, ...fields }`. No side effects.

### `state: enforced`

Ensure the resource exists with **exactly** the given properties. Unlike `present`
(which only checks specified fields), `enforced` resets omitted optional fields to
their defaults. This is the compliance enforcement state.

```yaml
- name: Lock down feature flags to only approved values
  ansible.platform.feature_flag:
    name: login_expiry
    enabled: true
    state: enforced
```

**Formal definition**: Let `D` be the full desired state including defaults for all
omitted optional fields. Ensure `E = D`. If `E` is ∅, create. If `E ≠ D`, update to
`D`. If `E = D`, no-op.

### `state: merged` (select modules)

Merge a partial configuration onto an existing resource. Unlike `present`, `merged`
performs a deep merge for list and dict fields rather than a full replacement.
Used by modules whose fields are collections (e.g. authenticator maps, role assignments).

## Entities vs. Endpoints

The core idea: **one module per entity**, not one module per endpoint.

Consider the `user` resource. The Gateway API exposes multiple endpoints for a user:

| Endpoint | HTTP Method | Purpose |
|----------|-------------|---------|
| `/api/gateway/v1/users/` | `POST` | Create user |
| `/api/gateway/v1/users/{id}/` | `PATCH` | Update user |
| `/api/gateway/v1/users/{id}/` | `DELETE` | Delete user |
| `/api/gateway/v1/users/` | `GET` | List users (for find-by-name) |
| `/api/gateway/v1/users/{id}/` | `GET` | Get single user |

Without the resource module pattern, a playbook author would need to:
1. Call the list endpoint to find the user by name.
2. Decide create vs. update based on the result.
3. If creating, call the POST endpoint.
4. If updating, call the PATCH endpoint with only changed fields.

The `ansible.platform.user` module encapsulates all of this:

```yaml
- name: Ensure user alice exists          # one task
  ansible.platform.user:
    username: alice
    email: alice@example.com
    organizations: [engineering, ops]
    state: present
```

Behind the scenes:
1. Find user by `username` — one GET to `/api/gateway/v1/users/?username=alice`.
2. Compare existing state to desired state.
3. If identical → `changed: false`, done.
4. If different → PATCH to `/api/gateway/v1/users/{id}/`.
5. If not found → POST to `/api/gateway/v1/users/`.

The playbook author writes one task. The module handles the rest.

### Multi-Endpoint Entities

Some entities require multiple API endpoints to fully configure. The transform mixin
declares **secondary operations** that run after the primary CRUD operation.

Example: Creating a user and assigning them to organizations:

```
Primary:   POST /api/gateway/v1/users/          → creates the user, returns id
Secondary: POST /api/gateway/v1/users/{id}/organizations/  → assigns org membership
```

The framework's `EndpointOperation` type supports declaring the dependency:

```python
EndpointOperation(
    method='POST',
    path='/api/gateway/v1/users/{id}/organizations/',
    operation_type='secondary',
    depends_on='create',
    order=2,
)
```

Secondary operations run in `order` sequence after the primary operation completes.
Path parameters like `{id}` are substituted from the result of the primary operation.

## The Convergence Contract

Every `ansible.platform` resource module guarantees this contract:

### Before making any change

The module **always** reads the current state of the resource from the Gateway API
before deciding whether to create, update, or delete. This is the "find before mutate"
pattern. It is what makes idempotency possible.

```
Input:  task args (desired state)
Step 1: GET resource (current state)
Step 2: Compare desired vs. current
Step 3: If same → return changed=false
Step 4: If different → execute API call → return changed=true
```

### check_mode

When `check_mode: true` is set on a task, step 4 is skipped. The module returns
what it *would* do, including a `would_change` key in the result, but makes no
API calls. This is guaranteed for all 22 modules.

### Return values

Every module returns a consistent structure:

```yaml
changed: true/false
failed: false
id: <resource integer ID>
<primary_key_field>: <value>          # e.g. username, name, port
<all resource fields>: <values>
_timing:
  rpc_time: <ms>
  manager_processing_time: <ms>
  api_call_time: <ms>
```

When `state: exists`:
```yaml
changed: false
failed: false
exists: true/false
<resource fields if exists>: <values>
```

## Why This Pattern Matters for AAP

### Multi-version AAP deployments

Organizations running AAP 2.4, 2.5, and pre-release 3.x simultaneously need a single
collection that works across all of them. The resource module pattern, combined with
the versioned data model, makes this possible. The playbook author writes:

```yaml
ansible.platform.user:
  username: alice
  state: present
```

The collection detects the Gateway API version, selects the right API model and
transform mixin, and the playbook works unchanged.

### Compliance enforcement

IT security teams often need to enforce that a platform is configured to a known-good
baseline. `state: enforced` on a resource module is their tool:

```yaml
- name: Enforce approved HTTP ports only
  ansible.platform.http_port:
    port: 443
    state: enforced
  loop: "{{ approved_ports }}"
```

This is not possible with endpoint-level modules — the concept of "exactly these
properties, nothing else" requires entity-level awareness.

### Idempotent automation pipelines

Ansible playbooks are often run on a schedule (e.g., every 30 minutes in a GitOps
pipeline). Entity-level idempotency ensures these runs are safe and only produce
changes when configuration drift has occurred.
