# Per-Module Comparison Index

## Overview

This directory contains detailed before/after comparison documentation for all ansible.platform collection modules. Each module has its own README.md file documenting what changed between stable-2.6 (before ANSTRAT-1640) and stable-2.7 (after ANSTRAT-1640).

**Total modules documented:** 22

---

## Group A: Modules That Existed in 2.6 and Changed in 2.7

These modules have both a "before" (2.6) and "after" (2.7) state. Key breaking change: all result fields are now nested under a module-specific key instead of being at the top level of the result.

| Module | Key Change | Migration Path |
|--------|-----------|-----------------|
| [application](application/README.md) | `result.*` → `result.application.*` | Straightforward field migration |
| [authenticator](authenticator/README.md) | `result.*` → `result.authenticator.*` | Straightforward field migration |
| [authenticator_map](authenticator_map/README.md) | `result.*` → `result.authenticator_map.*` | Straightforward field migration |
| [organization](organization/README.md) | `result.*` → `result.organization.*` | Straightforward field migration |
| [team](team/README.md) | `result.*` → `result.team.*` | Straightforward field migration |
| [role_user_assignment](role_user_assignment/README.md) | `result.*` → `result.role_user_assignment.*` | Compound key resource (no name field) |
| [role_team_assignment](role_team_assignment/README.md) | `result.*` → `result.role_team_assignment.*` | Compound key resource (no name field) |
| [settings](settings/README.md) | `result.*` → `result.settings.*` | Singleton resource (PATCH-only) |
| [token](token/README.md) | `result.*` → `result.token.*` | Special: `ansible_facts.aap_token` preserved |
| [user](user/README.md) | `result.*` → `result.user.*` | Complex: ID-based lookup, special password handling |

### Common Changes Across Group A

For all Group A modules:
- **Result structure:** Every field is now nested under `result.<module_name>`
- **Result key:** All fields nested under `result.<module_name>` (round-trip safe)
- **Execution:** Modules are now doc-only stubs; action plugins handle execution
- **Implementation:** Uses new dataclass model (`Ansible<ModuleName>`) and API transformation layer
- **Integration tests:** All assertions must be updated from flat to nested key access

---

## Group B: Modules That Are NEW in 2.7

These modules did NOT exist in 2.6. They provide new functionality in 2.7. No migration needed—these are entirely new capabilities.

| Module | Purpose | Status |
|--------|---------|--------|
| [authenticator_user](authenticator_user/README.md) | Manage authenticator user assignments and migrations | New in 2.7 |
| [ca_certificate](ca_certificate/README.md) | Manage CA certificates for SSL/TLS verification | New in 2.7 |
| [feature_flag](feature_flag/README.md) | Manage feature flags for platform control | New in 2.7 |
| [http_port](http_port/README.md) | Configure HTTP port settings | New in 2.7 |
| [role_definition](role_definition/README.md) | Define custom roles and their permissions | New in 2.7 |
| [route](route/README.md) | Define HTTP routing rules | New in 2.7 |
| [service](service/README.md) | Define backend services | New in 2.7 |
| [service_cluster](service_cluster/README.md) | Group service nodes into clusters | New in 2.7 |
| [service_key](service_key/README.md) | Manage service authentication keys | New in 2.7 |
| [service_node](service_node/README.md) | Register individual nodes in service clusters | New in 2.7 |
| [service_type](service_type/README.md) | Define service type categories | New in 2.7 |
| [ui_plugin_route](ui_plugin_route/README.md) | Register UI plugin routes | New in 2.7 |

### Common Characteristics of Group B

For all Group B modules:
- **Result structure:** All fields are nested under `result.<module_name>`
- **Result key:** All fields nested under `result.<module_name>` (no migration needed for new modules)
- **No migration needed:** These modules are entirely new; no pre-2.7 code needs updating
- **Consistent patterns:** Follow the same new action plugin architecture as Group A

---

