# Module Documentation: ansible.platform.role_definition

**Status:** NEW in 2.7 (ANSTRAT-1640)
**Module:** `ansible.platform.role_definition`

---

## Summary

The `role_definition` module is **NEW in 2.7**. It manages role definitions (what permissions roles grant). No migration needed from 2.6 (module did not exist).

This module handles creating, updating, and deleting role definitions that define permission sets in the system.

---

## 1. Module Arguments

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `name` | str | **yes** | — | Role definition name (unique) |
| `description` | str | no | — | Role description |
| `permissions` | list[str] | no | — | List of permission identifiers |
| `state` | str | no | `present` (default), `absent`, `exists` | Desired state |

---

## 2. Result Structure

### After (2.7.x) — nested under `role_definition` key

```json
{
    "changed": true,
    "role_definition": {
        "id": 5,
        "name": "Custom Role",
        "description": "Custom role for organization management",
        "permissions": ["org.change_organization", "org.view_organization"],
        "created": "2025-04-06T12:34:56.000Z",
        "modified": "2025-04-06T12:34:56.000Z"
    },
}
```

### Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Numeric primary key |
| `name` | str | The role name |
| `description` | str | Role description |
| `permissions` | list[str] | List of granted permissions |
| `created` | str | ISO 8601 timestamp when record was created |
| `modified` | str | ISO 8601 timestamp of last modification |

---

## 3. Examples

```yaml
# Create custom role with permissions
- name: Create custom role
  ansible.platform.role_definition:
    name: "Custom Role"
    description: "Custom role for organization management"
    permissions:
      - "org.change_organization"
      - "org.view_organization"
    state: present

# Update role permissions
- name: Update role
  ansible.platform.role_definition:
    name: "Custom Role"
    permissions:
      - "org.change_organization"
      - "org.view_organization"
      - "team.view_team"
    state: present

# Check if role exists
- name: Check role definition
  ansible.platform.role_definition:
    name: "Custom Role"
    state: exists
```

---

## 4. Notes

- **New in 2.7:** This module did not exist in 2.6
- **No migration needed:** New functionality only
- **Permission format:** Permissions follow `<app>.<action_<resource>` format
- **Built-in roles:** Platform includes built-in roles; create custom ones as needed
- **Assignments:** Use `role_user_assignment` and `role_team_assignment` to assign roles

---

## 5. First-use Checklist

- [ ] Identify available permissions from platform API documentation
- [ ] Design role permission sets appropriate for your organization
- [ ] Test in non-production environment first
- [ ] Document custom roles for team reference
- [ ] Check result at `result.role_definition.*` (nested key structure)
