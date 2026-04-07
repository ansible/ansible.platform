# Module: ansible.platform.service_key

Configure a gateway service key.

## Note: Module is new in 2.7.x

This module did not exist in 2.5.x. No migration needed — use directly in new playbooks.

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | str | yes | Service key name (must be unique) |
| `new_name` | str | no | Rename the service key |
| `is_active` | bool | no | Set the active state of the service key. Default: `true` |
| `service_cluster` | str | no | Service cluster name or ID |
| `algorithm` | str | no | Algorithm to use: HS256, HS384, or HS512 |
| `secret` | str | no | Secret key (required when creating, non-editable) |
| `secret_length` | int | no | Number of random bytes in the secret |
| `mark_previous_inactive` | bool | no | Deactivate other keys for this service when activating this one |
| `state` | str | no | Desired state: `present` (default), `absent`, or `exists` |

## Result structure

### Example result (2.7.x)

```json
{
    "changed": true,
    "service_key": {
        "id": 1,
        "name": "Automation Controller Service Key",
        "is_active": true,
        "service_cluster": 10,
        "algorithm": "HS256",
        "secret": "my_secret_key",
        "secret_length": 32,
        "created_at": "2025-01-15T10:30:00Z",
        "modified_at": "2025-01-15T10:30:00Z"
    },
}
```

## State: present — create example

```yaml
- name: Add service key
  ansible.platform.service_key:
    name: Automation Controller Service Key
    is_active: true
    service_cluster: Automation Controller
    algorithm: HS256
    secret: mysecret
    secret_length: 32
    state: present
  register: result

# result.service_key.id = 1
```

## State: present — rotate key example

```yaml
- name: Create new controller service key
  ansible.platform.service_key:
    name: Automation Controller Service Key
    new_name: New Automation Controller Service Key
    is_active: true
    service_cluster: Automation Controller
    algorithm: HS256
    secret: mysecret1
    secret_length: 32
    mark_previous_inactive: true      # Deactivate old keys
    state: present
  register: result
```

## State: absent — delete example

```yaml
- name: Delete service key
  ansible.platform.service_key:
    name: Old Service Key
    state: absent
  register: result

# result.changed = true
```

## State: exists — check example

```yaml
- name: Check if service key exists
  ansible.platform.service_key:
    name: Automation Controller Service Key
    state: exists
  register: result

# result:
# {
#   "changed": false,
#   "service_key": {
#     "id": 1,
#     "name": "Automation Controller Service Key",
#     "is_active": true
#   }
# }
```

## Full example playbook

```yaml
---
- name: Configure service keys
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Create controller service key
      ansible.platform.service_key:
        name: Controller Key
        is_active: true
        service_cluster: Automation Controller
        algorithm: HS256
        secret: "{{ controller_secret }}"
        secret_length: 32
        state: present
      register: controller_key

    - name: Create EDA service key
      ansible.platform.service_key:
        name: EDA Key
        is_active: true
        service_cluster: Event Driven Automation
        algorithm: HS256
        secret: "{{ eda_secret }}"
        secret_length: 32
        state: present
      register: eda_key

    - name: Create Hub service key
      ansible.platform.service_key:
        name: Hub Key
        is_active: true
        service_cluster: Automation Hub
        algorithm: HS512
        secret: "{{ hub_secret }}"
        secret_length: 64
        state: present
      register: hub_key

    - name: Print service key IDs
      debug:
        msg:
          - "Controller Key ID: {{ controller_key.service_key.id }}"
          - "EDA Key ID: {{ eda_key.service_key.id }}"
          - "Hub Key ID: {{ hub_key.service_key.id }}"
```

## Common patterns

### Key rotation with deactivation

```yaml
- name: Rotate service key
  block:
    - name: Check current key
      ansible.platform.service_key:
        name: "Active Service Key"
        state: exists
      register: current_key

    - name: Create new key and deactivate old one
      ansible.platform.service_key:
        name: "Active Service Key"
        new_name: "{{ current_key.service_key.name }}_rotated_{{ now(utc=True).strftime('%Y%m%d_%H%M%S') }}"
        is_active: true
        service_cluster: "{{ cluster_id }}"
        algorithm: HS256
        secret: "{{ new_secret_value }}"
        secret_length: 32
        mark_previous_inactive: true    # Old key becomes inactive
        state: present
      register: new_key

    - name: Update configuration with new key
      debug:
        msg: "New key created: {{ new_key.service_key.id }}"
```

### Setup multiple keys per cluster with different algorithms

```yaml
- name: Create keys with different algorithms
  ansible.platform.service_key:
    name: "{{ item.name }}"
    is_active: "{{ item.active }}"
    service_cluster: "My Service Cluster"
    algorithm: "{{ item.algorithm }}"
    secret: "{{ item.secret }}"
    secret_length: "{{ item.length }}"
    state: present
  loop:
    - name: "Primary Key (HS256)"
      algorithm: HS256
      length: 32
      active: true
      secret: "{{ secret_256 }}"
    - name: "Secondary Key (HS512)"
      algorithm: HS512
      length: 64
      active: false
      secret: "{{ secret_512 }}"
```

### Deactivate all keys except newest

```yaml
- name: Deactivate old keys by creating new primary
  ansible.platform.service_key:
    name: "Primary Service Key"
    is_active: true
    service_cluster: "{{ cluster_name }}"
    algorithm: HS256
    secret: "{{ new_secret }}"
    secret_length: 32
    mark_previous_inactive: true      # All other keys become inactive
    state: present
```

### Key cleanup and archival

```yaml
- name: Archive old service keys
  block:
    - name: Find all keys for cluster
      ansible.platform.service_key:
        name: "{{ item }}"
        state: exists
      loop: "{{ old_key_names }}"
      register: old_keys

    - name: Deactivate archived keys
      ansible.platform.service_key:
        name: "{{ item.item }}"
        is_active: false
        state: present
      loop: "{{ old_keys.results }}"
      when: item.service_key is defined

    - name: Delete very old keys
      ansible.platform.service_key:
        name: "{{ item }}"
        state: absent
      loop: "{{ very_old_key_names }}"
      ignore_errors: true
```
