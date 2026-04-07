# Module Documentation: ansible.platform.http_port

**Status:** NEW in 2.7 (ANSTRAT-1640)
**Module:** `ansible.platform.http_port`

---

## Summary

The `http_port` module is **NEW in 2.7**. It manages HTTP port configuration for the platform gateway. No migration needed from 2.6 (module did not exist).

This module handles configuration of the HTTP listener port settings.

---

## 1. Module Arguments

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `port` | int | no | — | HTTP port number (1024-65535 typically) |
| `state` | str | no | `present` (default), `absent`, `exists` | Desired state |

---

## 2. Result Structure

### After (2.7.x) — nested under `http_port` key

```json
{
    "changed": true,
    "http_port": {
        "id": 1,
        "port": 8080,
        "created": "2025-04-06T12:34:56.000Z",
        "modified": "2025-04-06T12:34:56.000Z"
    },
}
```

### Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Numeric primary key |
| `port` | int | The HTTP port number |
| `created` | str | ISO 8601 timestamp when record was created |
| `modified` | str | ISO 8601 timestamp of last modification |

---

## 3. Examples

```yaml
# Set HTTP port
- name: Configure HTTP port
  ansible.platform.http_port:
    port: 8080
    state: present

# Check HTTP port configuration
- name: Check HTTP port
  ansible.platform.http_port:
    state: exists
  register: port_config
```

---

## 4. Notes

- **New in 2.7:** This module did not exist in 2.6
- **No migration needed:** New functionality only
- **Port restrictions:** Standard privilege separation rules apply (ports < 1024 require elevated privileges)
- **Singleton resource:** HTTP port is typically a singleton configuration

---

## 5. First-use Checklist

- [ ] Verify port is available and not in use
- [ ] Ensure proper permissions for the port number
- [ ] Test in non-production environment first
- [ ] Check result at `result.http_port.*` (nested key structure)
