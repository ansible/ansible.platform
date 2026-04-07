# Module Documentation: ansible.platform.service_key

**Status:** NEW in 2.7 (ANSTRAT-1640)
**Module:** `ansible.platform.service_key`

---

## Summary

The `service_key` module is **NEW in 2.7**. It manages API keys for service authentication in the platform gateway. No migration needed from 2.6 (module did not exist).

This module handles creating and rotating service authentication keys.

---

## 1. Module Arguments

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `name` | str | **yes** | — | Key name (unique) |
| `service` | str | **yes** | — | Service name or ID |
| `description` | str | no | — | Key description |
| `state` | str | no | `present` (default), `absent`, `exists` | Desired state |

---

## 2. Result Structure

### After (2.7.x) — nested under `service_key` key

```json
{
    "changed": true,
    "service_key": {
        "id": 5,
        "name": "prod_api_key",
        "service": 1,
        "key": "sk-1234567890abcdef",
        "description": "Production API key",
        "created": "2025-04-06T12:34:56.000Z",
        "modified": "2025-04-06T12:34:56.000Z"
    },
}
```

### Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Numeric primary key |
| `name` | str | Key name |
| `service` | int | Associated service ID |
| `key` | str | The API key (secret) |
| `description` | str | Key description |
| `created` | str | ISO 8601 timestamp when record was created |
| `modified` | str | ISO 8601 timestamp of last modification |

---

## 3. Examples

```yaml
# Create a service key
- name: Create production API key
  ansible.platform.service_key:
    name: "prod_api_key"
    service: "api_service"
    description: "Production API key"
    state: present
  register: created_key

# Store the key securely
- name: Save API key (example)
  ansible.builtin.copy:
    content: "{{ created_key.service_key.key }}"
    dest: "/etc/secure/api_key.txt"
    mode: '0600'

# Delete a key (e.g., for rotation)
- name: Revoke old key
  ansible.platform.service_key:
    name: "old_api_key"
    state: absent
```

---

## 4. Notes

- **New in 2.7:** This module did not exist in 2.6
- **No migration needed:** New functionality only
- **Secret storage:** Keys are returned only on creation; store securely
- **Key rotation:** Create new key, update service config, then delete old key
- **Sensitive data:** Never log or display keys directly; use no_log where appropriate

---

## 5. First-use Checklist

- [ ] Identify services needing authentication keys
- [ ] Create keys for each service that needs one
- [ ] Store keys securely (vault, secrets manager)
- [ ] Configure services to use the keys
- [ ] Implement key rotation policy
- [ ] Check result at `result.service_key.*` (nested key structure)
