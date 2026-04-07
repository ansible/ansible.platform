# Module Comparison: ansible.platform.settings

**Before:** `stable-2.6` (`platform_main_before_1640`)
**After:** `stable-2.7` / ANSTRAT-1640 branch
**Module:** `ansible.platform.settings`

---

## Summary

The `settings` module is **SPECIAL**: it is a singleton-like resource with no `id` field and no natural lookup key. It manages global platform settings via PATCH operations. What changed:

1. **Result structure** — all fields now nested under `result.settings` instead of flat
2. **Execution path** — module is now doc-only; action plugin handles logic
3. **Internal implementation** — uses `AnsibleSettings` dataclass; special handling for PATCH-only updates
4. **Integration tests** — assertions changed from `result.<field>` → `result.settings.<field>`
6. **No name/id lookup** — settings are always fetched by singleton pattern

---

## 1. Arguments — UNCHANGED

Settings module accepts any platform setting as a keyword argument. Common settings include:

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `<setting_name>` | (varies) | no | Any setting name accepted by platform API |
| `state` | str | no | `present` (default), `absent`, `exists`, `enforced` | Desired state |

**No changes to arguments.** The module dynamically accepts all platform settings.

---

## 2. Result Structure

### Before (2.6.x) — flat top-level keys

```json
{
    "changed": true,
    "setting_name_1": "value1",
    "setting_name_2": 42,
    "setting_name_3": true
}
```

### After (2.7.x) — nested under `settings` key

```json
{
    "changed": true,
    "settings": {
        "setting_name_1": "value1",
        "setting_name_2": 42,
        "setting_name_3": true
    },
}
```
> **Backward Compatibility (2.7.x):** Flat top-level keys (`result.id`, `result.username`, etc.)
> are kept alongside the nested key for backward compatibility with ≤2.6 playbooks.
> They are silently deprecated and scheduled for removal after 2028-04-01.
> Prefer `result.<module>.<field>` in new code.



### Key differences

| Aspect | Before | After |
|--------|--------|-------|
| Any setting field | `result.<setting_name>` | `result.settings.<setting_name>` |

---

## 3. Documentation

2.7 DOCUMENTATION is enhanced with:
- Clarification that this is a singleton resource
- RETURN section documenting nested `settings` key
- Notes about dynamic setting names
- PATCH-only behavior documented

---

## 4. Examples — IMPROVED

### Before (2.6.x)

```yaml
- name: Update platform settings
  ansible.platform.settings:
    setting_name_1: "new_value"
    setting_name_2: 100
    state: present
```

### After (2.7.x)

```yaml
- name: Update platform settings
  ansible.platform.settings:
    setting_name_1: "new_value"
    setting_name_2: 100
    state: present
  register: updated_settings

- name: Check current settings
  ansible.platform.settings:
    state: exists
  register: current_settings

- name: Access specific setting
  ansible.builtin.debug:
    msg: "Current value: {{ current_settings.settings.setting_name_1 }}"
```

---

## 5. Integration Test Changes

All setting references changed to nested form:

```yaml
# BEFORE (2.6)
- result.setting_name_1
- result.setting_name_2

# AFTER (2.7)
- result.settings.setting_name_1
- result.settings.setting_name_2
```

---

## 6. Internal Implementation

| Aspect | Before (2.6) | After (2.7) |
|--------|---------|---------|
| Execution | Custom logic in `settings_module()` | Action plugin executes via manager |
| Module type | Functional | Doc-only stub |
| Dataclass | `AAPSettings` | `AnsibleSettings` |
| Lookup pattern | Singleton (no lookup key) | Singleton (no lookup key) |
| HTTP method | PATCH only | PATCH only |

**Special note:** Settings have no `id` or natural name field. They are always retrieved and updated as a whole (PATCH to `/settings/`).

---

## 7. Migration Checklist

- [ ] Replace all `result.<setting_name>` → `result.settings.<setting_name>`
- [ ] Remember: this resource has no id field; operations are PATCH-only
- [ ] Update integration test assertions for nested `settings` key
- [ ] When reading current settings, use `state: exists` and access via `result.settings.<name>`
- [ ] Enforcement of full state: when using `state: enforced`, all unspecified settings are left unchanged
