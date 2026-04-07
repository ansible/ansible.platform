# Module Comparison: ansible.platform.organization

**Before:** `stable-2.6` (`platform_main_before_1640`)
**After:** `stable-2.7` / ANSTRAT-1640 branch
**Module:** `ansible.platform.organization`

---

## Summary

The `organization` module **arguments are unchanged**. What changed:

1. **Result structure** — all fields now nested under `result.organization` instead of flat
2. **Execution path** — module is now doc-only; action plugin handles logic
3. **Internal implementation** — uses `AnsibleOrganization` dataclass instead of `AAPOrganization`
4. **Integration tests** — assertions changed from `result.id` → `result.organization.id`

---

## 1. Arguments — UNCHANGED

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `name` | str | **yes** | — | Organization name (unique) |
| `new_name` | str | no | — | Rename to new name |
| `description` | str | no | — | Organization description |
| `state` | str | no | `present` (default), `absent`, `exists`, `enforced` | Desired state |

**No changes to arguments.**

---

## 2. Result Structure

### Before (2.6.x) — flat top-level keys

```json
{
    "changed": true,
    "id": 5,
    "name": "Ansible Product Development",
    "description": "Organization for ansible developers"
}
```

### After (2.7.x) — nested under `organization` key

```json
{
    "changed": true,
    "organization": {
        "id": 5,
        "name": "Ansible Product Development",
        "description": "Organization for ansible developers"
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
| `id` | `result.id` | `result.organization.id` |
| `name` | `result.name` | `result.organization.name` |
| `description` | `result.description` | `result.organization.description` |

---

## 3. Documentation

2.7 DOCUMENTATION is enhanced with:
- Clearer state descriptions
- RETURN section documenting nested key
- More complete examples with round-trip pattern
- `version_added` field

---

## 4. Examples — IMPROVED

### Before (2.6.x) — minimal

```yaml
- name: Create Organization
  ansible.platform.organization:
    name: Ansible Product Development
    description: Organization for ansible developers

- name: Delete Organization
  ansible.platform.organization:
    name: Ansible Product Development
    state: absent
```

### After (2.7.x) — comprehensive

```yaml
- name: Create an organization
  ansible.platform.organization:
    name: Ansible Product Development
    description: Organization for ansible developers
  register: created_org

- name: Round-trip update using registered result
  ansible.platform.organization: "{{ created_org.organization | combine({'description': 'Updated description'}) }}"

- name: Check whether an organization exists
  ansible.platform.organization:
    name: Ansible Platform Development
    state: exists
  register: org_check

- name: Delete an organization
  ansible.platform.organization:
    name: Ansible Platform Development
    state: absent
```

---

## 5. Integration Test Changes

All result references changed to nested form:

```yaml
# BEFORE (2.6)
- org.id
- org.name

# AFTER (2.7)
- org.organization.id
- org.organization.name
```

---

## 6. Internal Implementation

| Aspect | Before (2.6) | After (2.7) |
|--------|---------|---------|
| Execution | `AAPOrganization(module).manage()` runs inline | Action plugin executes via manager |
| Module type | Functional | Doc-only stub |
| Dataclass | `AAPOrganization` | `AnsibleOrganization` |

---

## 7. Migration Checklist

- [ ] Replace `result.id` → `result.organization.id`
- [ ] Replace `result.name` → `result.organization.name`
- [ ] Replace `result.description` → `result.organization.description`
- [ ] Update integration test assertions for nested keys
- [ ] Test round-trip pattern: pass registered result back with combine() to update
