# Module Comparison: ansible.platform.authenticator_map

**Before:** `stable-2.6` (`platform_main_before_1640`)
**After:** `stable-2.7` / ANSTRAT-1640 branch
**Module:** `ansible.platform.authenticator_map`

---

## Summary

The `authenticator_map` module **arguments are largely unchanged**. This module maps authenticator fields to external login attributes. What changed:

1. **Result structure** — all fields now nested under `result.authenticator_map` instead of flat
2. **Execution path** — module is now doc-only; action plugin handles logic
3. **Internal implementation** — uses `AnsibleAuthenticatorMap` dataclass
4. **Integration tests** — assertions changed from `result.id` → `result.authenticator_map.id`

---

## 1. Arguments — UNCHANGED

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `authenticator` | str | **yes** | — | Authenticator name or ID |
| `map_type` | str | **yes** | — | Type of mapping (e.g., `dn`, `username`, `email`) |
| `new_map_type` | str | no | — | Rename mapping type |
| `organization` | str | no | — | Organization name or ID |
| `team` | str | no | — | Team name or ID |
| `state` | str | no | `present` (default), `absent`, `exists`, `enforced` | Desired state |

**No changes to arguments.**

---

## 2. Result Structure

### Before (2.6.x) — flat top-level keys

```json
{
    "changed": true,
    "id": 9,
    "authenticator": 1,
    "map_type": "dn",
    "organization": null,
    "team": null
}
```

### After (2.7.x) — nested under `authenticator_map` key

```json
{
    "changed": true,
    "authenticator_map": {
        "id": 9,
        "authenticator": 1,
        "map_type": "dn",
        "organization": null,
        "team": null
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
| `id` | `result.id` | `result.authenticator_map.id` |
| `authenticator` | `result.authenticator` | `result.authenticator_map.authenticator` |
| `map_type` | `result.map_type` | `result.authenticator_map.map_type` |
| `organization` | `result.organization` | `result.authenticator_map.organization` |
| `team` | `result.team` | `result.authenticator_map.team` |

---

## 3. Documentation

2.7 DOCUMENTATION is enhanced with clearer examples and RETURN section.

---

## 4. Examples — IMPROVED

### Before (2.6.x)

```yaml
- name: Create LDAP DN mapping
  ansible.platform.authenticator_map:
    authenticator: "LDAP Authenticator"
    map_type: dn
    organization: "Default"
    state: present
```

### After (2.7.x)

```yaml
- name: Create LDAP DN mapping
  ansible.platform.authenticator_map:
    authenticator: "LDAP Authenticator"
    map_type: dn
    organization: "Default"
    state: present
  register: created_map

- name: Check whether mapping exists
  ansible.platform.authenticator_map:
    authenticator: "LDAP Authenticator"
    map_type: dn
    state: exists
  register: map_check

- name: Delete the mapping
  ansible.platform.authenticator_map:
    authenticator: "LDAP Authenticator"
    map_type: dn
    state: absent
```

---

## 5. Integration Test Changes

All result references changed to nested form:

```yaml
# BEFORE (2.6)
- result.id
- result.authenticator
- result.map_type

# AFTER (2.7)
- result.authenticator_map.id
- result.authenticator_map.authenticator
- result.authenticator_map.map_type
```

---

## 6. Internal Implementation

| Aspect | Before (2.6) | After (2.7) |
|--------|---------|---------|
| Execution | `AAPAuthenticatorMap(module).manage()` runs inline | Action plugin executes via manager |
| Module type | Functional | Doc-only stub |
| Dataclass | `AAPAuthenticatorMap` | `AnsibleAuthenticatorMap` |

---

## 7. Migration Checklist

- [ ] Replace `result.id` → `result.authenticator_map.id`
- [ ] Replace `result.authenticator` → `result.authenticator_map.authenticator`
- [ ] Replace `result.map_type` → `result.authenticator_map.map_type`
- [ ] Replace `result.organization` → `result.authenticator_map.organization`
- [ ] Replace `result.team` → `result.authenticator_map.team`
- [ ] Update integration test assertions for nested keys
- [ ] Update cross-module references if used elsewhere
