# Module Documentation: ansible.platform.service

**Status:** NEW in 2.7 (ANSTRAT-1640)
**Module:** `ansible.platform.service`

---

## Summary

The `service` module is **NEW in 2.7**. It manages services in the platform gateway for routing and load balancing. No migration needed from 2.6 (module did not exist).

This module handles defining services that receive routed requests.

---

## 1. Module Arguments

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `name` | str | **yes** | — | Service name (unique) |
| `url` | str | no | — | Base URL for the service |
| `description` | str | no | — | Service description |
| `state` | str | no | `present` (default), `absent`, `exists` | Desired state |

---

## 2. Result Structure

### After (2.7.x) — nested under `service` key

```json
{
    "changed": true,
    "service": {
        "id": 1,
        "name": "api_service",
        "url": "http://api.internal:8000",
        "description": "API backend service",
        "created": "2025-04-06T12:34:56.000Z",
        "modified": "2025-04-06T12:34:56.000Z"
    },
}
```

### Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Numeric primary key |
| `name` | str | Service name |
| `url` | str | Service base URL |
| `description` | str | Service description |
| `created` | str | ISO 8601 timestamp when record was created |
| `modified` | str | ISO 8601 timestamp of last modification |

---

## 3. Examples

```yaml
# Create a service
- name: Create API service
  ansible.platform.service:
    name: "api_service"
    url: "http://api.internal:8000"
    description: "API backend service"
    state: present
  register: created_service

# Update service URL
- name: Update service
  ansible.platform.service:
    name: "api_service"
    url: "http://api.internal:8080"
    state: present

# Delete a service
- name: Delete service
  ansible.platform.service:
    name: "api_service"
    state: absent
```

---

## 4. Notes

- **New in 2.7:** This module did not exist in 2.6
- **No migration needed:** New functionality only
- **Service discovery:** Services are referenced by name in routes
- **Load balancing:** Services can have multiple nodes for distribution
- **URL format:** Must be a valid URL (http:// or https://)

---

## 5. First-use Checklist

- [ ] Identify backend services in your architecture
- [ ] Create service definitions for each backend
- [ ] Configure service URLs pointing to actual services
- [ ] Create routes to map incoming requests to services
- [ ] Check result at `result.service.*` (nested key structure)
