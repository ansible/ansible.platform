# Module Documentation: ansible.platform.feature_flag

**Status:** NEW in 2.7 (ANSTRAT-1640)
**Module:** `ansible.platform.feature_flag`

---

## Summary

The `feature_flag` module is **NEW in 2.7**. It manages feature flags for controlling experimental or optional functionality in the platform. No migration needed from 2.6 (module did not exist).

This module handles enabling, disabling, and checking feature flags that control platform behavior.

---

## 1. Module Arguments

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `name` | str | **yes** | — | Feature flag name (unique) |
| `enabled` | bool | no | — | Whether the feature is enabled |
| `state` | str | no | `present` (default), `absent`, `exists` | Desired state |

---

## 2. Result Structure

### After (2.7.x) — nested under `feature_flag` key

```json
{
    "changed": true,
    "feature_flag": {
        "id": 1,
        "name": "experimental_feature_x",
        "enabled": true,
        "created": "2025-04-06T12:34:56.000Z",
        "modified": "2025-04-06T12:34:56.000Z"
    },
}
```

### Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Numeric primary key |
| `name` | str | The feature flag name |
| `enabled` | bool | Whether the feature is enabled |
| `created` | str | ISO 8601 timestamp when record was created |
| `modified` | str | ISO 8601 timestamp of last modification |

---

## 3. Examples

```yaml
# Enable a feature flag
- name: Enable experimental feature
  ansible.platform.feature_flag:
    name: "experimental_feature_x"
    enabled: true
    state: present

# Disable a feature
- name: Disable experimental feature
  ansible.platform.feature_flag:
    name: "experimental_feature_x"
    enabled: false
    state: present

# Check if feature flag exists
- name: Check feature flag status
  ansible.platform.feature_flag:
    name: "experimental_feature_x"
    state: exists
```

---

## 4. Notes

- **New in 2.7:** This module did not exist in 2.6
- **No migration needed:** New functionality only
- **Platform control:** Feature flags manage experimental or beta features
- **Idempotent:** Module is idempotent; re-running with same values makes no changes

---

## 5. First-use Checklist

- [ ] Identify feature flags supported by your platform version
- [ ] Test enablement/disablement in non-production first
- [ ] Check result at `result.feature_flag.*` (nested key structure)
