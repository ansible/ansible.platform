# Module Comparison: ansible.platform.team

**Before:** `stable-2.6` (`platform_main_before_1640`)
**After:** `stable-2.7` / ANSTRAT-1640 branch
**Module:** `ansible.platform.team`

---

## Summary

The `team` module **arguments are unchanged**. What changed:

1. **Result structure** — all fields now nested under `result.team` instead of flat
2. **Execution path** — module is now doc-only; action plugin handles logic
3. **Internal implementation** — uses `AnsibleTeam` dataclass instead of `AAPTeam`
4. **Integration tests** — assertions changed from `result.id` → `result.team.id`

---

## 1. Arguments — UNCHANGED

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `name` | str | **yes** | — | Team name (unique within organization) |
| `new_name` | str | no | — | Rename to new name |
| `description` | str | no | — | Team description |
| `organization` | str | **yes** | — | Organization name or ID |
| `new_organization` | str | no | — | Move to different organization |
| `state` | str | no | `present` (default), `absent`, `exists`, `enforced` | Desired state |

**No changes to arguments.**

---

## 2. Result Structure

### Before (2.6.x) — flat top-level keys

```json
{
    "changed": true,
    "id": 7,
    "name": "Gateway Developers",
    "description": "AAP Gateway Developers Team",
    "organization": 5
}
```

### After (2.7.x) — nested under `team` key

```json
{
    "changed": true,
    "team": {
        "id": 7,
        "name": "Gateway Developers",
        "description": "AAP Gateway Developers Team",
        "organization": 5
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
| `id` | `result.id` | `result.team.id` |
| `name` | `result.name` | `result.team.name` |
| `description` | `result.description` | `result.team.description` |
| `organization` | `result.organization` | `result.team.organization` |

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
- name: Create Team
  ansible.platform.team:
    name: Gateway Developers
    description: AAP Gateway Developers Team
    organization: Ansible Product Development

- name: Delete Team
  ansible.platform.team:
    name: Gateway Developers
    organization: "Red Hat Ansible"
    state: absent
```

### After (2.7.x)

```yaml
- name: Create a team
  ansible.platform.team:
    name: Gateway Developers
    description: AAP Gateway Developers Team
    organization: Ansible Product Development
  register: created_team

- name: Round-trip update using registered result
  ansible.platform.team: "{{ created_team.team | combine({'description': 'Updated description'}) }}"

- name: Check whether a team exists
  ansible.platform.team:
    name: Gateway Developers
    organization: Ansible Product Development
    state: exists
  register: team_check

- name: Delete a team
  ansible.platform.team:
    name: Gateway Developers
    organization: Ansible Product Development
    state: absent
```

---

## 5. Integration Test Changes

All result references changed to nested form:

```yaml
# BEFORE (2.6)
- team.id
- team.organization

# AFTER (2.7)
- team.team.id
- team.team.organization
```

---

## 6. Internal Implementation

| Aspect | Before (2.6) | After (2.7) |
|--------|---------|---------|
| Execution | `AAPTeam(module).manage()` runs inline | Action plugin executes via manager |
| Module type | Functional | Doc-only stub |
| Dataclass | `AAPTeam` | `AnsibleTeam` |

---

## 7. Migration Checklist

- [ ] Replace `result.id` → `result.team.id`
- [ ] Replace `result.name` → `result.team.name`
- [ ] Replace `result.organization` → `result.team.organization`
- [ ] Replace `result.description` → `result.team.description`
- [ ] Update integration test assertions for nested keys
- [ ] Update cross-module references: `org_result.id` → `org_result.organization.id`
