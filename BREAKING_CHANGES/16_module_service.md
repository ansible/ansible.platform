# Module: ansible.platform.service

Configure a gateway service.

## Note: Module is new in 2.7.x

This module did not exist in 2.5.x. No migration needed — use directly in new playbooks.

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | str | yes | Service name (must be unique) |
| `new_name` | str | no | Rename the service |
| `description` | str | no | Service description |
| `api_slug` | str | no | URL slug for gateway API path (for Controller, Hub, EDA). Not used for gateway routes |
| `http_port` | str | no | HTTP port name or ID. Required when creating |
| `service_cluster` | str | no | Service cluster name or ID. Required when creating |
| `is_service_https` | bool | no | If service cluster uses HTTPS. Default: `false` |
| `enable_gateway_auth` | bool | no | Insert gateway token into request. Default: `true` |
| `enable_mtls` | bool | no | Require mutual TLS authentication. Default: `false` |
| `is_internal_route` | bool | no | Only accessible to other services |
| `service_path` | str | no | URL path on service cluster. Required when creating |
| `service_port` | int | no | Port on service cluster. Required when creating |
| `node_tags` | str | no | Comma-separated tags for traffic filtering |
| `order` | int | no | Route order (lower first). Defaults to 50 when created |
| `idle_timeout_seconds` | int | no | Idle timeout for proxied connection |
| `request_timeout_seconds` | int | no | Request timeout for proxied connection |
| `state` | str | no | Desired state: `present` (default), `absent`, `exists`, or `enforced` |

## Result structure

### Example result (2.7.x)

```json
{
    "changed": true,
    "service": {
        "id": 1,
        "name": "Hub API",
        "description": "Proxy to the Automation Hub",
        "api_slug": "hub",
        "http_port": 2,
        "service_cluster": 5,
        "is_service_https": true,
        "enable_gateway_auth": true,
        "enable_mtls": false,
        "is_internal_route": false,
        "service_path": "/api/v1/",
        "service_port": 8000,
        "node_tags": null,
        "order": 100,
        "idle_timeout_seconds": 300,
        "request_timeout_seconds": 60,
        "created_at": "2025-01-15T10:30:00Z",
        "modified_at": "2025-01-15T10:30:00Z"
    },
}
```

## State: present — create example

```yaml
- name: Create service
  ansible.platform.service:
    name: Hub API
    description: Proxy to the Automation Hub
    api_slug: "hub"
    http_port: "Port 8080"
    service_cluster: "Automation Hub"
    is_service_https: true
    service_path: /api/v1/
    service_port: 8000
    order: 100
    state: present
  register: result

# result.service.id = 1
```

## State: present — update example

```yaml
- name: Update service
  ansible.platform.service:
    name: Hub API
    service_path: /api/v2/
    state: present
  register: result
```

## State: absent — delete example

```yaml
- name: Delete service
  ansible.platform.service:
    name: Gateway API
    state: absent
  register: result

# result.changed = true
```

## State: exists — check example

```yaml
- name: Check if service exists
  ansible.platform.service:
    name: Gateway API
    state: exists
  register: result

# result:
# {
#   "changed": false,
#   "service": {
#     "id": 2,
#     "name": "Gateway API",
#     "api_slug": "gateway"
#   }
# }
```

## Full example playbook

```yaml
---
- name: Configure gateway services
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Create Gateway API service
      ansible.platform.service:
        name: Gateway API
        description: Core gateway API
        api_slug: "gateway"
        http_port: "HTTPS Port"
        service_cluster: "Gateway Cluster"
        is_service_https: true
        service_path: /api/
        service_port: 8443
        order: 10
        state: present
      register: gateway_service

    - name: Create Controller service
      ansible.platform.service:
        name: Controller API
        description: Automation Controller integration
        api_slug: "controller"
        http_port: "HTTPS Port"
        service_cluster: "Controller Cluster"
        is_service_https: true
        service_path: /api/v2/
        service_port: 443
        order: 20
        state: present
      register: controller_service

    - name: Create Hub service
      ansible.platform.service:
        name: Hub API
        description: Automation Hub integration
        api_slug: "hub"
        http_port: "HTTP Port"
        service_cluster: "Hub Cluster"
        is_service_https: false
        service_path: /api/v3/
        service_port: 8000
        order: 30
        state: present
      register: hub_service

    - name: Create EDA service
      ansible.platform.service:
        name: EDA API
        description: Event Driven Automation
        api_slug: "eda"
        http_port: "HTTPS Port"
        service_cluster: "EDA Cluster"
        is_service_https: true
        service_path: /api/eda/v1/
        service_port: 8443
        order: 40
        state: present
      register: eda_service

    - name: Print service IDs
      debug:
        msg:
          - "Gateway service ID: {{ gateway_service.service.id }}"
          - "Controller service ID: {{ controller_service.service.id }}"
          - "Hub service ID: {{ hub_service.service.id }}"
          - "EDA service ID: {{ eda_service.service.id }}"
```

## Common patterns

### Create service with ordered precedence

```yaml
- name: Create services with specific order
  ansible.platform.service:
    name: "{{ item.name }}"
    description: "{{ item.description }}"
    api_slug: "{{ item.api_slug }}"
    http_port: "HTTPS Port"
    service_cluster: "{{ item.cluster }}"
    is_service_https: true
    service_path: "{{ item.path }}"
    service_port: 443
    order: "{{ item.order }}"
    state: present
  loop:
    - name: "Premium API"
      description: "High-priority API"
      api_slug: "premium"
      cluster: "Premium Cluster"
      path: "/api/premium/"
      order: 10
    - name: "Standard API"
      description: "Standard API"
      api_slug: "standard"
      cluster: "Standard Cluster"
      path: "/api/standard/"
      order: 20
    - name: "Legacy API"
      description: "Legacy support"
      api_slug: "legacy"
      cluster: "Legacy Cluster"
      path: "/api/v1/"
      order: 100
```

### Setup internal-only service

```yaml
- name: Create internal admin service
  ansible.platform.service:
    name: "Internal Admin Service"
    description: "Admin operations, internal only"
    http_port: "Internal Port"
    service_cluster: "Admin Cluster"
    is_service_https: true
    is_internal_route: true
    enable_gateway_auth: true
    service_path: /admin/
    service_port: 9000
    order: 5
    state: present
```

### Service with mTLS and node routing

```yaml
- name: Create mTLS service with node tags
  ansible.platform.service:
    name: "Secure Database Service"
    description: "Database with mutual TLS"
    http_port: "Secure Port"
    service_cluster: "DB Cluster"
    is_service_https: true
    enable_gateway_auth: false      # Required for mTLS
    enable_mtls: true
    service_path: /db/
    service_port: 5432
    node_tags: "database,secure"    # Only these nodes get traffic
    order: 15
    state: present
```

### Update service path for version migration

```yaml
- name: Check current service configuration
  ansible.platform.service:
    name: "API Service"
    state: exists
  register: current_service

- name: Update service path if version differs
  ansible.platform.service:
    name: "API Service"
    service_path: "{{ new_api_path }}"
    state: present
  when: current_service.service.service_path != new_api_path
  vars:
    new_api_path: "/api/v3/"
```
