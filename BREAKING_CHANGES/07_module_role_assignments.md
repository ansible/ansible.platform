# Modules: ansible.platform.role_user_assignment and role_team_assignment

## Arguments — full comparison tables

### role_user_assignment

| Argument | Type | Required | Old (2.5.x) | New (2.7.x) | Notes |
|----------|------|----------|-------------|-------------|-------|
| `role_definition` | str | yes | ✓ same | ✓ same | Role definition name or ID |
| `user` | str | yes | ✓ same | ✓ same | User name or ID |
| `object_id` | str | no | ✓ same | ✓ same | ID of object (org, team, etc.) to scope role to |
| `object_ids` | list | no | N/A | ✓ new in 2.7 | List of object IDs for multi-object assignment |
| `state` | str | no | present/absent | present/absent | |
| `gateway_hostname` | str | no | ✓ old credential | deprecated | Use `gateway_url` instead |
| `gateway_url` | str | no | N/A | ✓ new credential | Replaces `gateway_hostname` |

### role_team_assignment

| Argument | Type | Required | Old (2.5.x) | New (2.7.x) | Notes |
|----------|------|----------|-------------|-------------|-------|
| `role_definition` | str | yes | ✓ same | ✓ same | Role definition name or ID |
| `team` | str | yes | ✓ same | ✓ same | Team name or ID |
| `object_id` | str | no | ✓ same | ✓ same | ID of object (org, team, etc.) to scope role to |
| `object_ids` | list | no | N/A | ✓ new in 2.7 | List of object IDs for multi-object assignment |
| `state` | str | no | present/absent | present/absent | |
| `gateway_hostname` | str | no | ✓ old credential | deprecated | Use `gateway_url` instead |
| `gateway_url` | str | no | N/A | ✓ new credential | Replaces `gateway_hostname` |

## Result structure — breaking change

---

## role_user_assignment

### Before (2.5.x)

**Sample result:**
```json
{
    "changed": true,
    "id": 301
}
```

```yaml
- name: Assign Platform Auditor role to user
  ansible.platform.role_user_assignment:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    role_definition: "Platform Auditor"
    user: jdoe
    state: present
  register: assignment

- debug:
    msg: "Assignment ID: {{ assignment.id }}"   # top-level
```

---

### After (2.7.x)

**Sample result (single assignment):**
```json
{
    "changed": true,
    "role_user_assignment": {
        "id": 301,
        "role_definition": "Platform Auditor",
        "user": "jdoe",
        "object_id": null,
        "content_type": null
    },
}
```

```yaml
- name: Assign Platform Auditor role to user
  ansible.platform.role_user_assignment:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    role_definition: "Platform Auditor"
    user: jdoe
    state: present
  register: assignment

- debug:
    msg: "Assignment ID: {{ assignment.role_user_assignment.id }}"   # nested
```

---

### Multi-object assignment (new in 2.7.x)

```yaml
- name: Assign role to user for multiple objects
  ansible.platform.role_user_assignment:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    role_definition: "Organization Member"
    user: jdoe
    object_ids:
      - 7
      - 8
      - 9
    state: present
  register: assignment
```

**Sample result (multi-object):**
```json
{
    "changed": true,
    "role_user_assignment": {
        "assignments": [
            { "id": 301, "role_definition": "Organization Member", "user": "jdoe", "object_id": 7 },
            { "id": 302, "role_definition": "Organization Member", "user": "jdoe", "object_id": 8 },
            { "id": 303, "role_definition": "Organization Member", "user": "jdoe", "object_id": 9 }
        ]
    },
}
```

---

## role_team_assignment

### Before (2.5.x)

**Sample result:**
```json
{
    "changed": true,
    "id": 415
}
```

```yaml
- name: Assign role to team
  ansible.platform.role_team_assignment:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    role_definition: "Organization Member"
    team: "Backend Team"
    object_id: 7
    state: present
  register: assignment

- debug:
    msg: "Assignment ID: {{ assignment.id }}"
```

---

### After (2.7.x)

**Sample result:**
```json
{
    "changed": true,
    "role_team_assignment": {
        "id": 415,
        "role_definition": "Organization Member",
        "team": "Backend Team",
        "object_id": 7,
        "content_type": "organization"
    },
}
```

```yaml
- name: Assign role to team
  ansible.platform.role_team_assignment:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    role_definition: "Organization Member"
    team: "Backend Team"
    object_id: 7
    state: present
  register: assignment

- debug:
    msg: "Assignment ID: {{ assignment.role_team_assignment.id }}"  # nested
```

---

## Full example playbook — before and after

### Before (2.5.x)
```yaml
---
- name: Role assignment setup
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:
    - name: Create user
      ansible.platform.user:
        gateway_hostname: https://gateway.example.com
        gateway_username: admin
        gateway_password: "{{ vault_pw }}"
        username: jdoe
        email: jdoe@example.com
        state: present
      register: user_result

    - name: Create org
      ansible.platform.organization:
        gateway_hostname: https://gateway.example.com
        gateway_username: admin
        gateway_password: "{{ vault_pw }}"
        name: Engineering
        state: present
      register: org_result

    - name: Assign user to org
      ansible.platform.role_user_assignment:
        gateway_hostname: https://gateway.example.com
        gateway_username: admin
        gateway_password: "{{ vault_pw }}"
        role_definition: "Organization Member"
        user: "{{ user_result.id }}"        # top-level
        object_id: "{{ org_result.id }}"    # top-level
        state: present
```

### After (2.7.x)
```yaml
---
- name: Role assignment setup
  hosts: localhost
  connection: local
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Create user
      ansible.platform.user:
        username: jdoe
        email: jdoe@example.com
        state: present
      register: user_result

    - name: Create org
      ansible.platform.organization:
        name: Engineering
        state: present
      register: org_result

    - name: Assign user to org
      ansible.platform.role_user_assignment:
        role_definition: "Organization Member"
        user: "{{ user_result.user.id }}"            # nested
        object_id: "{{ org_result.organization.id }}" # nested
        state: present
```
