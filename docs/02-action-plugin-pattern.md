# Action Plugin Pattern — Entity-Centric Platform Management

## Table of Contents

1. [What an Action Plugin Is](#section-1-what-an-action-plugin-is)
2. [The Four States](#section-2-the-four-states)
3. [Entities vs. Endpoints](#section-3-entities-vs-endpoints)
4. [Multi-Endpoint Entities](#section-4-multi-endpoint-entities)
5. [The Convergence Contract](#section-5-the-convergence-contract)
6. [Multi-version AAP Deployments](#section-6-multi-version-aap-deployments)
7. [Compliance Enforcement](#section-7-compliance-enforcement)

---

## SECTION 1: What an Action Plugin Is

### Action Plugin with a Module Stub

Each `ansible.platform` entity is implemented as an **action plugin** backed by a thin
module stub:

- `plugins/modules/<resource>.py` — contains only `DOCUMENTATION` and `EXAMPLES` strings.
  No executable code. This is what `ansible-doc` reads and what makes the module visible
  to playbook authors.
- `plugins/action/<resource>.py` — contains all execution logic as an `ActionModule`
  class extending `BaseResourceActionPlugin`. This is what actually runs.

Ansible automatically invokes the action plugin when a module and action plugin share
the same name. From the playbook author's perspective it looks identical to any other
module — they write `ansible.platform.user` and it works. The action plugin / stub
split is an implementation detail they never need to know.

### Manages a Configuration Entity, Not an API Endpoint

An `ansible.platform` action plugin manages the full lifecycle of a configuration
entity — a user, an organization, an HTTP port — regardless of how many API calls are
required to create, read, update, or delete that entity.

The action plugin's job is **convergence**: you declare the desired state of a thing,
and it figures out what operations are needed to make reality match. The user never
thinks about HTTP verbs, endpoint paths, or payload structure. They think about the
entity and the state they want it in.

### Core Properties

Every `ansible.platform` action plugin exhibits these properties:

1. **Entity-centric**: The interface mirrors the logical entity, not the API structure.
2. **Idempotent**: Running the same task twice produces `changed: false` on the second run.
3. **State-driven**: Accepts a `state` parameter that drives what action is taken.
4. **check_mode aware**: `check_mode: true` returns what would change without touching the platform.
5. **Version-transparent**: The same task YAML works across AAP Gateway versions.

### Convergence: Declare Desired State, Action Plugin Makes Reality Match

The defining behavior of every `ansible.platform` action plugin is **convergence**. Given a desired state declaration, it:

1. Reads the current state from the Gateway API
2. Compares it to what the user declared
3. Computes the minimal set of changes needed
4. Applies only those changes (or skips if nothing differs)
5. Reports what changed

The user declares *what* they want. The module handles *how* to get there.

---

## SECTION 2: The Four States

Every `ansible.platform` action plugin supports the following four states.
The exact set supported by each plugin is declared in its module stub `DOCUMENTATION` string.

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
    first_name: Alice
    last_name: Smith
    state: present
```

**Formal definition**: Let `D` be the desired state (fields specified in the task).
Let `E` be the existing state. If `E` is ∅ (resource does not exist), create resource
with fields `D`. If `E` is not ∅ and `D ⊆ E` (all specified fields match), no-op.
If `D ⊄ E`, patch resource with fields where `D ≠ E`.

**Edge cases**:
- Unspecified optional fields are left untouched (not reset to defaults)
- Creation fails if required fields are missing
- Partial updates preserve fields not mentioned in the task
- Idempotent: `changed: false` when fields already match

### `state: absent`

Ensure the resource does not exist. If it does not exist, return `changed: false`.
If it exists, delete it and return `changed: true`.

```yaml
- name: Remove a stale HTTP port configuration
  ansible.platform.http_port:
    port: 8080
    state: absent
```

**Formal definition**: If `E` is ∅, no-op. If `E` is not ∅, delete resource.

**Edge cases**:
- Deletion is always idempotent (running twice returns `changed: false` the second time)
- Cannot delete required system resources (e.g., a built-in organization)
- Module returns `failed: true` if the resource cannot be deleted

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

- name: Do something only if it exists
  debug:
    msg: "Organization details: {{ org_check }}"
  when: org_check.exists
```

**Formal definition**: Returns `{ exists: E ≠ ∅, ...fields }`. No side effects.

**Return structure**:
```yaml
changed: false
failed: false
exists: true/false
id: <integer ID if exists>
<resource fields>: <values>
```

### `state: enforced`

Ensure the resource exists with **exactly** the given properties. Unlike `present`
(which only checks specified fields), `enforced` resets omitted optional fields to
their defaults. This is the compliance enforcement state.

```yaml
- name: Lock down HTTP port configuration
  ansible.platform.http_port:
    port: 443
    enabled: true
    ssl_certificate: "default"
    state: enforced

- name: Enforce feature flags to approved values
  ansible.platform.feature_flag:
    name: login_expiry
    enabled: true
    expiry_days: 30
    state: enforced
  loop: "{{ approved_flags }}"
```

**Formal definition**: Let `D` be the full desired state including defaults for all
omitted optional fields. Ensure `E = D`. If `E` is ∅, create. If `E ≠ D`, update to `D`.
If `E = D`, no-op.

**Key differences from `present`**:
- Omitted fields are set to defaults (not left untouched)
- Compliance enforcement: guarantees exact match, not partial match
- Use when you need to reset a resource to a known-good baseline
- Useful for security baselines and configuration hardening

**Edge cases**:
- Read-only fields are never reset (system-managed fields like `created_at`)
- Defaults are version-specific (defined by the AAP Gateway version)
- More restrictive than `present` — use it when you need exact configuration

---

## SECTION 3: Entities vs. Endpoints

The fundamental design distinction that separates a resource module from an API wrapper.

### The Endpoint-Centric Model (Anti-Pattern)

Map every API endpoint to a module. This is what automated code generators produce when
pointed at an OpenAPI spec with no architectural guidance.

**Characteristics:**

- **One module per HTTP endpoint path** — each API route becomes its own module
- **Parameters mirror the API payload verbatim** — API-internal field names
- **No state management** — `present`/`absent` at best
- **Configuring a logical entity requires chaining multiple modules** — a user's role assignments span 3 endpoints, so 3 modules, 3 tasks
- **No convergence** — the module calls the endpoint whether or not anything needs to change
- **Idempotency is the caller's problem** — the user must add `when` conditions

**Result**: ~200 modules for ~20 logical entities. The user is doing the API's job.

### The Entity-Centric Model (Resource Module)

Map every **configurable entity** to a module. The module owns the entity's full lifecycle.

**Characteristics:**

- **One module per logical thing** — user, organization, service_cluster, HTTP port
- **Parameters use human-readable, Ansible-idiomatic names** — snake_case, normalized terminology
- **Full state semantics** — `present`, `absent`, `exists`, `enforced`
- **Module aggregates whatever API calls are needed internally** — one task, many endpoints
- **Convergence built in** — compare desired vs actual, only act on differences
- **Idempotency is the module's responsibility** — `changed: true` only when something actually changed

**Result**: ~20 modules for ~20 entities = **1 module per entity**. The user declares what they want. The module does the rest.

### Complexity Distribution (Comparison Table)

| Concern | Endpoint Model | Resource Model |
|---------|----------------|----------------|
| **API path knowledge** | User (playbook) — must know which modules map to which paths | Module internals — user never sees paths |
| **Call ordering** | User (playbook) — must sequence tasks correctly | Module internals — transform mixin enforces order |
| **Payload construction** | User (task params) — must match API structure exactly | Transform mixin — user provides flat, normalized config |
| **Idempotency** | User (when/changed_when) — caller's responsibility | Module — diff desired vs actual, skip if no diff |
| **Rate limiting** | User (throttle/retries) — high risk with many tasks | Module — fewer calls, only when changes needed |
| **Field naming** | API's internal names | Ansible-normalized terms (snake_case) |
| **State comparison** | Not available — no gathered state | Built-in — gathered vs desired diff |

In the endpoint model, complexity is pushed to the playbook author. In the resource model, it is absorbed by the module.

### AAP Platform Examples

**User resource:** One entity, multiple endpoints

| Endpoint | HTTP Method | Purpose |
|----------|-------------|---------|
| `/api/gateway/v1/users/` | `POST` | Create user |
| `/api/gateway/v1/users/{id}/` | `PATCH` | Update user |
| `/api/gateway/v1/users/{id}/` | `DELETE` | Delete user |
| `/api/gateway/v1/users/` | `GET` | List users (for find-by-name) |
| `/api/gateway/v1/users/{id}/` | `GET` | Get single user |

Without the resource module pattern, a playbook author would need to:
1. Call the list endpoint to find the user by username.
2. Decide create vs. update based on the result.
3. If creating, call the POST endpoint.
4. If updating, call the PATCH endpoint with only changed fields.

The `ansible.platform.user` module encapsulates all of this:

```yaml
- name: Ensure user alice exists
  ansible.platform.user:
    username: alice
    email: alice@example.com
    organizations: [engineering, ops]
    state: present
```

Behind the scenes:
1. Find user by `username` — GET to `/api/gateway/v1/users/?username=alice`
2. Compare existing state to desired state.
3. If identical → `changed: false`, done.
4. If different → PATCH to `/api/gateway/v1/users/{id}/`
5. If not found → POST to `/api/gateway/v1/users/`

The playbook author writes one task. The module handles the rest.

**Organization resource:** Scoped entity

```yaml
- name: Ensure organization exists
  ansible.platform.organization:
    name: "Engineering"
    max_hosts: 500
    state: present
```

Behind the scenes, the module:
1. Finds organization by name (or creates if missing)
2. Updates fields as needed
3. Handles version-specific API differences

**Service cluster resource:** Multi-level aggregation

```yaml
- name: Configure service cluster
  ansible.platform.service_cluster:
    name: "us-west"
    organization: "Engineering"
    capacity: 1000
    state: present
```

The module aggregates multiple API calls to configure the cluster, its organization membership, and capacity settings — all transparently.

---

## SECTION 4: Multi-Endpoint Entities

Some entities require multiple API endpoints to fully configure. The transform mixin
declares **secondary operations** that run after the primary CRUD operation.

### User with Organization Assignment

Creating a user and assigning them to organizations:

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

### Organization with Feature Flags

Some operations span multiple resources. The module hides this complexity:

```yaml
- name: Create organization with baseline features
  ansible.platform.organization:
    name: "Engineering"
    enable_feature_x: true
    enable_feature_y: false
    state: present
```

Behind the scenes:
1. POST to create the organization → returns org `id`
2. PATCH feature flags using the returned `id`

The user provides one task. The module handles all the orchestration.

---

## SECTION 5: The Convergence Contract

Every `ansible.platform` resource module guarantees this contract:

### The Convergence Loop

```
1. GATHER:  Read current config from Gateway (same schema as user input)
2. COMPARE: Diff desired config against current config
3. PLAN:    Compute operations needed (create, update, delete)
4. EXECUTE: Apply operations via API (or skip if no diff)
5. REPORT:  Return changed=true/false, before/after state
```

### Before Making Any Change

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

When `check_mode: true` is set on a task, step 4 is skipped. The action plugin returns
what it *would* do, including a `would_change` key in the result, but makes no
API calls. This is guaranteed for all 22 action plugins.

```yaml
- name: Preview changes without applying them
  ansible.platform.user:
    username: alice
    email: alice@example.com
    state: present
  check_mode: true
  register: preview

- name: Show what would change
  debug:
    msg: "Would change: {{ preview.changed }}"
```

### Return Values

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

### The Contract

An action plugin that cannot do this loop is just an API client with YAML syntax.
The convergence contract is what separates infrastructure automation from imperative
scripting.

### Check Mode: Convergence Without Side Effects

Ansible's `--check` flag asks modules to predict what *would* change without actually
changing anything. Because resource modules are built on deterministic comparison,
check mode is not a simulation — it is a **computation**.

The convergence loop becomes:

```
1. GATHER:  Read current config from Gateway → before
2. PREDICT: Compute after from set theory (no API calls)
3. REPORT:  Return changed=(before != after), before/after state
```

Step 2 does not contact the API (after the initial read). The comparison is deterministic.

---

## SECTION 6: Multi-version AAP Deployments

Organizations running AAP 2.6 today need the same playbooks to keep working as they
upgrade to 2.7, 2.8, and future 2.x releases. The versioned data model makes this
possible without any changes to playbooks.

### The Problem: Version Divergence

Each Gateway API release can introduce field changes, endpoint changes, and behaviour
changes. A naive collection locked to a single API version breaks on upgrade:

- AAP 2.6: Current release — `api/v1/` transform mixins
- AAP 2.7: Upcoming release — may introduce API field changes or new endpoints
- AAP 2.x: Future releases — handled by adding new versioned mixin directories

A naive collection (one module per version) requires duplicating all modules for every
release.

### The Solution: Version-Transparent API Model

The playbook author writes version-agnostic YAML:

```yaml
- name: Ensure user alice exists
  ansible.platform.user:
    username: alice
    email: alice@example.com
    organizations: [engineering]
    state: present
```

This identical task works on AAP 2.6, 2.7, and future 2.x releases because:

1. **Version detection** happens at task runtime:
   - Manager process calls `/api/gateway/v1/ping` → detects version
   - Result is cached for the duration of the play

2. **Version-specific mixins** are loaded dynamically:
   - AAP 2.6 → `UserTransformMixin_v1` (current API)
   - AAP 2.7 → `UserTransformMixin_v2` (if API changes ship in 2.7)
   - Future releases → new versioned mixin, no framework changes

3. **Field mapping** is version-aware per mixin:
   - v1: current field names and endpoint paths
   - v2+: updated field names if the Gateway API changes them

### Practical Example: Multi-Version Playbook

```yaml
---
- name: Ensure users exist — works on AAP 2.6, 2.7, and future releases
  hosts: aap_gateways
  tasks:
    # This task runs identically on all three versions
    - name: Create user alice
      ansible.platform.user:
        username: alice
        email: alice@example.com
        organizations: [engineering, ops]
        state: present
      register: alice_result

    # Another example: organization creation
    - name: Create engineering organization
      ansible.platform.organization:
        name: "Engineering"
        max_hosts: 500
        state: present

    # Another example: HTTP port (version-independent)
    - name: Configure HTTP port
      ansible.platform.http_port:
        port: 8080
        enabled: true
        state: present
```

No conditional logic. No version checks. The collection detects the version,
selects the right API model and transform mixin, and the playbook works unchanged.

### How It Works Internally

The manager process detects versions at startup and caches them:

```python
# In PlatformService (manager subprocess)
def __init__(self, ...):
    self.http_session = requests.Session()
    self.api_version = None  # Lazy-loaded
    self.version_cache = {}  # Cached mixin classes

def get_api_version(self):
    if self.api_version is None:
        response = self.http_session.get("https://<host>/api/gateway/v1/ping")
        self.api_version = response.json()["version"]
    return self.api_version

def execute(self, operation, module_name, ansible_data):
    version = self.get_api_version()
    
    # Load the version-specific mixin
    mixin_class = self.version_cache.get((version, module_name))
    if mixin_class is None:
        mixin_class = registry.find_best_version(version, module_name)
        self.version_cache[(version, module_name)] = mixin_class
    
    # Execute with the right mixin
    return mixin_class.execute(operation, ansible_data)
```

This is why a single playbook works across all versions: the version detection
and mixin selection are transparent to the action plugin.

---

## SECTION 7: Compliance Enforcement

IT security teams often need to enforce that a platform is configured to a known-good
baseline. `state: enforced` on a resource module is their tool.

### Compliance Baseline as Code

Define the desired state once, audit and enforce it everywhere:

```yaml
---
- name: Enforce HTTP port baseline
  hosts: aap_gateways
  tasks:
    - name: Only approved HTTP ports should exist
      ansible.platform.http_port:
        port: 443
        enabled: true
        ssl_certificate: "default"
        state: enforced
      loop: "{{ approved_ports }}"
```

This ensures that:
- Only the listed ports exist and are enabled
- Each port has exactly the specified configuration
- Any unauthorized ports are removed
- Any configuration drift is corrected

### Compliance Audit (read-only)

Use `check_mode` with `state: enforced` to audit without changing anything:

```yaml
- name: Audit HTTP port compliance
  ansible.platform.http_port:
    port: "{{ item }}"
    enabled: true
    ssl_certificate: "default"
    state: enforced
  loop: "{{ approved_ports }}"
  check_mode: true
  register: audit_result

- name: Report compliance status
  debug:
    msg: |
      Compliance drift detected:
      {% if audit_result.changed %}
      FAILED - Configuration does not match baseline
      Changes needed: {{ audit_result | to_nice_json }}
      {% else %}
      PASSED - Configuration matches baseline
      {% endif %}
```

### Security Hardening Example

```yaml
---
- name: Harden platform security baseline
  hosts: aap_gateways
  tasks:
    - name: Enforce feature flag configuration
      ansible.platform.feature_flag:
        name: "{{ item.name }}"
        enabled: "{{ item.enabled }}"
        value: "{{ item.value }}"
        state: enforced
      loop:
        - {name: "login_expiry", enabled: true, value: "30"}
        - {name: "mfa_required", enabled: true, value: "true"}
        - {name: "debug_mode", enabled: false, value: "false"}

    - name: Enforce password policy
      ansible.platform.password_policy:
        min_length: 12
        require_uppercase: true
        require_numbers: true
        require_special_chars: true
        state: enforced
```

### Scheduled Compliance Enforcement

Run compliance enforcement on a schedule to detect and fix drift:

```yaml
---
- name: Scheduled compliance enforcement
  hosts: aap_gateways
  tasks:
    - name: Enforce all baselines
      include_tasks: compliance_baseline.yml

    - name: Report results
      mail:
        host: "{{ mail_host }}"
        subject: "AAP Compliance Report"
        body: |
          Compliance enforcement completed.
          Changed: {{ compliance_result.changed }}
          Details: {{ compliance_result.diff }}
```

This is the defining use case for `state: enforced` — automatic detection and correction
of security configuration drift.

---

## Summary: Endpoint Wrapper vs. Action Plugin

| Aspect | Endpoint Wrapper | `ansible.platform` Action Plugin |
|--------|-----------------|----------------------------------|
| **Module count** | ~200 (1 per endpoint) | 22 (1 per entity) |
| **Tasks to configure user with orgs** | 2–3 | 1 |
| **Compliance enforcement** | Not possible | Built-in (`state: enforced`) |
| **Compliance audits** | Manual scripting | Native (check_mode + enforced) |
| **API rate limit risk** | High | Low (only calls API when diff detected) |
| **User must know API structure** | Yes | No |
| **Playbook readability** | Low | High |
| **Multi-version support** | Multiple playbooks required | Single playbook works everywhere |
| **Implementation** | Standalone module | Action plugin + module stub |

The `ansible.platform` action plugin pattern turns Ansible playbooks from **imperative
API scripts** into **declarative platform definitions**. Instead of "call this endpoint,
then that one, then check the result," the user writes "this user should exist in these
organizations, this port should be configured this way, only these feature flags should
be enabled." The action plugin handles the rest.
