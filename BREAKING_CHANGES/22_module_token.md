# Module: ansible.platform.token

Create, update, or destroy automation platform gateway tokens.

## Note: Token management structure changed in 2.7.x

This module existed in 2.5.x but return structure is significantly enhanced in 2.7.x.

## Arguments — mostly unchanged

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `description` | str | no | Optional description of the access token |
| `application` | str | no | Application name, ID, or named URL tied to token |
| `organization` | str | no | Organization name, ID, or URL (used for lookup, cannot be modified) |
| `scope` | str | no | Scope: `read` or `write`. Default: `write` |
| `existing_token` | dict | no | Token dict from create mode (used with state absent) |
| `existing_token_id` | str | no | Token ID number (used with state absent) |
| `state` | str | no | Desired state: `present` (default) or `absent` |

## Result structure

### Before (2.5.x) — incomplete return

```json
{
    "changed": true,
    "id": 42
}
```

Old playbooks had to use the result ID with a subsequent lookup call to get full token data.

### After (2.7.x) — full token object

```json
{
    "changed": true,
    "ansible_facts": {
        "aap_token": {
            "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            "id": "42",
            "description": "My API token",
            "scope": "write",
            "application": 10,
            "created_at": "2025-01-15T10:30:00Z",
            "modified_at": "2025-01-15T10:30:00Z"
        }
    },
    "elapsed_ms": 189,
    "api_version": "1"
}
```

## State: present — before/after example

### Before (2.5.x)

```yaml
- name: Create token for use in other modules
  ansible.platform.token:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    description: "Temporary token for deployment"
    scope: "write"
    state: present
  register: token_result

# token_result:
# {
#   "changed": true,
#   "id": 42
# }

- name: Use token in subsequent task
  ansible.platform.user:
    gateway_hostname: https://gateway.example.com
    aap_token: "{{ token_result }}"  # Had to reference entire dict
    username: newuser
    state: present
```

### After (2.7.x)

```yaml
- name: Create token for use in other modules
  ansible.platform.token:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    description: "Temporary token for deployment"
    scope: "write"
    state: present
  register: token_result

# token_result.ansible_facts.aap_token contains:
# {
#   "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "id": "42",
#   "description": "Temporary token for deployment",
#   "scope": "write"
# }

- name: Use token in subsequent task
  ansible.platform.user:
    gateway_url: https://gateway.example.com
    aap_token: "{{ aap_token }}"      # Automatically set as fact
    username: newuser
    state: present
```

## State: absent — delete example

```yaml
- name: Delete token by existing_token reference
  ansible.platform.token:
    existing_token: "{{ aap_token }}"
    state: absent

- name: Delete token by ID
  ansible.platform.token:
    existing_token_id: 42
    state: absent
```

## Full example playbook — before and after

### Before (2.5.x)

```yaml
---
- name: Token lifecycle with old style
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:
    - name: Create a temporary token
      ansible.platform.token:
        gateway_hostname: https://gateway.example.com
        gateway_username: admin
        gateway_password: "{{ vault_pw }}"
        description: "Temporary deployment token"
        scope: "write"
        state: present
      register: token_result

    - name: Use the token
      ansible.platform.user:
        gateway_hostname: https://gateway.example.com
        aap_token: "{{ token_result }}"
        username: jdoe
        email: jdoe@example.com
        state: present
      register: user_result

    - name: Clean up token
      ansible.platform.token:
        gateway_hostname: https://gateway.example.com
        aap_token: "{{ token_result }}"
        existing_token: "{{ token_result }}"
        state: absent
```

### After (2.7.x)

```yaml
---
- name: Token lifecycle with new style
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Create a temporary token
      ansible.platform.token:
        description: "Temporary deployment token"
        scope: "write"
        state: present
      register: token_result

    # aap_token is automatically set as Ansible fact from ansible_facts
    - name: Use the token
      ansible.platform.user:
        username: jdoe
        email: jdoe@example.com
        state: present
      register: user_result

    - name: Clean up token
      ansible.platform.token:
        existing_token: "{{ aap_token }}"
        state: absent
```

## Common patterns

### Create temporary token for scripted operations

```yaml
- name: Perform operations with temporary token
  block:
    - name: Create short-lived token
      ansible.platform.token:
        description: "Script execution token"
        scope: "write"
        state: present
      register: temp_token

    - name: Execute multiple tasks with token
      ansible.platform.user:
        username: "{{ item }}"
        email: "{{ item }}@example.com"
        state: present
      loop:
        - user1
        - user2
        - user3

  always:
    - name: Delete temporary token
      ansible.platform.token:
        existing_token: "{{ aap_token }}"
        state: absent
      when: aap_token is defined
```

### Create application-scoped token

```yaml
- name: Create token for specific application
  ansible.platform.token:
    description: "Controller integration token"
    application: "Automation Controller"
    scope: "read"
    state: present
  register: app_token

- name: Store token for later use
  copy:
    content: "{{ aap_token.token }}\n"
    dest: "/etc/aap/controller.token"
    mode: '0600'
  no_log: true
```

### Token rotation

```yaml
- name: Rotate API token
  block:
    - name: Store old token ID
      set_fact:
        old_token_id: "{{ existing_token_id }}"

    - name: Create new token
      ansible.platform.token:
        description: "API token (rotated)"
        scope: "write"
        state: present
      register: new_token

    - name: Update configuration with new token
      debug:
        msg: "New token available: {{ aap_token.id }}"

    - name: Delete old token after grace period
      ansible.platform.token:
        existing_token_id: "{{ old_token_id }}"
        state: absent
      when: old_token_id is defined
```

### Create read-only token for monitoring

```yaml
- name: Create monitoring token with read-only scope
  ansible.platform.token:
    description: "Monitoring and metrics collection"
    scope: "read"
    state: present
  register: monitoring_token

- name: Save token for monitoring system
  copy:
    content: |
      GATEWAY_TOKEN={{ aap_token.token }}
      GATEWAY_URL=https://gateway.example.com
    dest: "/etc/monitoring/gateway.env"
    mode: '0600'
  no_log: true
```
