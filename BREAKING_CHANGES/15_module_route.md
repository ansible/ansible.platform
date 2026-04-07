# Module: ansible.platform.route

Configure a gateway custom (non-api) route.

## Note: Module is new in 2.7.x

This module did not exist in 2.5.x. No migration needed — use directly in new playbooks.

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | str | yes | Route name (must be unique) |
| `new_name` | str | no | Rename the route |
| `description` | str | no | Route description |
| `gateway_path` | str | no | Path on AAP gateway. Required when creating |
| `http_port` | str | no | HTTP port name or ID. Required when creating |
| `service_cluster` | str | no | Service cluster name or ID. Required when creating |
| `is_service_https` | bool | no | If service cluster uses HTTPS. Default: `false` |
| `enable_gateway_auth` | bool | no | Insert gateway token into request. Default: `true` |
| `enable_mtls` | bool | no | Require mutual TLS authentication. Default: `false` |
| `is_internal_route` | bool | no | Only accessible to other services |
| `service_path` | str | no | URL path on service cluster. Required when creating |
| `service_port` | int | no | Port on service cluster. Required when creating |
| `node_tags` | str | no | Comma-separated tags for traffic filtering |
| `idle_timeout_seconds` | int | no | Idle timeout for proxied connection |
| `request_timeout_seconds` | int | no | Request timeout for proxied connection |
| `state` | str | no | Desired state: `present` (default), `absent`, `exists`, or `enforced` |

## Result structure

### Example result (2.7.x)

```json
{
    "changed": true,
    "route": {
        "id": 1,
        "name": "Controller API",
        "description": "Proxy to the Controller",
        "gateway_path": "/config/controller/",
        "http_port": 1,
        "service_cluster": 10,
        "is_service_https": true,
        "enable_gateway_auth": true,
        "enable_mtls": false,
        "is_internal_route": false,
        "service_path": "/config/v1/",
        "service_port": 3000,
        "node_tags": null,
        "idle_timeout_seconds": 300,
        "request_timeout_seconds": 60,
        "created_at": "2025-01-15T10:30:00Z",
        "modified_at": "2025-01-15T10:30:00Z"
    },
}
```

## State: present — create example

```yaml
- name: Create route
  ansible.platform.route:
    name: Controller API
    description: Proxy to the Controller
    http_port: 1
    gateway_path: /config/controller/
    service_cluster: "Automation Controller"
    is_service_https: true
    service_path: /config/v1/
    service_port: 3000
    state: present
  register: result

# result.route.id = 1
```

## State: present — with mTLS example

```yaml
- name: Create route with mTLS enabled
  ansible.platform.route:
    name: EDA Event Stream
    description: EDA Event Stream with mTLS
    http_port: 1
    gateway_path: /eda/events/
    service_cluster: "Event Driven Automation"
    is_service_https: true
    enable_gateway_auth: false      # Required for mTLS
    enable_mtls: true
    service_path: /events/
    service_port: 8080
    state: present
  register: result
```

## State: absent — delete example

```yaml
- name: Delete route
  ansible.platform.route:
    name: Controller API
    state: absent
  register: result

# result.changed = true
```

## State: exists — check example

```yaml
- name: Check if route exists
  ansible.platform.route:
    name: Controller API
    state: exists
  register: result

# result:
# {
#   "changed": false,
#   "route": {
#     "id": 1,
#     "name": "Controller API",
#     "gateway_path": "/config/controller/"
#   }
# }
```

## Full example playbook

```yaml
---
- name: Configure gateway routes
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Create controller route
      ansible.platform.route:
        name: Controller API
        description: Proxy to Automation Controller
        http_port: "HTTPS Port"
        gateway_path: /controller/
        service_cluster: "Controller Cluster"
        is_service_https: true
        service_path: /api/v2/
        service_port: 443
        state: present
      register: controller_route

    - name: Create EDA route with mTLS
      ansible.platform.route:
        name: EDA Service
        description: Event Driven Automation with mTLS
        http_port: "HTTPS Port"
        gateway_path: /eda/
        service_cluster: "EDA Cluster"
        is_service_https: true
        enable_gateway_auth: false
        enable_mtls: true
        service_path: /api/eda/v1/
        service_port: 8443
        state: present
      register: eda_route

    - name: Create Hub route
      ansible.platform.route:
        name: Hub API
        description: Automation Hub
        http_port: "HTTP Port"
        gateway_path: /hub/
        service_cluster: "Hub Cluster"
        is_service_https: false
        service_path: /api/v3/
        service_port: 8000
        state: present
      register: hub_route

    - name: Print route IDs
      debug:
        msg:
          - "Controller route ID: {{ controller_route.route.id }}"
          - "EDA route ID: {{ eda_route.route.id }}"
          - "Hub route ID: {{ hub_route.route.id }}"
```

## Common patterns

### Setup internal-only route

```yaml
- name: Create internal service route
  ansible.platform.route:
    name: "Internal Admin API"
    description: "Admin operations, not exposed externally"
    http_port: "Internal Port"
    gateway_path: /admin-internal/
    service_cluster: "Admin Service"
    is_service_https: true
    is_internal_route: true
    enable_gateway_auth: true
    service_path: /admin/
    service_port: 9000
    state: present
```

### Route with node-specific traffic

```yaml
- name: Create route with node tags
  ansible.platform.route:
    name: "Dedicated Worker Route"
    gateway_path: /dedicated/
    service_cluster: "Worker Cluster"
    http_port: "Port 8080"
    service_path: /api/
    service_port: 8000
    node_tags: "worker,dedicated"      # Only these tagged nodes get traffic
    state: present
```

### Setup multiple routes for different service versions

```yaml
- name: Create route to service version 1
  ansible.platform.route:
    name: "API v1 Route"
    gateway_path: /api/v1/
    http_port: "API Port"
    service_cluster: "API Cluster"
    service_path: /api/v1/
    service_port: 8000
    state: present

- name: Create route to service version 2
  ansible.platform.route:
    name: "API v2 Route"
    gateway_path: /api/v2/
    http_port: "API Port"
    service_cluster: "API Cluster"
    service_path: /api/v2/
    service_port: 8000
    state: present
```

### Validate mutual TLS constraint

```yaml
- name: Create route with constraint check
  block:
    - name: Ensure mTLS and gateway auth are mutually exclusive
      assert:
        that:
          - not (enable_mtls and enable_gateway_auth)
        fail_msg: "mTLS requires gateway auth to be disabled"

    - name: Create mTLS route
      ansible.platform.route:
        name: "mTLS Service"
        gateway_path: /mtls/
        http_port: "HTTPS Port"
        service_cluster: "mTLS Cluster"
        enable_gateway_auth: false
        enable_mtls: true
        service_path: /
        service_port: 443
        state: present
```
