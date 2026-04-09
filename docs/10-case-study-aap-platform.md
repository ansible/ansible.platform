# Case Study: AAP Platform Resources

This document provides a concrete map of the 22 modules in `ansible.platform`, their
domain groupings, identity characteristics, complexity level for implementation, and
known AAP API quirks that affect the collection design.

---

## SECTION 1: The Platform API Landscape

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

## SECTION 2: Module Map

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

## SECTION 3: Identity Categories

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

## SECTION 4: Known API Quirks

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

## SECTION 5: Platform-Specific Challenges

### macOS + Python 3.12 SSL Fork-Safety

**Challenge**: Python 3.12 on macOS disallows HTTP/SSL socket reuse across process forks
(multiprocessing safety). A naïve approach where the action plugin and manager process
share an HTTP session causes a crash on the fork.

**Solution**: The collection uses a subprocess-based manager (not threads or forked processes
with shared state). The manager process owns the HTTP session. Action plugins communicate
via Unix domain socket RPC, never touching the socket directly.

**Relevant code**:
- `plugins/plugin_utils/manager/platform_manager.py` — PlatformManager spawns subprocess
- `plugins/plugin_utils/manager/rpc_client.py` — ManagerRPCClient communicates via socket

---

### Manager Idle Timeout (Orphaned Process Prevention)

**Challenge**: The manager process is a long-lived subprocess. If a playbook fails, is
cancelled, or the Ansible worker is killed, the manager subprocess may be orphaned,
consuming memory and sockets indefinitely.

**Solution**: `PlatformManager.idle_timeout` (default 3600s) auto-terminates the manager
if no RPC requests are received for that duration. Set to 0 to disable.

**Configuration**:
```python
manager = PlatformManager(idle_timeout=3600)  # 1 hour
manager = PlatformManager(idle_timeout=0)     # Never auto-terminate (debug only)
```

**Monitoring**: Playbook logs report manager creation and termination timestamps.

---

### 2.x Backward Compatibility via Transform Mixin Versioning

**Challenge**: Future AAP releases (2.7, 2.8, and beyond) may introduce API field
changes or new endpoint paths. The collection must continue working across releases
without requiring users to change their playbooks.

**Solution**: Version-specific transform mixins in `api/v1/`, `api/v2/` directories.
The registry auto-detects the platform API version and routes to the correct mixin.
The Ansible-facing interface (`AnsibleUser`, `AnsibleOrganization`, etc.) never changes.

**Example**:
```
plugins/plugin_utils/api/
  v1/
    user.py  (APIUser_v1, UserTransformMixin_v1 — current, AAP 2.6)
  v2/
    user.py  (APIUser_v2, UserTransformMixin_v2 — added when AAP 2.7 API changes ship)
```

**Fallback logic**: If the registry detects a version with no exact mixin match,
it falls back to the highest available version automatically, with a warning logged.

---

### `fields_to_null` for Composite Field Transitions

**Challenge**: Some fields are conditional on others. For example, in `authenticator_map`,
changing `map_type` should null out related fields that no longer apply.

**Solution**: In the transform mixin's `update()` method, detect the transition and
explicitly null the affected fields:

```python
class AuthenticatorMapTransformMixin_v1(BaseTransformMixin):
    def update(self, context, api_instance, desired_ansible_instance):
        # If map_type is changing, null out fields specific to the old type
        if desired_ansible_instance.map_type != api_instance.map_type:
            return context.manager.update(
                api_url,
                desired_api_instance,
                fields_to_null=['field_a', 'field_b']
            )
        else:
            return context.manager.update(api_url, desired_api_instance)
```

This prevents stale data from the old type leaking into the new type's configuration.

---

## SECTION 6: Version Strategy

### How AAP 2.6, 2.7, and Future 2.x Releases Are Handled

1. **Platform detection**: On first task execution, the action plugin asks the manager to
   detect the AAP Gateway API version.

2. **Version → Mixin routing**: The registry maps API version to the correct mixin:
   - v1 API → `UserTransformMixin_v1` (AAP 2.6, current)
   - v2 API → `UserTransformMixin_v2` (AAP 2.7+, added when API changes ship)
   - Future → new versioned directory, no framework changes needed

3. **Fallback**: If a version is not found, the registry falls back to the highest
   available version with a warning:
   ```
   WARN: API v2 detected but no v2 mixin for 'user'. Using v1 mixin.
   ```

4. **Single playbook works everywhere**: Users write:
   ```yaml
   - name: Ensure user exists
     ansible.platform.user:
       username: alice
       organization: engineering
   ```
   The same playbook works on AAP 2.6, 2.7, and future 2.x releases without modification.

### Adding Support for a New API Version

To support a new AAP release (e.g., 2.7) when its API changes ship:

1. Create `plugins/plugin_utils/api/v2/` directory
2. Copy existing v1 files as a starting point
3. Update dataclasses and field mappings to match the 3.0 API
4. Update mixin class names: `UserTransformMixin_v2` → `UserTransformMixin_v3`
5. The registry auto-discovers the new version on startup
6. No action plugin changes needed

---

## SECTION 7: Implementation Roadmap

### Phase 1: Core Identity ✅
`organization`, `user`, `team` — Idle timeout and integration test coverage complete

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

---

## Complete Module Reference

| # | Module | Domain | Lookup Field | Complexity | Status |
|---|--------|--------|--------------|-----------|--------|
| 1 | `organization` | Identity | `name` | Low | ✅ |
| 2 | `user` | Identity | `username` | Medium | ✅ |
| 3 | `team` | Identity | `name` | Medium | ✅ |
| 4 | `authenticator` | Auth | `name` | Medium | ✅ |
| 5 | `authenticator_map` | Auth | (composite) | High | ✅ |
| 6 | `authenticator_user` | Auth | (composite) | Medium | ✅ |
| 7 | `role_definition` | Access Control | `name` | Medium | ✅ |
| 8 | `role_user_assignment` | Access Control | (composite) | High | ✅ |
| 9 | `role_team_assignment` | Access Control | (composite) | High | ✅ |
| 10 | `service` | Services | `name` | Medium | ✅ |
| 11 | `service_type` | Services | `name` | Low | ✅ |
| 12 | `service_cluster` | Services | `name` | Medium | ✅ |
| 13 | `service_key` | Services | `name` | Medium | ✅ |
| 14 | `service_node` | Services | `name` | Medium | ✅ |
| 15 | `http_port` | Config | `port` | Low | ✅ |
| 16 | `route` | Config | `name` | Low | ✅ |
| 17 | `ui_plugin_route` | Config | `name` | Low | ✅ |
| 18 | `settings` | Config | (singleton) | Low | ✅ |
| 19 | `feature_flag` | Config | `name` | Low | ✅ |
| 20 | `ca_certificate` | Security | `name` | Low | ✅ |
| 21 | `token` | Security | `name` | Low | ✅ |
| 22 | `application` | Applications | (composite) | Medium | ✅ |

**Total: 22 modules across 7 domains.**
