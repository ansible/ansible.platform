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
The exact set supported by each module is declared in its `DOCUMENTATION` string and in
`VALID_STATES` on the Ansible model class.

> **See also**: [13-user-module-worked-example.md](13-user-module-worked-example.md)
> for detailed playbook examples and expected output for every state using the `user`
> module as a concrete running example.

### `state: merged`

**"Create or update — add what is missing, update what differs."**

If the resource does not exist, create it. If it already exists, compare only the
fields you specified — if they all match the current state, return `changed: false`.
If any specified field differs, PATCH only those fields and return `changed: true`.
Fields you do **not** specify are left exactly as they are.

```yaml
# First run — user does not exist → POST → changed: true
- name: Create user alice
  ansible.platform.user:
    config:
      - username: "alice"
        email: "alice@example.com"
        first_name: "Alice"
        last_name: "Smith"
        is_superuser: false
    state: merged
    gateway_hostname: "https://gateway.example.com"
    gateway_username: "admin"
    gateway_password: "adminpass"
    gateway_validate_certs: true
  register: result
# result.changed == true
# result.before == []
# result.after  == [{id: 42, username: alice, email: alice@example.com, ...}]
```

```yaml
# Second run — user exists, nothing changed → changed: false
- name: Create user alice (idempotency)
  ansible.platform.user:
    config:
      - username: "alice"
        email: "alice@example.com"
        first_name: "Alice"
        last_name: "Smith"
        is_superuser: false
    state: merged
  register: result
# result.changed == false
# result.before  == result.after  (identical)
```

```yaml
# Update one field — alice exists but email changed → PATCH → changed: true
- name: Update alice's email
  ansible.platform.user:
    config:
      - username: "alice"
        email: "alice-new@example.com"
    state: merged
  register: result
# result.changed == true
# result.before[0].email == "alice@example.com"
# result.after[0].email  == "alice-new@example.com"
```

**Formal definition**: `C' = C ∪ D`
Let `D` be the desired fields, `E` the existing record. If `E = ∅`, create with `D`.
If `E ≠ ∅` and `D ⊆ E` (all specified fields match), no-op. If `D ⊄ E`, PATCH the
fields in `D` that differ.

### `state: deleted`

**"Remove the resource if it exists."**

If the resource does not exist, return `changed: false`. If it exists, delete it and
return `changed: true`. Running deleted twice is always idempotent.

```yaml
# First run — alice exists → DELETE → changed: true
- name: Remove user alice
  ansible.platform.user:
    config:
      - username: "alice"
    state: deleted
  register: result
# result.changed == true
# result.before  == [{id: 42, username: alice, ...}]
# result.after   == []
```

```yaml
# Second run — alice is already gone → changed: false
- name: Remove user alice again (idempotency)
  ansible.platform.user:
    config:
      - username: "alice"
    state: deleted
  register: result
# result.changed == false
# result.before  == []
# result.after   == []
```

**Formal definition**: `C' = C \ D`
For each item in `D`, if a matching resource exists in `C`, delete it.

### `state: gathered`

**"Read current state — no changes."**

Fetches and returns the current state of all matching resources. Never creates,
updates, or deletes anything. Always returns `changed: false`.

```yaml
# Gather all users
- name: Read all users
  ansible.platform.user:
    state: gathered
    gateway_hostname: "https://gateway.example.com"
    gateway_username: "admin"
    gateway_password: "adminpass"
    gateway_validate_certs: true
  register: users
# users.changed  == false
# users.gathered == [{id: 1, username: admin, ...}, {id: 42, username: alice, ...}]

- name: Print all usernames
  ansible.builtin.debug:
    msg: "{{ users.gathered | map(attribute='username') | list }}"
# Output: ["admin", "alice"]
```

```yaml
# Gather a specific user (filter by config)
- name: Check if alice exists
  ansible.platform.user:
    config:
      - username: "alice"
    state: gathered
  register: result
# result.gathered | length > 0  → alice exists
# result.gathered | length == 0 → alice does not exist
```

