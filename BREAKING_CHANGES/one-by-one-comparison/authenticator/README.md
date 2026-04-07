# Module Comparison: ansible.platform.authenticator

**Before:** `stable-2.6` (`platform_main_before_1640`)
**After:** `stable-2.7` / ANSTRAT-1640 branch
**Module:** `ansible.platform.authenticator`

---

## Summary

The `authenticator` module **arguments are unchanged**. What changed:

1. **Result structure** — all fields now nested under `result.authenticator` instead of flat
2. **Execution path** — module is now doc-only; action plugin handles logic
3. **Internal implementation** — uses `AnsibleAuthenticator` dataclass instead of `AAPAuthenticator`
4. **Integration tests** — assertions changed from `result.id` → `result.authenticator.id`
6. **Configuration field** — still accepts dict but API behavior unchanged

---

## 1. Arguments — UNCHANGED

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `name` | str | **yes** | — | Authenticator name (unique) |
| `new_name` | str | no | — | Rename to new name |
| `slug` | str | no | — | Unique slug identifier |
| `type` | str | **yes** | — | Authenticator type (e.g., `ansible_base.authentication.authenticator_plugins.local`) |
| `configuration` | dict | **yes** | — | Type-specific configuration |
| `state` | str | no | `present` (default), `absent`, `exists`, `enforced` | Desired state |

**No changes to arguments.**

---

## 2. Result Structure

### Before (2.6.x) — flat top-level keys

```json
{
    "changed": true,
    "id": 1,
    "name": "Local Authenticator",
    "slug": "local-auth",
    "type": "ansible_base.authentication.authenticator_plugins.local",
    "configuration": {},
    "enabled": true
}
```

### After (2.7.x) — nested under `authenticator` key

```json
{
    "changed": true,
    "authenticator": {
        "id": 1,
        "name": "Local Authenticator",
        "slug": "local-auth",
        "type": "ansible_base.authentication.authenticator_plugins.local",
        "configuration": {},
        "enabled": true
    },
}
```
> **Backward Compatibility (2.7.x):** Flat top-level keys (`result.id`, `result.username`, etc.)
> are kept alongside the nested key for backward compatibility with ≤2.6 playbooks.
> They are silently deprecated and scheduled for removal after 2028-04-01.
> Prefer `result.<module>.<field>` in new code.



### Key differences

| Field | Before | After |
|-------|--------|-------|
| `id` | `result.id` | `result.authenticator.id` |
| `name` | `result.name` | `result.authenticator.name` |
| `slug` | `result.slug` | `result.authenticator.slug` |
| `type` | `result.type` | `result.authenticator.type` |
| `configuration` | `result.configuration` | `result.authenticator.configuration` |

---

## 3. Documentation

2.7 DOCUMENTATION is enhanced with clearer examples and RETURN section.

---

## 4. Examples — IMPROVED

### Before (2.6.x)

```yaml
- name: Create local authenticator
  ansible.platform.authenticator:
    name: "Local Authenticator"
    slug: "local-auth"
    type: "ansible_base.authentication.authenticator_plugins.local"
    configuration: {}
    state: present
```

### After (2.7.x)

```yaml
- name: Create local authenticator
  ansible.platform.authenticator:
    name: "Local Authenticator"
    slug: "local-auth"
    type: "ansible_base.authentication.authenticator_plugins.local"
    configuration: {}
    state: present
  register: created_auth

- name: Round-trip update using registered result
  ansible.platform.authenticator: "{{ created_auth.authenticator | combine({'configuration': {'updated': true}}) }}"

- name: Check whether authenticator exists
  ansible.platform.authenticator:
    name: "Local Authenticator"
    state: exists
  register: auth_check
```

---

## 5. Integration Test Changes

All result references changed to nested form. Pay special attention to cross-module usage where authenticator IDs are passed to other modules:

```yaml
# BEFORE (2.6)
- create_auth.id

# AFTER (2.7)
- create_auth.authenticator.id
```

---

## 6. Internal Implementation

| Aspect | Before (2.6) | After (2.7) |
|--------|---------|---------|
| Execution | `AAPAuthenticator(module).manage()` runs inline | Action plugin executes via manager |
| Module type | Functional | Doc-only stub |
| Dataclass | `AAPAuthenticator` | `AnsibleAuthenticator` |

---

## 7. Migration Checklist

- [ ] Replace `result.id` → `result.authenticator.id`
- [ ] Replace `result.name` → `result.authenticator.name`
- [ ] Replace `result.slug` → `result.authenticator.slug`
- [ ] Replace `result.configuration` → `result.authenticator.configuration`
- [ ] Update all cross-module references: `auth_result.id` → `auth_result.authenticator.id`
- [ ] Update integration test assertions for nested keys
- [ ] When using authenticator ID in user module: `test_authenticator.authenticator.id` (nested key)
