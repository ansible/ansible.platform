# Module: ansible.platform.http_port

Configure gateway HTTP ports where Envoy proxy listens.

## Note: Module is new in 2.7.x

This module did not exist in 2.5.x. No migration needed — use directly in new playbooks.

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | str | yes | The name of the HTTP port (must be unique) |
| `new_name` | str | no | Rename the port by changing the existing name |
| `number` | int | no | Port number (must be unique). Required when creating |
| `use_https` | bool | no | Secure this port with HTTPS. Default: `false` |
| `is_api_port` | bool | no | If true, port is used for serving remote AAP APIs. Only one can be true. Default: `false` |
| `state` | str | no | Desired state: `present` (default), `absent`, or `exists` |

## Result structure

### Example result (2.7.x)

```json
{
    "changed": true,
    "http_port": {
        "id": 1,
        "name": "Port for APIs",
        "number": 443,
        "use_https": true,
        "is_api_port": true,
        "created_at": "2025-01-15T10:30:00Z",
        "modified_at": "2025-01-15T10:30:00Z"
    },
    "elapsed_ms": 189,
    "api_version": "1"
}
```

## State: present — create example

```yaml
- name: Add API HTTP port
  ansible.platform.http_port:
    name: "Port for APIs"
    number: 443
    use_https: true
    is_api_port: true
    state: present
  register: result

# result.http_port.id = 1
```

## State: present — update example

```yaml
- name: Update HTTP port
  ansible.platform.http_port:
    name: "Port for APIs"
    number: 8443
    use_https: true
    state: present
  register: result
```

## State: absent — delete example

```yaml
- name: Remove HTTP port
  ansible.platform.http_port:
    name: "Port for APIs"
    state: absent
  register: result

# result.changed = true
```

## State: exists — check example

```yaml
- name: Check if port exists
  ansible.platform.http_port:
    name: "Port for APIs"
    state: exists
  register: result

# result:
# {
#   "changed": false,
#   "http_port": {
#     "id": 1,
#     "name": "Port for APIs",
#     "number": 443,
#     "use_https": true,
#     "is_api_port": true
#   }
# }
```

## Full example playbook

```yaml
---
- name: Configure HTTP ports
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Add standard HTTP port
      ansible.platform.http_port:
        name: "HTTP Port"
        number: 80
        use_https: false
        state: present
      register: http_result

    - name: Add secure HTTPS port for APIs
      ansible.platform.http_port:
        name: "HTTPS API Port"
        number: 443
        use_https: true
        is_api_port: true
        state: present
      register: https_api_result

    - name: Add custom service port
      ansible.platform.http_port:
        name: "Service Port"
        number: 8080
        use_https: false
        state: present
      register: service_result

    - name: Print configured ports
      debug:
        msg:
          - "HTTP Port ID: {{ http_result.http_port.id }}"
          - "HTTPS API Port ID: {{ https_api_result.http_port.id }}"
          - "Service Port ID: {{ service_result.http_port.id }}"

    - name: Update port configuration
      ansible.platform.http_port:
        name: "HTTP Port"
        number: 8000
        use_https: false
        state: present

    - name: Rename port
      ansible.platform.http_port:
        name: "Service Port"
        new_name: "Custom Service Port"
        state: present
```

## Common patterns

### Setup multi-port gateway

```yaml
- name: Setup gateway with multiple ports
  block:
    - name: Create HTTP port
      ansible.platform.http_port:
        name: "{{ item.name }}"
        number: "{{ item.number }}"
        use_https: "{{ item.https }}"
        is_api_port: "{{ item.is_api | default(false) }}"
        state: present
      loop:
        - name: "HTTP"
          number: 80
          https: false
        - name: "HTTPS"
          number: 443
          https: true
        - name: "API"
          number: 8443
          https: true
          is_api: true
      register: port_results

    - name: Store port IDs for routing
      set_fact:
        http_port_id: "{{ port_results.results[0].http_port.id }}"
        https_port_id: "{{ port_results.results[1].http_port.id }}"
        api_port_id: "{{ port_results.results[2].http_port.id }}"
```

### Conditional port creation based on environment

```yaml
- name: Setup ports based on environment
  ansible.platform.http_port:
    name: "{{ item.name }}"
    number: "{{ item.number }}"
    use_https: "{{ item.https }}"
    state: present
  loop:
    - name: "HTTP"
      number: 80
      https: false
    - name: "HTTPS"
      number: 443
      https: true
    - name: "Dev Debug Port"
      number: 9000
      https: false
  when: environment == 'development' or item.https

- name: Only HTTPS in production
  ansible.platform.http_port:
    name: "{{ item.name }}"
    number: "{{ item.number }}"
    use_https: true
    state: present
  loop:
    - name: "HTTPS"
      number: 443
    - name: "HTTPS API"
      number: 8443
  when: environment == 'production'
```

### Port lifecycle management

```yaml
- name: Check if port exists before creation
  ansible.platform.http_port:
    name: "Service Port"
    state: exists
  register: port_check

- name: Create port only if not exists
  ansible.platform.http_port:
    name: "Service Port"
    number: 8080
    use_https: false
    state: present
  when: not port_check.http_port

- name: Cleanup unused ports
  ansible.platform.http_port:
    name: "{{ item }}"
    state: absent
  loop:
    - "Old Debug Port"
    - "Deprecated Service Port"
  ignore_errors: true  # OK if ports don't exist
```