**Formal definition**: Returns `{ gathered: C }` where `C` is the current state.
No side effects.

### `state: replaced`

**"Replace a resource's full field set."**

Like `merged`, but instead of patching only the fields you specify, `replaced` resets
ALL writable fields — setting unspecified ones to `null`. Use this when you want the
resource to have exactly and only the fields you declare.

```yaml
# alice currently has: first_name=Alice, last_name=Smith, is_superuser=false
- name: Replace alice's record (unspecified fields will be nulled)
  ansible.platform.user:
    config:
      - username: "alice"
        email: "alice-replaced@example.com"
        # first_name, last_name, is_superuser NOT specified
    state: replaced
  register: result
# PATCH body: {email: alice-replaced@example.com,
#              first_name: null, last_name: null, is_superuser: null}
# result.after[0].first_name == null
# result.after[0].last_name  == null
```

**Formal definition**: `C' = (C \ K(D)) ∪ D`
For each item in `D`, find the matching item in `C` by `CANONICAL_KEY`, then replace
it entirely with the desired item (nulling any fields not in `D`).

> **Key difference from `merged`**: `merged` only touches fields you specify.
> `replaced` nulls out everything else.

### `state: overridden`

**"Enforce an exact set — delete anything not in config."**

After `overridden`, the platform's resource set equals exactly `config`. Resources on
the platform that are not in `config` are deleted. Resources in `config` that don't
exist are created. Existing resources that differ are updated.

```yaml
# Current platform state: [admin, alice, charlie]
# After overridden, ONLY alice and bob will exist
- name: Enforce exact user set
  ansible.platform.user:
    config:
      - username: "alice"
        email: "alice@example.com"
      - username: "bob"
        email: "bob@example.com"
    state: overridden
  register: result
# HTTP calls:
#   GET  /api/gateway/v1/users/          ← read current
#   POST /api/gateway/v1/users/          ← create bob
#   DELETE /api/gateway/v1/users/1/      ← delete admin (!)
#   DELETE /api/gateway/v1/users/99/     ← delete charlie
# result.changed == true
```

> **Warning**: `overridden` will delete system users such as `admin` if they are not
> listed in `config`. For user management, prefer `merged` + `deleted`.

**Formal definition**: `C' = D`
Delete all resources in `C` that have no match in `D`. Create all resources in `D`
that have no match in `C`. Update resources that match but differ.

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

Every module returns a consistent structure for write states (`merged`, `deleted`,
`replaced`, `overridden`):

```yaml
changed: true/false
failed: false
before:                   # list of resource dicts BEFORE this run
  - id: 42
    username: "alice"
    email: "alice@example.com"
    first_name: "Alice"
    last_name: "Smith"
    is_superuser: false
    created: "2025-06-01T10:00:00Z"
    modified: "2025-06-01T10:00:00Z"
    # ... all API-returned fields
after:                    # list of resource dicts AFTER this run
  - id: 42
    username: "alice"
    email: "alice-new@example.com"   # ← updated field
    first_name: "Alice"
    last_name: "Smith"
    is_superuser: false
    modified: "2025-06-01T11:30:00Z"
config:                   # alias for 'after' (or 'gathered' for gathered state)
  - id: 42
    username: "alice"
    # ...
```

For `state: gathered`:
```yaml
changed: false
failed: false
gathered:                 # list of resource dicts (current state)
  - id: 1
    username: "admin"
    # ...
  - id: 42
    username: "alice"
    # ...
config:                   # alias for 'gathered'
  - id: 1
    username: "admin"
    # ...
```

**Accessing return values in playbooks:**

```yaml
# Check if a specific user was in the 'after' list
- debug:
    msg: "alice id = {{ (result.after | selectattr('username', 'eq', 'alice') | first).id }}"

# Count how many users exist after the run
- debug:
    msg: "Total users: {{ result.after | length }}"

# Get all usernames from gathered state
- debug:
    msg: "{{ users.gathered | map(attribute='username') | list }}"
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
