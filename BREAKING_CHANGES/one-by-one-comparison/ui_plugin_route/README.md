# Module Documentation: ansible.platform.ui_plugin_route

**Status:** NEW in 2.7 (ANSTRAT-1640)
**Module:** `ansible.platform.ui_plugin_route`

---

## Summary

The `ui_plugin_route` module is **NEW in 2.7**. It manages UI plugin routing for extending the web interface. No migration needed from 2.6 (module did not exist).

This module handles registering UI plugin routes that extend the platform's web interface.

---

## 1. Module Arguments

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `name` | str | **yes** | — | Route name (unique) |
| `plugin_name` | str | **yes** | — | Plugin identifier |
| `route` | str | no | — | URL path for the route |
| `description` | str | no | — | Route description |
| `state` | str | no | `present` (default), `absent`, `exists` | Desired state |

---

## 2. Result Structure

### After (2.7.x) — nested under `ui_plugin_route` key

```json
{
    "changed": true,
    "ui_plugin_route": {
        "id": 4,
        "name": "custom_analytics",
        "plugin_name": "analytics-plugin",
        "route": "/analytics",
        "description": "Custom analytics UI plugin",
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
| `plugin_name` | str | Plugin identifier |
| `route` | str | URL path for the route |
| `description` | str | Route description |
| `created` | str | ISO 8601 timestamp when record was created |
| `modified` | str | ISO 8601 timestamp of last modification |

---

## 3. Examples

```yaml
# Register a UI plugin route
- name: Register UI plugin route
  ansible.platform.ui_plugin_route:
    name: "custom_analytics"
    plugin_name: "analytics-plugin"
    route: "/analytics"
    description: "Custom analytics UI plugin"
    state: present

# Register multiple plugin routes
- name: Register multiple UI plugin routes
  ansible.platform.ui_plugin_route:
    name: "{{ item.name }}"
    plugin_name: "{{ item.plugin_name }}"
    route: "{{ item.route }}"
    state: present
  loop:
    - name: "custom_analytics"
      plugin_name: "analytics-plugin"
      route: "/analytics"
    - name: "custom_reporting"
      plugin_name: "reporting-plugin"
      route: "/reporting"

# Remove a UI plugin route
- name: Remove plugin route
  ansible.platform.ui_plugin_route:
    name: "custom_analytics"
    state: absent
```

---

## 4. Notes

- **New in 2.7:** This module did not exist in 2.6
- **No migration needed:** New functionality only
- **Plugin extensibility:** UI plugins extend the web interface
- **Route mapping:** Maps plugin routes to web URLs
- **Path patterns:** Routes should be unique and follow platform conventions
- **Plugin discovery:** Plugin must be available/registered before route can be created

---

## 5. First-use Checklist

- [ ] Ensure UI plugins are installed in the platform
- [ ] Determine appropriate URL paths for each plugin
- [ ] Register routes for enabled plugins
- [ ] Test plugin access via web interface
- [ ] Document custom UI plugins for team reference
- [ ] Check result at `result.ui_plugin_route.*` (nested key structure)
