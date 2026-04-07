# Module: ansible.platform.organization

## Arguments — full comparison table

| Argument | Type | Required | Old (2.5.x) | New (2.7.x) | Notes |
|----------|------|----------|-------------|-------------|-------|
| `name` | str | yes | ✓ same | ✓ same | Must be unique |
| `new_name` | str | no | ✓ same | ✓ same | Rename by setting this while specifying current `name` |
| `description` | str | no | ✓ same | ✓ same | Organization description |
| `state` | str | no | present/absent/exists | present/absent/exists/enforced | `enforced` is new |
| `gateway_hostname` | str | no | ✓ old credential | deprecated | Use `gateway_url` instead |
| `gateway_url` | str | no | N/A | ✓ new credential | Replaces `gateway_hostname` |

## Result structure — breaking change

### Before (2.5.x)

```yaml
- name: Create organisation
  ansible.platform.organization:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    name: Engineering
    description: Engineering team
    state: present
  register: result

# result: { "changed": true, "id": 7 }

- name: Create team in this org
  ansible.platform.team:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    name: "Backend Team"
    organization: "{{ result.id }}"   # used numeric id at top level
    state: present
```

**Sample result (2.5.x):**
```json
{
    "changed": true,
    "id": 7
}
```

---

### After (2.7.x)

```yaml
- name: Create organisation
  ansible.platform.organization:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    name: Engineering
    description: Engineering team
    state: present
  register: result

# result.organization.id is now the path

- name: Create team in this org
  ansible.platform.team:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    name: "Backend Team"
    organization: "Engineering"       # preferred — pass name, not id
    state: present
```

**Sample result (2.7.x):**
```json
{
    "changed": true,
    "organization": {
        "id": 7,
        "name": "Engineering",
        "description": "Engineering team",
        "max_hosts": 0
    },
    "elapsed_ms": 134,
    "api_version": "1"
}
```

---

## State: exists — before/after

### Before (2.5.x)
```json
{ "changed": false, "id": 7 }
```

### After (2.7.x)
```json
{
    "changed": false,
    "organization": {
        "id": 7,
        "name": "Engineering",
        "description": "Engineering team",
        "max_hosts": 0
    }
}
```

---

## Rename organisation — before/after

### Before (2.5.x)
```yaml
- name: Rename organisation
  ansible.platform.organization:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    name: Engineering
    new_name: Platform Engineering
    state: present
  register: result

# result: { "changed": true, "id": 7 }
```

### After (2.7.x)
```yaml
- name: Rename organisation
  ansible.platform.organization:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    name: Engineering
    new_name: Platform Engineering
    state: present
  register: result

# result: { "changed": true, "organization": { "id": 7, "name": "Platform Engineering", ... } }
```

---

## Full example playbook — before and after

### Before (2.5.x)
```yaml
---
- name: Organisation setup
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:
    - name: Create org
      ansible.platform.organization:
        gateway_hostname: https://gateway.example.com
        gateway_username: admin
        gateway_password: "{{ vault_pw }}"
        name: Engineering
        state: present
      register: org

    - name: Create team using org id
      ansible.platform.team:
        gateway_hostname: https://gateway.example.com
        gateway_username: admin
        gateway_password: "{{ vault_pw }}"
        name: Backend
        organization: "{{ org.id }}"           # top-level id
        state: present
```

### After (2.7.x)
```yaml
---
- name: Organisation setup
  hosts: localhost
  connection: local
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Create org
      ansible.platform.organization:
        name: Engineering
        state: present
      register: org

    - name: Create team using org name (preferred)
      ansible.platform.team:
        name: Backend
        organization: Engineering              # name lookup — no id needed
        state: present

    - name: Or use id if needed
      ansible.platform.team:
        name: Frontend
        organization: "{{ org.organization.id }}"   # nested id
        state: present
```
