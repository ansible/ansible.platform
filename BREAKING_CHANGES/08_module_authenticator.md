# Modules: ansible.platform.authenticator and authenticator_map

## Arguments — full comparison tables

### authenticator

| Argument | Type | Required | Old (2.5.x) | New (2.7.x) | Notes |
|----------|------|----------|-------------|-------------|-------|
| `name` | str | yes | ✓ same | ✓ same | Must be unique |
| `new_name` | str | no | ✓ same | ✓ same | Rename by setting this |
| `slug` | str | no | N/A | ✓ new in 2.7 | Immutable identifier. Auto-generated if not provided |
| `enabled` | bool | no | ✓ same | ✓ same | Default: `false` |
| `create_objects` | bool | no | ✓ same | ✓ same | Allow creating users/teams/orgs. Default: `true` |
| `remove_users` | bool | no | ✓ same | ✓ same | Remove users from other groups on auth. Default: `true` |
| `type` | str | yes | ✓ same | ✓ same | Auth plugin type (e.g., `authenticator_plugins.ldap`) |
| `configuration` | dict | no | ✓ same | ✓ same | Plugin-specific config dict |
| `order` | int | no | ✓ same | ✓ same | Priority order. Default: `1` |
| `auto_migrate_users_to` | str | no | ✓ same | ✓ same | Auto-migrate users to target authenticator |
| `state` | str | no | present/absent/exists | present/absent/exists/enforced | `enforced` is new |
| `gateway_hostname` | str | no | ✓ old credential | deprecated | Use `gateway_url` instead |
| `gateway_url` | str | no | N/A | ✓ new credential | Replaces `gateway_hostname` |

### authenticator_map

| Argument | Type | Required | Old (2.5.x) | New (2.7.x) | Notes |
|----------|------|----------|-------------|-------------|-------|
| `name` | str | yes | ✓ same | ✓ same | Must be unique |
| `new_name` | str | no | ✓ same | ✓ same | Rename by setting this |
| `authenticator` | str | yes | ✓ same | ✓ same | Authenticator name or ID |
| `new_authenticator` | str | no | ✓ same | ✓ same | Change authenticator |
| `revoke` | bool | no | ✓ same | ✓ same | Revoke permission if rule doesn't match. Default: `false` |
| `map_type` | str | no | ✓ same | ✓ same | `allow`, `is_superuser`, `team`, `organization`, or `role` |
| `team` | str | no | ✓ same | ✓ same | Team name (required if map_type is `team`) |
| `organization` | str | no | ✓ same | ✓ same | Org name (required for org/team map_types) |
| `role` | str | no | ✓ same | ✓ same | Role definition name |
| `triggers` | dict | no | ✓ same | ✓ same | Trigger conditions for rule evaluation |
| `order` | int | no | ✓ same | ✓ same | Processing order. Default: `0` |
| `state` | str | no | present/absent/exists | present/absent/exists/enforced | `enforced` is new |
| `gateway_hostname` | str | no | ✓ old credential | deprecated | Use `gateway_url` instead |
| `gateway_url` | str | no | N/A | ✓ new credential | Replaces `gateway_hostname` |

## Result structure — breaking change

---

## authenticator

### Before (2.5.x)

**Sample result:**
```json
{
    "changed": true,
    "id": 5
}
```

```yaml
- name: Create LDAP authenticator
  ansible.platform.authenticator:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    name: "Corporate LDAP"
    type: "ansible_base.authentication.authenticator_plugins.ldap"
    configuration:
      SERVER_URI: "ldap://ldap.example.com"
      BIND_DN: "cn=admin,dc=example,dc=com"
      BIND_PASSWORD: "ldapsecret"
      USER_SEARCH:
        - "ou=users,dc=example,dc=com"
        - "SCOPE_SUBTREE"
        - "(uid=%(user)s)"
    enabled: true
    state: present
  register: auth_result

- debug:
    msg: "Authenticator ID: {{ auth_result.id }}"
```

---

### After (2.7.x)

**Sample result:**
```json
{
    "changed": true,
    "authenticator": {
        "id": 5,
        "name": "Corporate LDAP",
        "type": "ansible_base.authentication.authenticator_plugins.ldap",
        "enabled": true,
        "configuration": {
            "SERVER_URI": "ldap://ldap.example.com",
            "BIND_DN": "cn=admin,dc=example,dc=com",
            "USER_SEARCH": ["ou=users,dc=example,dc=com", "SCOPE_SUBTREE", "(uid=%(user)s)"]
        },
        "slug": "corporate-ldap",
        "order": 1
    },
}
```

