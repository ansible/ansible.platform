# Module: ansible.platform.team

## Arguments — full comparison table

| Argument | Type | Required | Old (2.5.x) | New (2.7.x) | Notes |
|----------|------|----------|-------------|-------------|-------|
| `name` | str | yes | ✓ same | ✓ same | Must be unique within organization |
| `new_name` | str | no | ✓ same | ✓ same | Rename by setting this |
| `description` | str | no | ✓ same | ✓ same | Team description |
| `organization` | str | yes | ✓ same | ✓ same | Organization name or ID |
| `state` | str | no | present/absent/exists | present/absent/exists/enforced | `enforced` is new |
| `gateway_hostname` | str | no | ✓ old credential | deprecated | Use `gateway_url` instead |
| `gateway_url` | str | no | N/A | ✓ new credential | Replaces `gateway_hostname` |

## Result structure — breaking change

### Before (2.5.x)

**Sample result:**
```json
{
    "changed": true,
    "id": 15
}
```

```yaml
- name: Create team
  ansible.platform.team:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    name: Backend Team
    organization: Engineering
    state: present
  register: team_result

# Assign role using team id
- name: Assign role to team
  ansible.platform.role_team_assignment:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    role_definition: "Organization Member"
    team: "{{ team_result.id }}"       # top-level id
    object_id: 7
    state: present
```

---

### After (2.7.x)

**Sample result:**
```json
{
    "changed": true,
    "team": {
        "id": 15,
        "name": "Backend Team",
        "description": "",
        "organization": 7
    },
}
```

```yaml
- name: Create team
  ansible.platform.team:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    name: Backend Team
    organization: Engineering
    state: present
  register: team_result

# Assign role using team id — path changed
- name: Assign role to team
  ansible.platform.role_team_assignment:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    role_definition: "Organization Member"
    team: "{{ team_result.team.id }}"   # nested under 'team'
    object_id: 7
    state: present
```

---

## State: exists — before/after

### Before (2.5.x)
```json
{ "changed": false, "id": 15 }
```

### After (2.7.x)
```json
{
    "changed": false,
    "team": {
        "id": 15,
        "name": "Backend Team",
        "description": "",
        "organization": 7
    }
}
```

---

## Full example playbook — before and after

### Before (2.5.x)
```yaml
---
- name: Team management
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:
    - name: Create team
      ansible.platform.team:
        gateway_hostname: https://gateway.example.com
        gateway_username: admin
        gateway_password: "{{ vault_pw }}"
        name: Backend Team
        organization: Engineering
        state: present
      register: team

    - debug:
        msg: "Team ID: {{ team.id }}"

    - name: Delete team
      ansible.platform.team:
        gateway_hostname: https://gateway.example.com
        gateway_username: admin
        gateway_password: "{{ vault_pw }}"
        name: Backend Team
        organization: Engineering
        state: absent
```

### After (2.7.x)
```yaml
---
- name: Team management
  hosts: localhost
  connection: local
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Create team
      ansible.platform.team:
        name: Backend Team
        organization: Engineering
        state: present
      register: team

    - debug:
        msg: "Team ID: {{ team.team.id }}"     # changed

    - name: Delete team
      ansible.platform.team:
        name: Backend Team
        organization: Engineering
        state: absent
```
