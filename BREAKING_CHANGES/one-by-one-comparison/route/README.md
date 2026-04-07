# Module Documentation: ansible.platform.route

**Status:** NEW in 2.7 (ANSTRAT-1640)
**Module:** `ansible.platform.route`

---

## Summary

The `route` module is **NEW in 2.7**. It manages HTTP routing rules in the platform gateway. No migration needed from 2.6 (module did not exist).

This module handles configuring route definitions for request routing and load balancing.

---

## 1. Module Arguments

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `name` | str | **yes** | — | Route name (unique) |
| `service` | str | no | — | Service name or ID |
| `source` | str | no | — | Source path pattern |
| `destination` | str | no | — | Destination path pattern |
| `state` | str | no | `present` (default), `absent`, `exists` | Desired state |

---

## 2. Result Structure

### After (2.7.x) — nested under `route` key

```json
{
    "changed": true,
    "route": {
        "id": 2,
        "name": "api_route",
        "service": 1,
        "source": "/api",
        "destination": "/gateway/api",
        "created": "2025-04-06T12:34:56.000Z",
        "modified": "2025-04-06T12:34:56.000Z"
    },
}
```

### Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Numeric primary key |
| `name` | str | Route name |
| `service` | int | Associated service ID |
| `source` | str | Source path pattern |
| `destination` | str | Destination path pattern |
| `created` | str | ISO 8601 timestamp when record was created |
| `modified` | str | ISO 8601 timestamp of last modification |

---

## 3. Examples

```yaml
# Create a route
- name: Create API route
  ansible.platform.route:
    name: "api_route"
    service: "api_service"
    source: "/api"
    destination: "/gateway/api"
    state: present

# Update route destination
- name: Update route
  ansible.platform.route:
    name: "api_route"
    destination: "/backend/api"
    state: present

# Delete a route
- name: Delete route
  ansible.platform.route:
    name: "api_route"
    state: absent
```

---

## 4. Notes

- **New in 2.7:** This module did not exist in 2.6
- **No migration needed:** New functionality only
- **Pattern matching:** Routes support path patterns for flexible routing
- **Services:** Routes must reference existing services
- **Load balancing:** Routes enable request distribution across service nodes

---

## 5. First-use Checklist

- [ ] Understand path pattern syntax for source/destination
- [ ] Ensure referenced services exist
- [ ] Test routing rules in non-production first
- [ ] Verify traffic flows correctly to destination
- [ ] Check result at `result.route.*` (nested key structure)