```yaml
- name: Create LDAP authenticator
  ansible.platform.authenticator:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    name: "Corporate LDAP"
    type: "ansible_base.authentication.authenticator_plugins.ldap"
    configuration:
      SERVER_URI: "ldap://ldap.example.com"
      BIND_DN: "cn=admin,dc=example,dc=com"
      BIND_PASSWORD: "ldapsecret"
      USER_SEARCH:
        - "ou=users,dc=example,dc=com"
        - "SCOPE_SUBTREE"
        - "(uid=%(user)s)"
    enabled: true
    state: present
  register: auth_result

- debug:
    msg: "Authenticator ID: {{ auth_result.authenticator.id }}"    # nested
```

---

## authenticator_map

### Before (2.5.x)

**Sample result:**
```json
{
    "changed": true,
    "id": 18
}
```

```yaml
- name: Create authenticator map
  ansible.platform.authenticator_map:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    name: "LDAP Admin Map"
    authenticator: "Corporate LDAP"
    map_type: "is_superuser"
    triggers:
      groups:
        has_or:
          - "cn=admins,ou=groups,dc=example,dc=com"
    state: present
  register: map_result

- debug:
    msg: "Map ID: {{ map_result.id }}"
```

---

### After (2.7.x)

**Sample result:**
```json
{
    "changed": true,
    "authenticator_map": {
        "id": 18,
        "name": "LDAP Admin Map",
        "authenticator": 5,
        "map_type": "is_superuser",
        "triggers": {
            "groups": {
                "has_or": ["cn=admins,ou=groups,dc=example,dc=com"]
            }
        },
        "organization": null,
        "team": null,
        "order": 1
    },
}
```

```yaml
- name: Create authenticator map
  ansible.platform.authenticator_map:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    name: "LDAP Admin Map"
    authenticator: "Corporate LDAP"
    map_type: "is_superuser"
    triggers:
      groups:
        has_or:
          - "cn=admins,ou=groups,dc=example,dc=com"
    state: present
  register: map_result

- debug:
    msg: "Map ID: {{ map_result.authenticator_map.id }}"    # nested
```

---

## Full example playbook — before and after

### Before (2.5.x)
```yaml
---
- name: LDAP authentication setup
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:
    - name: Create LDAP authenticator
      ansible.platform.authenticator:
        gateway_hostname: https://gateway.example.com
        gateway_username: admin
        gateway_password: "{{ vault_pw }}"
        name: Corporate LDAP
        type: ansible_base.authentication.authenticator_plugins.ldap
        configuration:
          SERVER_URI: ldap://ldap.example.com
          BIND_DN: cn=admin,dc=example,dc=com
          BIND_PASSWORD: "{{ vault_ldap_pw }}"
        enabled: true
        state: present
      register: auth

    - name: Map LDAP admins to superusers
      ansible.platform.authenticator_map:
        gateway_hostname: https://gateway.example.com
        gateway_username: admin
        gateway_password: "{{ vault_pw }}"
        name: Admin Map
        authenticator: "{{ auth.id }}"         # top-level id
        map_type: is_superuser
        triggers:
          groups:
            has_or:
              - cn=admins,ou=groups,dc=example,dc=com
        state: present
```

### After (2.7.x)
```yaml
---
- name: LDAP authentication setup
  hosts: localhost
  connection: local
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Create LDAP authenticator
      ansible.platform.authenticator:
        name: Corporate LDAP
        type: ansible_base.authentication.authenticator_plugins.ldap
        configuration:
          SERVER_URI: ldap://ldap.example.com
          BIND_DN: cn=admin,dc=example,dc=com
          BIND_PASSWORD: "{{ vault_ldap_pw }}"
        enabled: true
        state: present
      register: auth

    - name: Map LDAP admins to superusers
      ansible.platform.authenticator_map:
        name: Admin Map
        authenticator: Corporate LDAP          # pass name directly — cleaner
        map_type: is_superuser
        triggers:
          groups:
            has_or:
              - cn=admins,ou=groups,dc=example,dc=com
        state: present
```
