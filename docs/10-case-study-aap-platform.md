# Case Study: AAP Platform Resources

This document provides a concrete map of the 22 modules in `ansible.platform`, their
domain groupings, identity characteristics, complexity level for implementation, and
known AAP API quirks that affect the collection design.

---

## The Platform API Landscape

AAP Gateway exposes a REST API with resources grouped across several functional domains.
The collection models these as 22 Ansible modules, each covering exactly one logical entity.

### Coverage by Domain

| Domain | Modules | Complexity |
|--------|---------|-----------|
| Identity | `user`, `organization`, `team` | Medium (org ref fields, membership secondary endpoints) |
| Authentication | `authenticator`, `authenticator_map`, `authenticator_user` | High (composite keys, map ordering) |
| Access Control | `role_definition`, `role_user_assignment`, `role_team_assignment` | High (composite keys, no simple unique identifier) |
| Services | `service`, `service_cluster`, `service_type`, `service_key`, `service_node` | Medium-High (cluster ref fields, cross-service dependencies) |
| Platform Config | `http_port`, `route`, `ui_plugin_route`, `settings`, `feature_flag` | Low-Medium |
| Security | `ca_certificate`, `token` | Low |
| Applications | `application` | Medium (URI list fields, OAuth2 config) |

---

## Module Map

### Identity Domain

#### `user`
- **Lookup field**: `username`
- **Ref fields**: `organizations` (list of org names → list of org IDs)
- **Write-only field**: `password` (never returned in API response)
- **Secondary endpoint**: `POST /users/{id}/organizations/` (org membership assignment)
- **API version**: v1 and v2 (v2 renames some fields)
- **Idempotency note**: Password is never compared — treat as "no change" unless
  a non-empty password is explicitly provided

#### `organization`
- **Lookup field**: `name`
- **Ref fields**: None
- **Complexity**: Simple 1:1 mapping — the easiest module in the collection
- **API version**: v1 and v2

#### `team`
- **Lookup field**: `name`
- **Ref fields**: `organization` (org name → org ID)
- **Composite key for find**: `(name, organization_id)` — team names are unique within
  an organization but not globally

---

### Authentication Domain

#### `authenticator`
- **Lookup field**: `name`
- **Ref fields**: None
- **Special fields**: `configuration` (a freeform dict whose schema depends on
  `type` — LDAP, SAML, Google OAuth, etc.)
- **Complexity note**: The `configuration` dict structure varies per authenticator type.
  Deep idempotency comparison of `configuration` is intentionally shallow — only
  explicitly provided keys are compared.

#### `authenticator_map`
- **Lookup field**: None (no stable unique name field)
- **Composite key for find**: `(authenticator, map_type, organization)` or similar
- **Idempotency challenge**: The map has ordered entries; position matters
- **Complexity**: High — requires careful ordered-list comparison

#### `authenticator_user`
- **Lookup field**: Composite `(authenticator, username)`
- **Purpose**: Associates a user with an authenticator and maps their external UID
- **Complexity**: Medium

---

### Access Control Domain

#### `role_definition`
- **Lookup field**: `name`
- **Special**: Role definitions are system-defined or custom. System roles cannot be
  deleted. The module must handle `state: absent` gracefully for system roles.
- **API quirk**: Attempting to delete a built-in role returns 403, not 404

#### `role_user_assignment`
- **Lookup field**: None — composite key `(role_definition, user, object_id)`
- **API design**: This resource is an assignment junction table. There is no "update" —
  only create and delete. Idempotency: if the assignment already exists, `changed: false`.
- **Complexity**: High — composite key, no simple find-by-name

#### `role_team_assignment`
- **Lookup field**: None — composite key `(role_definition, team, object_id)`
- **Same pattern as**: `role_user_assignment`

---

### Services Domain

#### `service`
- **Lookup field**: `name`
- **Ref fields**: `service_type` (service type name → ID)
- **API quirk**: Services cannot be renamed. `name` is immutable after creation.

#### `service_cluster`
- **Lookup field**: `name`
- **Ref fields**: `service` (service name → ID)
- **Complexity**: Medium

#### `service_type`
- **Lookup field**: `name`
- **Ref fields**: None
- **Complexity**: Low

#### `service_key`
- **Lookup field**: `name`
- **Ref fields**: `service_cluster` (cluster name → cluster ID)
- **Idempotency challenge**: The ref field comparison must resolve the cluster name
  to an ID before comparing against the existing `service_cluster` (stored as ID).
  See Design Principle 7.

#### `service_node`
- **Lookup field**: `name`
- **Ref fields**: `service_cluster` (cluster name → cluster ID)
- **Same ref field challenge as**: `service_key`

---

### Platform Config Domain

#### `http_port`
- **Lookup field**: `port` (the port number itself is the unique identifier)
- **Ref fields**: None
- **State support**: `present`, `absent`, `exists`

#### `route`
- **Lookup field**: `name`
- **Ref fields**: `service` (service name → ID)
- **Special fields**: `timeout_seconds` (maps to `idle_timeout_seconds` in API)

