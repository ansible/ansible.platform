# Module Documentation: ansible.platform.service_type

**Status:** NEW in 2.7 (ANSTRAT-1640)
**Module:** `ansible.platform.service_type`

---

## Summary

The `service_type` module is **NEW in 2.7**. It manages service type definitions that categorize services in the platform gateway. No migration needed from 2.6 (module did not exist).

This module handles defining different service type categories.

---

## 1. Module Arguments

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `name` | str | **yes** | — | Service type name (unique) |
| `description` | str | no | — | Service type description |
| `state` | str | no | `present` (default), `absent`, `exists` | Desired state |

---

## 2. Result Structure

### After (2.7.x) — nested under `service_type` key

```json
{
    "changed": true,
    "service_type": {
        "id": 2,
        "name": "api",
        "description": "API service type",
        "created": "2025-04-06T12:34:56.000Z",
        "modified": "2025-04-06T12:34:56.000Z"
    },
}
```

### Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Numeric primary key |
| `name` | str | Service type name |
| `description` | str | Service type description |
| `created` | str | ISO 8601 timestamp when record was created |
| `modified` | str | ISO 8601 timestamp of last modification |

---

## 3. Examples

```yaml
# Create service type
- name: Create API service type
  ansible.platform.service_type:
    name: "api"
    description: "API service type"
    state: present

# Create multiple service types
- name: Create service types
  ansible.platform.service_type:
    name: "{{ item.name }}"
    description: "{{ item.description }}"
    state: present
  loop:
    - name: "api"
      description: "API service type"
    - name: "database"
      description: "Database service type"
    - name: "cache"
      description: "Cache service type"
```

---

## 4. Notes

- **New in 2.7:** This module did not exist in 2.6
- **No migration needed:** New functionality only
- **Categorization:** Service types help organize and filter services
- **Optional:** Services may or may not require a type
- **Platform-defined:** Platform may ship with built-in service types

---

## 5. First-use Checklist

- [ ] Identify service categories in your infrastructure
- [ ] Create service type definitions
- [ ] Categorize services using these types
- [ ] Use service_type filters for management
- [ ] Check result at `result.service_type.*` (nested key structure)
