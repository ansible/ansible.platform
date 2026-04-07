# Module Comparison: ansible.platform.token

**Before:** `stable-2.6` (`platform_main_before_1640`)
**After:** `stable-2.7` / ANSTRAT-1640 branch
**Module:** `ansible.platform.token`

---

## Summary

The `token` module **arguments are largely unchanged** but has special behavior regarding return values and `ansible_facts`. What changed:

1. **Result structure** — token data now nested under `result.token` instead of flat
2. **Execution path** — module is now doc-only; action plugin handles logic
3. **Internal implementation** — uses `AnsibleToken` dataclass instead of custom logic
4. **Integration tests** — assertions changed from `result.id` → `result.token.id`
6. **ansible_facts behavior** — **PRESERVED**: `ansible_facts.aap_token` is still set for convenience (backward-compatible)

---

## 1. Arguments — UNCHANGED

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `description` | str | no | — | Token description |
| `application` | str | no | — | Application name or ID (optional) |
| `organization` | str | no | — | Organization name or ID (optional, for lookup context) |
| `scope` | str | no | `read`, `write` | Token permission scope |
| `existing_token` | dict | no | — | Token dict from a prior create (for deletion) |
| `existing_token_id` | str | no | — | Token ID (number) for deletion |
| `state` | str | no | `present` (default), `absent` | Desired state |

**No changes to arguments.**

---

## 2. Result Structure

### Before (2.6.x) — flat top-level keys + ansible_facts

```json
{
    "changed": true,
    "id": 42,
    "token": "abcdef1234567890...",
    "description": "API token",
    "scope": "write",
    "application": null,
    "ansible_facts": {
        "aap_token": "abcdef1234567890..."
    }
}
```

### After (2.7.x) — nested under `token` key + ansible_facts (PRESERVED)

```json
{
    "changed": true,
    "token": {
        "id": 42,
        "token": "abcdef1234567890...",
        "description": "API token",
        "scope": "write",
        "application": null
    },
    "ansible_facts": {
        "aap_token": "abcdef1234567890..."
    },
}
```

### Key differences

| Field | Before | After |
|-------|--------|-------|
| `id` | `result.id` | `result.token.id` |
| `token` (the secret string) | `result.token` | `result.token.token` |
| `description` | `result.description` | `result.token.description` |
| `scope` | `result.scope` | `result.token.scope` |
| `application` | `result.application` | `result.token.application` |
| `ansible_facts.aap_token` | `result.ansible_facts.aap_token` | **PRESERVED**: `result.ansible_facts.aap_token` |

---

## 3. Documentation

2.7 DOCUMENTATION is unchanged from 2.6 (token module docs are doc-only in 2.7).

---

## 4. Examples — UNCHANGED BEHAVIOR

### Before and After (behavior is the same)

```yaml
- block:
    - name: Create a new token
      ansible.platform.token:
        description: 'My API token'
        scope: "write"
        state: present
        aap_token: "{{ existing_token }}"
      register: token_result

    # 2.7: Access nested token data
    - name: Show token details
      ansible.builtin.debug:
        msg: "Token ID: {{ token_result.token.id }}, Secret: {{ token_result.token.token }}"

    # BOTH versions: ansible_facts.aap_token is set automatically
    - name: Use the token fact in later tasks
      ansible.builtin.debug:
        msg: "Token fact is available as: {{ aap_token }}"

  always:
    - name: Delete the token
      ansible.platform.token:
        existing_token: "{{ token_result.token }}"
        state: absent
```

---

## 5. Integration Test Changes

All token result references changed to nested form:

```yaml
# BEFORE (2.6)
- result.id
- result.token (the secret string)
- result.description

# AFTER (2.7)
- result.token.id
- result.token.token (the secret string)
- result.token.description
```

**However**, `ansible_facts.aap_token` remains unchanged in both versions for backward compatibility.

---

## 6. Internal Implementation

| Aspect | Before (2.6) | After (2.7) |
|--------|---------|---------|
| Execution | Custom logic in `main()` | Action plugin executes via manager |
| Module type | Functional | Doc-only stub |
| Dataclass | None (custom logic) | `AnsibleToken` |
| Special behavior | Sets `ansible_facts.aap_token` | **Preserved**: Still sets `ansible_facts.aap_token` |

**Special note:** The action plugin preserves the `ansible_facts` behavior for backward compatibility. Existing playbooks that rely on `aap_token` fact will continue to work.

---

## 7. Migration Checklist

- [ ] Replace `result.id` → `result.token.id`
- [ ] Replace `result.token` → `result.token.token` (the nested secret string)
- [ ] Replace `result.description` → `result.token.description`
- [ ] Replace `result.scope` → `result.token.scope`
- [ ] Replace `result.application` → `result.token.application`
- [ ] **VERIFY** that `ansible_facts.aap_token` is still available (it is — backward compatible)
- [ ] Update integration test assertions for nested `token` key
- [ ] When passing token to `existing_token` for deletion, use `result.token` (the dict, not the string)
- [ ] Verify ansible_facts usage still works: references to `{{ aap_token }}` should still be valid