## Migration Strategy

### For Playbooks Using Group A Modules

1. **Identify all usages** of the 10 Group A modules in your playbooks
2. **Update result references** from flat keys to nested keys:
   ```yaml
   # Before (2.6)
   result.id
   result.name

   # After (2.7)
   result.<module>.id
   result.<module>.name
   ```
3. **Update conditionals** that check for field existence:
   ```yaml
   # Before (2.6)
   when: 'id' in result

   # After (2.7)
   when: result.<module> is defined and 'id' in result.<module>
   ```
4. **Test thoroughly** in a non-production environment

### For New Code

- **Use Group B modules** for new features (authenticator_user, CA certificates, routing, services, etc.)
- **Follow the nested result pattern** automatically
- **Leverage new capabilities** that didn't exist in 2.6

---

## Quick Reference: Result Key Naming

The nested key in results follows this pattern:

```
result.<module_name>.*
```

Where `<module_name>` is the singular form of the module name:

| Module | Result Key |
|--------|-----------|
| `application` | `result.application` |
| `authenticator` | `result.authenticator` |
| `authenticator_map` | `result.authenticator_map` |
| `authenticator_user` | `result.authenticator_user` |
| `ca_certificate` | `result.ca_certificate` |
| `feature_flag` | `result.feature_flag` |
| `http_port` | `result.http_port` |
| `organization` | `result.organization` |
| `role_definition` | `result.role_definition` |
| `role_team_assignment` | `result.role_team_assignment` |
| `role_user_assignment` | `result.role_user_assignment` |
| `route` | `result.route` |
| `service` | `result.service` |
| `service_cluster` | `result.service_cluster` |
| `service_key` | `result.service_key` |
| `service_node` | `result.service_node` |
| `service_type` | `result.service_type` |
| `settings` | `result.settings` |
| `team` | `result.team` |
| `token` | `result.token` |
| `ui_plugin_route` | `result.ui_plugin_route` |
| `user` | `result.user` |

---

## Special Cases

### Token Module
- **Special behavior:** `ansible_facts.aap_token` is still set for backward compatibility
- **Result key:** `result.token.*` for all other fields

### Settings Module
- **Singleton resource:** No ID field; PATCH-only updates
- **Dynamic fields:** All setting names accepted dynamically
- **Result key:** `result.settings.*`

### Role Assignment Modules
- **Compound keys:** Identified by (role_definition, object_id, user/team) tuple
- **No name field:** These resources don't have a natural "name" lookup field
- **Result key:** `result.role_user_assignment.*` or `result.role_team_assignment.*`

### User Module
- **ID-based lookup:** Can use numeric username (user.id) for lookups; action plugin handles transparently
- **Password handling:** `update_secrets: false` prevents password re-push on updates
- **Result key:** `result.user.*`

---

## Documentation Structure

Each module comparison includes:

1. **Summary** — Brief overview of what changed
2. **Arguments** — Before/after argument comparison (Group A) or single argument table (Group B)
3. **Result Structure** — Before/after JSON examples (Group A) or after JSON (Group B)
4. **Key Differences** — Table showing specific field mapping changes
5. **Integration Test Changes** — Specific test assertion updates (Group A only)
6. **Internal Implementation** — Technical details about module architecture changes
7. **Migration Checklist** — Step-by-step migration guide (Group A) or first-use checklist (Group B)

---

## Additional Resources

- [Main BREAKING_CHANGES directory](../README.md) — Overview of all breaking changes
- [Application module comparison](application/README.md) — Template for module structure
- Platform API documentation — For complete field specifications

---

## Summary by Numbers

- **Total modules:** 22
- **Group A (changed in 2.7):** 10
- **Group B (new in 2.7):** 12
- **Key change:** Result nesting (all modules)
- **Backward compat:** Flat top-level keys deprecated (removal after 2028-04-01)
- **Module types affected:** All; doc-only + action plugin pattern
