# Module: ansible.platform.service_type

Configure a gateway service type.

## Note: Module is new in 2.7.x

This module did not exist in 2.5.x. No migration needed — use directly in new playbooks.

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | str | yes | Service type name (must be unique) |
| `new_name` | str | no | Rename the service type |
| `ping_url` | str | no | Ping/status API path for service type |
| `login_path` | str | no | API path to login for the service type |
| `logout_path` | str | no | API path to logout for the service type |
| `service_index_path` | str | no | API path to resource service index endpoint |
| `state` | str | no | Desired state: `present` (default), `absent`, or `exists` |

## Result structure

### Example result (2.7.x)

```json
{
    "changed": true,
    "service_type": {
        "id": 1,
        "name": "eda",
        "ping_url": "/api/eda/v1/status/",
        "login_path": "/v1/auth/session/login/",
        "logout_path": "/v1/auth/session/logout/",
        "service_index_path": "/service-index/",
        "created_at": "2025-01-15T10:30:00Z",
        "modified_at": "2025-01-15T10:30:00Z"
    },
    "elapsed_ms": 123,
    "api_version": "1"
}
```

## State: present — create example

```yaml
- name: Add service type
  ansible.platform.service_type:
    name: eda
    ping_url: /api/eda/v1/status/
    login_path: /v1/auth/session/login/
    logout_path: /v1/auth/session/logout/
    service_index_path: /service-index/
    state: present
  register: result

# result.service_type.id = 1
```

## State: absent — delete example

```yaml
- name: Delete service type
  ansible.platform.service_type:
    name: eda
    state: absent
  register: result

# result.changed = true
```

## State: exists — check example

```yaml
- name: Check if service type exists
  ansible.platform.service_type:
    name: eda
    state: exists
  register: result

# result:
# {
#   "changed": false,
#   "service_type": {
#     "id": 1,
#     "name": "eda",
#     "ping_url": "/api/eda/v1/status/"
#   }
# }
```

## Full example playbook

```yaml
---
- name: Configure service types
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Add EDA service type
      ansible.platform.service_type:
        name: eda
        ping_url: /api/eda/v1/status/
        login_path: /v1/auth/session/login/
        logout_path: /v1/auth/session/logout/
        service_index_path: /service-index/
        state: present
      register: eda_type

    - name: Add Controller service type
      ansible.platform.service_type:
        name: controller
        ping_url: /api/v2/config/
        login_path: /api/v2/authtoken/
        logout_path: /api/v2/users/me/
        service_index_path: /api/v2/
        state: present
      register: controller_type

    - name: Add Hub service type
      ansible.platform.service_type:
        name: hub
        ping_url: /api/v3/_ui/v1/
        login_path: /api/galaxy/v3/auth/token/
        logout_path: /api/galaxy/v3/auth/logout/
        service_index_path: /api/v3/
        state: present
      register: hub_type

    - name: Print service type IDs
      debug:
        msg:
          - "EDA Type ID: {{ eda_type.service_type.id }}"
          - "Controller Type ID: {{ controller_type.service_type.id }}"
          - "Hub Type ID: {{ hub_type.service_type.id }}"
```

## Common patterns

### Setup standard service types

```yaml
- name: Create standard service types
  ansible.platform.service_type:
    name: "{{ item.name }}"
    ping_url: "{{ item.ping_url }}"
    login_path: "{{ item.login_path }}"
    logout_path: "{{ item.logout_path }}"
    service_index_path: "{{ item.service_index_path }}"
    state: present
  loop:
    - name: "eda"
      ping_url: "/api/eda/v1/status/"
      login_path: "/v1/auth/session/login/"
      logout_path: "/v1/auth/session/logout/"
      service_index_path: "/service-index/"
    - name: "controller"
      ping_url: "/api/v2/config/"
      login_path: "/api/v2/authtoken/"
      logout_path: "/api/v2/users/me/"
      service_index_path: "/api/v2/"
    - name: "hub"
      ping_url: "/api/v3/_ui/v1/"
      login_path: "/api/galaxy/v3/auth/token/"
      logout_path: "/api/galaxy/v3/auth/logout/"
      service_index_path: "/api/v3/"
  register: type_results
```

### Create custom service type

```yaml
- name: Add custom service type
  ansible.platform.service_type:
    name: "custom-api"
    ping_url: "/api/custom/health/"
    login_path: "/api/custom/auth/login/"
    logout_path: "/api/custom/auth/logout/"
    service_index_path: "/api/custom/v1/"
    state: present
```

### Update service type paths

```yaml
- name: Check if service type exists
  ansible.platform.service_type:
    name: "custom-service"
    state: exists
  register: service_type_check

- name: Update service type with new paths
  ansible.platform.service_type:
    name: "custom-service"
    ping_url: "/api/custom/v2/health/"
    service_index_path: "/api/custom/v2/"
    state: present
  when: service_type_check.service_type.ping_url != "/api/custom/v2/health/"
```

### Cleanup old service types

```yaml
- name: Remove deprecated service types
  ansible.platform.service_type:
    name: "{{ item }}"
    state: absent
  loop:
    - "legacy-service"
    - "deprecated-api"
    - "old-version"
  ignore_errors: true                 # OK if types don't exist
```