#### `ui_plugin_route`
- **Lookup field**: `name`
- **Ref fields**: None
- **Special fields**: `idle_timeout_seconds`, `request_timeout_seconds`

#### `settings`
- **Lookup field**: N/A (singleton resource — only one settings object per platform)
- **State support**: `present` only (create = update for singletons)
- **Idempotency**: Compare all explicitly set fields; use `enforced` to reset defaults

#### `feature_flag`
- **Lookup field**: `name`
- **Ref fields**: None
- **Complexity**: Low

---

### Security Domain

#### `ca_certificate`
- **Lookup field**: `name`
- **Special**: Certificate content is a multi-line PEM string. Comparison must handle
  trailing whitespace and line ending normalization.
- **Write concern**: Certificate replacement has security implications — do not
  silently update unless explicitly requested.

#### `token`
- **Lookup field**: `name`
- **Special**: Token values are write-only. The API never returns the token value after
  creation. The collection stores the token in `token_value` on create but never on
  subsequent reads.
- **State support**: `present`, `absent`, `exists`

---

### Applications Domain

#### `application`
- **Lookup field**: Composite `(name, organization)`
- **Ref fields**: `organization` (org name → org ID)
- **Special fields**:
  - `redirect_uris`: Python list → space-separated string in API
  - `post_logout_redirect_uris`: same list→string transformation
  - `client_secret`: write-only (OAuth2 client secret)
- **Complexity**: Medium — URI list conversion, composite key lookup

---

## Identity Categories

Resources fall into three identity categories that affect how the module implements
`get_lookup_field()` and `get_find_list_query_params()`:

### Category A: Single Unique Name

The resource has a globally unique `name` field. Find-by-name returns 0 or 1 results.

| Module | Lookup field |
|--------|-------------|
| `organization` | `name` |
| `team` | `name` (within org — needs org in query) |
| `authenticator` | `name` |
| `role_definition` | `name` |
| `service` | `name` |
| `service_type` | `name` |
| `service_cluster` | `name` |
| `feature_flag` | `name` |
| `route` | `name` |
| `ui_plugin_route` | `name` |
| `ca_certificate` | `name` |
| `token` | `name` |

### Category B: Non-Name Unique Identifier

The resource has no `name` but has another stable unique identifier.

| Module | Lookup field | Notes |
|--------|-------------|-------|
| `user` | `username` | username is unique |
| `http_port` | `port` | port number is unique |

### Category C: Composite Key (No Single Unique Field)

The resource is identified by a combination of fields. `get_find_list_query_params()`
returns multiple query parameters.

| Module | Composite key |
|--------|--------------|
| `authenticator_map` | `authenticator` + `map_type` + ... |
| `role_user_assignment` | `role_definition` + `user` + `object_id` |
| `role_team_assignment` | `role_definition` + `team` + `object_id` |
| `application` | `name` + `organization` |
| `service_key` | `name` + `service_cluster` |
| `service_node` | `name` + `service_cluster` |

---

## Known API Quirks

### Immutable fields after creation

Some fields cannot be changed after the resource is created. The API returns 400 if
you attempt to update them.

| Module | Immutable field |
|--------|----------------|
| `service` | `name` |
| `user` | `username` (in some versions) |
| `authenticator` | `type` |

**Collection behavior**: When `state: present` detects a desired change to an immutable
field, the module should return an error with a clear message. It should never silently
succeed with `changed: false` when the actual state doesn't match.

### Write-only fields

| Module | Write-only field |
|--------|----------------|
| `user` | `password` |
| `token` | `token_value` |
| `application` | `client_secret` |
| `authenticator` | `configuration.password` (LDAP bind password) |

**Collection behavior**: These fields must:
1. Be accepted on input without validation against the current state
2. Never be included in the idempotency comparison
3. Never appear in the `from_api` reverse transform

### System-managed resources

Certain resources are created and managed by AAP itself and should not be deleted
by the collection.

| Module | System-managed instances |
|--------|------------------------|
| `role_definition` | Built-in roles (Platform Administrator, etc.) |
| `authenticator` | `Local Database` authenticator |
| `organization` | `Default` organization |

**Collection behavior**: `state: absent` on a system-managed resource should either
be a no-op with a warning, or fail with a clear error message (not a 403 crash).

---

## Implementation Roadmap

### Phase 1: Core Identity ✅
`organization`, `user`, `team`

### Phase 2: Service Infrastructure ✅
`service_type`, `service_cluster`, `service`, `service_key`, `service_node`

### Phase 3: Platform Configuration ✅
`http_port`, `route`, `ui_plugin_route`, `settings`, `feature_flag`

### Phase 4: Authentication and Access Control ✅
`authenticator`, `authenticator_map`, `authenticator_user`,
`role_definition`, `role_user_assignment`, `role_team_assignment`

### Phase 5: Security and Applications ✅
`ca_certificate`, `token`, `application`

### Phase 6: Planned
- Inventory sources
- Job templates (if Gateway API exposes them)
- Webhook receivers
- Notification profiles (pending API availability)
