# Module: ansible.platform.ui_plugin_route

Configure a gateway UI plugin route.

## Note: Module is new in 2.7.x

This module did not exist in 2.5.x. No migration needed — use directly in new playbooks.

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | str | yes | UI plugin route name (must be unique) |
| `new_name` | str | no | Rename the UI plugin route |
| `description` | str | no | Route description |
| `ui_plugin_path` | str | no | Relative path to UI plugin on service cluster. Required when creating |
| `http_port` | str | no | HTTP port name or ID. Required when creating |
| `service_cluster` | str | no | Service cluster name or ID. Required when creating. Cannot be Gateway type |
| `is_service_https` | bool | no | If service cluster uses HTTPS. Default: `false` |
| `service_port` | int | no | Port on service cluster. Required when creating |
| `node_tags` | str | no | Comma-separated tags for traffic filtering |
| `order` | int | no | Route precedence (lower first). Defaults to 50 when created |
| `idle_timeout_seconds` | int | no | Idle timeout for proxied connection |
| `request_timeout_seconds` | int | no | Request timeout for proxied connection |
| `state` | str | no | Desired state: `present` (default), `absent`, `exists`, or `enforced` |

## Read-only fields (auto-generated)

These fields are computed and cannot be set:
- `gateway_path` — auto-generated as `/plugin/{cluster_name}/{ui_plugin_path}/`
- `service_path` — automatically matches `ui_plugin_path`
- `enable_gateway_auth` — always `false` for UI plugins
- `is_internal_route` — always `false` for UI plugins

## Result structure

### Example result (2.7.x)

```json
{
    "changed": true,
    "ui_plugin_route": {
        "id": 1,
        "name": "EDA Dashboard Plugin",
        "description": "Route to EDA dashboard plugin",
        "gateway_path": "/plugin/eda-cluster/dashboard/",
        "ui_plugin_path": "dashboard",
        "http_port": 2,
        "service_cluster": 5,
        "is_service_https": false,
        "enable_gateway_auth": false,
        "is_internal_route": false,
        "service_path": "dashboard",
        "service_port": 8080,
        "node_tags": null,
        "order": 50,
        "idle_timeout_seconds": 300,
        "request_timeout_seconds": 60,
        "created_at": "2025-01-15T10:30:00Z",
        "modified_at": "2025-01-15T10:30:00Z"
    },
}
```

## State: present — create example

```yaml
- name: Create UI plugin route
  ansible.platform.ui_plugin_route:
    name: EDA Dashboard Plugin
    description: Route to EDA dashboard plugin
    ui_plugin_path: "dashboard"
    http_port: "Port 8080"
    service_cluster: "EDA Cluster"
    is_service_https: false
    service_port: 8080
    order: 50
    state: present
  register: result

# result.ui_plugin_route.id = 1
# result.ui_plugin_route.gateway_path = "/plugin/eda-cluster/dashboard/"
```

## State: present — with node tags example

```yaml
- name: Create UI plugin route with node tags
  ansible.platform.ui_plugin_route:
    name: Hub Plugin Route
    ui_plugin_path: "my-plugin"
    http_port: "HTTPS Port"
    service_cluster: "Automation Hub"
    is_service_https: true
    service_port: 8000
    node_tags: "frontend,plugin"
    order: 40
    state: present
  register: result
```

## State: absent — delete example

```yaml
- name: Delete UI plugin route
  ansible.platform.ui_plugin_route:
    name: EDA Dashboard Plugin
    state: absent
  register: result

# result.changed = true
```

## State: exists — check example

```yaml
- name: Check UI plugin route exists
  ansible.platform.ui_plugin_route:
    name: EDA Dashboard Plugin
    state: exists
  register: result

# result:
# {
#   "changed": false,
#   "ui_plugin_route": {
#     "id": 1,
#     "name": "EDA Dashboard Plugin",
#     "gateway_path": "/plugin/eda-cluster/dashboard/"
#   }
# }
```

## State: enforced — example

```yaml
- name: Ensure UI plugin route has exact configuration
  ansible.platform.ui_plugin_route:
    name: EDA Dashboard Plugin
    service_port: 8081
    order: 50
    state: enforced
  register: result
```

## Full example playbook

