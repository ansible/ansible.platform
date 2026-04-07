# Module Comparison: ansible.platform.role_user_assignment

**Before:** `stable-2.6` (`platform_main_before_1640`)
**After:** `stable-2.7` / ANSTRAT-1640 branch
**Module:** `ansible.platform.role_user_assignment`

---

## Summary

The `role_user_assignment` module **arguments are unchanged**. This is a special module with no natural "name" field—it uses compound keys (role_definition, user, object_id). What changed:

1. **Result structure** — all fields now nested under `result.role_user_assignment` instead of flat
2. **Execution path** — module is now doc-only; action plugin handles logic
3. **Internal implementation** — uses `AnsibleRoleUserAssignment` dataclass
4. **Integration tests** — assertions changed from `result.id` → `result.role_user_assignment.id`

---

## 1. Arguments — UNCHANGED

This module has NO `name`-like lookup field. It uses:

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `role_definition` | str | **yes** | — | Role name or ID |
| `user` | str | **yes** | — | Username or user ID |
| `object_id` | str | no* | — | ID of the object (org, team, etc.) being assigned |
| `object_ids` | list[str] | no* | — | List of object IDs for bulk assignments |
| `object_ansible_id` | str | no* | — | Ansible UUID of the object |
| `user_ansible_id` | str | no* | — | Ansible UUID of the user |
| `state` | str | no | `present` (default), `absent`, `exists` | Desired state |

*One of `object_id`, `object_ids`, or `object_ansible_id` is required.

**No changes to arguments.**

---

## 2. Result Structure

### Before (2.6.x) — flat top-level keys

```json
{
    "changed": true,
    "id": 123,
    "role_definition": 2,
    "object_id": 5,
    "user": 42
}
```

### After (2.7.x) — nested under `role_user_assignment` key

```json
{
    "changed": true,
    "role_user_assignment": {
        "id": 123,
        "role_definition": 2,
        "object_id": 5,
        "user": 42
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
| `id` | `result.id` | `result.role_user_assignment.id` |
| `role_definition` | `result.role_definition` | `result.role_user_assignment.role_definition` |
| `user` | `result.user` | `result.role_user_assignment.user` |
| `object_id` | `result.object_id` | `result.role_user_assignment.object_id` |

---

## 3. Documentation

2.7 DOCUMENTATION is enhanced with:
- Clearer state descriptions
- RETURN section documenting nested key
- More complete examples
- `version_added` field

---

## 4. Examples — IMPROVED

### Before (2.6.x)

```yaml
- name: Give Bob organization admin role for org 1
  ansible.platform.role_user_assignment:
    role_definition: Organization Admin
    object_id: 1
    user: bob
    state: present

- name: Give Bob Team admin role for teams with id 1 and name "team2"
  ansible.platform.role_user_assignment:
    role_definition: Team Admin
    object_ids: ['1', 'team2']
    user: bob
    state: present
```

### After (2.7.x)

```yaml
- name: Give Bob organization admin role for org 1
  ansible.platform.role_user_assignment:
    role_definition: Organization Admin
    object_id: 1
    user: bob
    state: present
  register: role_assignment

- name: Verify Bob has the admin role
  ansible.platform.role_user_assignment:
    role_definition: Organization Admin
    object_id: 1
    user: bob
    state: exists
  register: role_check

- name: Remove Bob's organization admin role
  ansible.platform.role_user_assignment:
    role_definition: Organization Admin
    object_id: 1
    user: bob
    state: absent
```

---

## 5. Integration Test Changes

All result references changed to nested form:

```yaml
# BEFORE (2.6)
- result.id
- result.role_definition
- result.object_id

# AFTER (2.7)
- result.role_user_assignment.id
- result.role_user_assignment.role_definition
- result.role_user_assignment.object_id
```

---

## 6. Internal Implementation

| Aspect | Before (2.6) | After (2.7) |
|--------|---------|---------|
| Execution | Custom inline logic in `assign_user_role()` | Action plugin executes via manager |
| Module type | Functional | Doc-only stub |
| Dataclass | None (custom logic) | `AnsibleRoleUserAssignment` |

---

## 7. Migration Checklist

- [ ] Replace `result.id` → `result.role_user_assignment.id`
- [ ] Replace `result.role_definition` → `result.role_user_assignment.role_definition`
- [ ] Replace `result.user` → `result.role_user_assignment.user`
- [ ] Replace `result.object_id` → `result.role_user_assignment.object_id`
- [ ] Update integration test assertions for nested keys
- [ ] Update cleanup blocks that reference assignment results
- [ ] Remember: this module has no natural "name" field; it's identified by compound key (role + user + object)
