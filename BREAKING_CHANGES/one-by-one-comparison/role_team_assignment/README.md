# Module Comparison: ansible.platform.role_team_assignment

**Before:** `stable-2.6` (`platform_main_before_1640`)
**After:** `stable-2.7` / ANSTRAT-1640 branch
**Module:** `ansible.platform.role_team_assignment`

---

## Summary

The `role_team_assignment` module **arguments are unchanged**. Like `role_user_assignment`, this module has no natural "name" field—it uses compound keys (role_definition, team, object_id). What changed:

1. **Result structure** — all fields now nested under `result.role_team_assignment` instead of flat
2. **Execution path** — module is now doc-only; action plugin handles logic
3. **Internal implementation** — uses `AnsibleRoleTeamAssignment` dataclass
4. **Integration tests** — assertions changed from `result.id` → `result.role_team_assignment.id`

---

## 1. Arguments — UNCHANGED

This module has NO `name`-like lookup field. It uses:

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `role_definition` | str | **yes** | — | Role name or ID |
| `team` | str | **yes** | — | Team name or team ID |
| `object_id` | str | no* | — | ID of the object (org, team, etc.) being assigned |
| `object_ids` | list[str] | no* | — | List of object IDs for bulk assignments |
| `object_ansible_id` | str | no* | — | Ansible UUID of the object |
| `team_ansible_id` | str | no* | — | Ansible UUID of the team |
| `state` | str | no | `present` (default), `absent`, `exists` | Desired state |

*One of `object_id`, `object_ids`, or `object_ansible_id` is required.

**No changes to arguments.**

---

## 2. Result Structure

### Before (2.6.x) — flat top-level keys

```json
{
    "changed": true,
    "id": 456,
    "role_definition": 3,
    "object_id": 5,
    "team": 12
}
```

### After (2.7.x) — nested under `role_team_assignment` key

```json
{
    "changed": true,
    "role_team_assignment": {
        "id": 456,
        "role_definition": 3,
        "object_id": 5,
        "team": 12
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
| `id` | `result.id` | `result.role_team_assignment.id` |
| `role_definition` | `result.role_definition` | `result.role_team_assignment.role_definition` |
| `team` | `result.team` | `result.role_team_assignment.team` |
| `object_id` | `result.object_id` | `result.role_team_assignment.object_id` |

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
- name: Give Team Developers organization admin role for org 1
  ansible.platform.role_team_assignment:
    role_definition: Organization Admin
    object_id: 1
    team: "Team Developers"
    state: present

- name: Give Team Developers Team admin role for multiple teams
  ansible.platform.role_team_assignment:
    role_definition: Team Admin
    object_ids: ['1', '2']
    team: "Team Developers"
    state: present
```

### After (2.7.x)

```yaml
- name: Give Team Developers organization admin role for org 1
  ansible.platform.role_team_assignment:
    role_definition: Organization Admin
    object_id: 1
    team: "Team Developers"
    state: present
  register: team_role_assignment

- name: Verify the role assignment
  ansible.platform.role_team_assignment:
    role_definition: Organization Admin
    object_id: 1
    team: "Team Developers"
    state: exists
  register: role_check

- name: Remove Team Developers' organization admin role
  ansible.platform.role_team_assignment:
    role_definition: Organization Admin
    object_id: 1
    team: "Team Developers"
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
- result.team

# AFTER (2.7)
- result.role_team_assignment.id
- result.role_team_assignment.role_definition
- result.role_team_assignment.object_id
- result.role_team_assignment.team
```

---

## 6. Internal Implementation

| Aspect | Before (2.6) | After (2.7) |
|--------|---------|---------|
| Execution | Custom inline logic in `assign_team_role()` | Action plugin executes via manager |
| Module type | Functional | Doc-only stub |
| Dataclass | None (custom logic) | `AnsibleRoleTeamAssignment` |

---

## 7. Migration Checklist

- [ ] Replace `result.id` → `result.role_team_assignment.id`
- [ ] Replace `result.role_definition` → `result.role_team_assignment.role_definition`
- [ ] Replace `result.team` → `result.role_team_assignment.team`
- [ ] Replace `result.object_id` → `result.role_team_assignment.object_id`
- [ ] Update integration test assertions for nested keys
- [ ] Update cleanup blocks that reference assignment results
- [ ] Remember: this module has no natural "name" field; it's identified by compound key (role + team + object)