```yaml
---
- name: Configure UI plugin routes
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Create EDA dashboard plugin route
      ansible.platform.ui_plugin_route:
        name: EDA Dashboard Plugin
        description: Route to EDA dashboard UI plugin
        ui_plugin_path: "dashboard"
        http_port: "HTTPS Port"
        service_cluster: "EDA Cluster"
        is_service_https: true
        service_port: 8080
        order: 10
        state: present
      register: eda_plugin

    - name: Create Hub analytics plugin route
      ansible.platform.ui_plugin_route:
        name: Hub Analytics Plugin
        description: Route to Hub analytics UI plugin
        ui_plugin_path: "analytics"
        http_port: "HTTPS Port"
        service_cluster: "Automation Hub"
        is_service_https: true
        service_port: 8000
        order: 20
        state: present
      register: hub_analytics

    - name: Create Controller extensions plugin route
      ansible.platform.ui_plugin_route:
        name: Controller Extensions Plugin
        description: Route to Controller extensions
        ui_plugin_path: "extensions"
        http_port: "HTTPS Port"
        service_cluster: "Automation Controller"
        is_service_https: true
        service_port: 443
        node_tags: "frontend"
        order: 30
        state: present
      register: controller_extensions

    - name: Print plugin route gateway paths
      debug:
        msg:
          - "EDA Dashboard: {{ eda_plugin.ui_plugin_route.gateway_path }}"
          - "Hub Analytics: {{ hub_analytics.ui_plugin_route.gateway_path }}"
          - "Controller Extensions: {{ controller_extensions.ui_plugin_route.gateway_path }}"
```

## Common patterns

### Create multiple UI plugin routes with automatic path generation

```yaml
- name: Create multiple UI plugin routes
  ansible.platform.ui_plugin_route:
    name: "{{ item.name }}"
    description: "{{ item.description }}"
    ui_plugin_path: "{{ item.path }}"
    http_port: "HTTPS Port"
    service_cluster: "{{ item.cluster }}"
    is_service_https: true
    service_port: 8080
    order: "{{ item.order }}"
    state: present
  loop:
    - name: "EDA Dashboard"
      description: "EDA dashboard UI"
      path: "dashboard"
      cluster: "EDA Cluster"
      order: 10
    - name: "Hub Marketplace"
      description: "Hub marketplace UI"
      path: "marketplace"
      cluster: "Automation Hub"
      order: 20
    - name: "Controller Admin"
      description: "Controller administration UI"
      path: "admin"
      cluster: "Automation Controller"
      order: 30
  register: plugin_routes
```

### Plugin route with node-specific routing

```yaml
- name: Create high-availability plugin route
  ansible.platform.ui_plugin_route:
    name: "HA Dashboard Plugin"
    ui_plugin_path: "dashboard"
    http_port: "Load Balancer Port"
    service_cluster: "Multi-Zone Cluster"
    is_service_https: true
    service_port: 8080
    node_tags: "dashboard-frontend"      # Route to specific tagged nodes
    idle_timeout_seconds: 600
    request_timeout_seconds: 120
    state: present
```

### Update plugin route order for display priority

```yaml
- name: Check plugin route order
  ansible.platform.ui_plugin_route:
    name: "EDA Dashboard Plugin"
    state: exists
  register: plugin_check

- name: Reorder plugin routes by priority
  ansible.platform.ui_plugin_route:
    name: "{{ item.name }}"
    order: "{{ item.order }}"
    state: present
  loop:
    - name: "Critical Dashboard"
      order: 1
    - name: "Important Tools"
      order: 10
    - name: "Optional Features"
      order: 100
```

### Cleanup old plugin routes

```yaml
- name: Remove deprecated plugin routes
  ansible.platform.ui_plugin_route:
    name: "{{ item }}"
    state: absent
  loop:
    - "Legacy Dashboard Plugin"
    - "Deprecated Analytics UI"
    - "Old Configuration Plugin"
  ignore_errors: true                 # OK if routes don't exist
```

### Verify gateway paths are correctly auto-generated

```yaml
- name: Verify plugin route gateway paths
  block:
    - name: Check EDA plugin path
      ansible.platform.ui_plugin_route:
        name: "EDA Dashboard"
        state: exists
      register: eda_route

    - name: Assert gateway path is auto-generated correctly
      assert:
        that:
          - eda_route.ui_plugin_route.gateway_path == "/plugin/eda-cluster/dashboard/"
          - eda_route.ui_plugin_route.enable_gateway_auth == false
          - eda_route.ui_plugin_route.is_internal_route == false
        fail_msg: "Plugin route auto-generated fields are incorrect"
```
