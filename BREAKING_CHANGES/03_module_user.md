# Module: ansible.platform.user

## Arguments — full comparison table

| Argument | Type | Required | Old (2.5.x) | New (2.7.x) | Notes |
|----------|------|----------|-------------|-------------|-------|
| `username` | str | yes | ✓ same | ✓ same | 150 chars max, letters/digits/@/./+/-/_ only |
| `email` | str | no | ✓ same | ✓ same | |
| `first_name` | str | no | ✓ same | ✓ same | |
| `last_name` | str | no | ✓ same | ✓ same | |
| `password` | str | no | ✓ same | ✓ same | Write-only field |
| `is_superuser` | bool | no | ✓ same | ✓ same | Alias: `superuser` |
| `is_platform_auditor` | bool | no | ✓ deprecated | ✓ deprecated | Use `role_user_assignment` instead |
| `organizations` | list | no | ✓ deprecated | ✓ deprecated | Use `role_user_assignment` instead |
| `associated_authenticators` | dict | no | ✓ present | ✓ enhanced | Map of authenticator ID → {uid, email} |
| `update_secrets` | bool | no | N/A | ✓ new in 2.7 | Default: `true`. If `false`, skip secret fields on update |
| `authenticators` | list | no | ✓ deprecated | ✓ deprecated | Use `associated_authenticators` instead |
| `authenticator_uid` | str | no | ✓ deprecated | ✓ deprecated | Use `associated_authenticators` instead |
| `state` | str | no | present/absent/exists | present/absent/exists/enforced | `enforced` is new |
| `gateway_hostname` | str | no | ✓ old credential | deprecated | Use `gateway_url` instead |
| `gateway_url` | str | no | N/A | ✓ new credential | Replaces `gateway_hostname` |

## Result structure — breaking change

### Before (2.5.x)

```yaml
- name: Create user
  ansible.platform.user:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    username: jdoe
    first_name: John
    last_name: Doe
    email: jdoe@example.com
    is_superuser: false
    state: present
  register: result

- name: Assign role to user
  ansible.platform.role_user_assignment:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    role_definition: "Platform Auditor"
    user: "{{ result.id }}"          # top-level id
    state: present
```

**Sample result (2.5.x):**
```json
{
    "changed": true,
    "id": 42
}
```

---

### After (2.7.x)

```yaml
- name: Create user
  ansible.platform.user:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    username: jdoe
    first_name: John
    last_name: Doe
    email: jdoe@example.com
    is_superuser: false
    state: present
  register: result

- name: Assign role to user
  ansible.platform.role_user_assignment:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    role_definition: "Platform Auditor"
    user: "{{ result.user.id }}"     # nested under 'user'
    state: present
```

**Sample result (2.7.x):**
```json
{
    "changed": true,
    "user": {
        "id": 42,
        "username": "jdoe",
        "first_name": "John",
        "last_name": "Doe",
        "email": "jdoe@example.com",
        "is_superuser": false,
        "is_platform_auditor": false,
        "password": "Password Disabled",
        "organizations": [],
        "associated_authenticators": {}
    },
    "elapsed_ms": 187,
    "api_version": "1"
}
```

---

## State: exists — before/after

### Before (2.5.x)
```yaml
- name: Check if user exists
  ansible.platform.user:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    username: jdoe
    state: exists
  register: result

# result: { "changed": false, "id": 42 }

- debug:
    msg: "User ID is {{ result.id }}"
```

### After (2.7.x)
```yaml
- name: Check if user exists
  ansible.platform.user:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    username: jdoe
    state: exists
  register: result

# result:
# {
#   "changed": false,
#   "user": { "id": 42, "username": "jdoe", "email": "jdoe@example.com", ... }
# }

- debug:
    msg: "User ID is {{ result.user.id }}"      # was result.id
```

---

## State: enforced — new in 2.7.x

`state: enforced` is new. It sets only the fields you specify and leaves
all other fields at their current values. Useful for ensuring specific
attributes without overwriting unrelated settings.

```yaml
- name: Ensure user is not a superuser (enforce only that field)
  ansible.platform.user:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    username: jdoe
    is_superuser: false
    state: enforced
  register: result
```

**Sample result:**
```json
{
    "changed": true,
    "user": {
        "id": 42,
        "username": "jdoe",
        "first_name": "John",
        "last_name": "Doe",
        "email": "jdoe@example.com",
        "is_superuser": false,
        "is_platform_auditor": false,
        "password": "Password Disabled",
        "organizations": [],
        "associated_authenticators": {}
    },
    "elapsed_ms": 201,
    "api_version": "1"
}
```

---

## Deprecated fields (still work, will be removed in a future release)

| Field | Status | Replacement |
|-------|--------|-------------|
| `organizations` | Deprecated — returns empty list | Use `ansible.platform.role_user_assignment` |
| `is_platform_auditor` | Deprecated — still returned | No direct replacement yet |

---

## Full example playbook — before and after

### Before (2.5.x)
```yaml
---
- name: User management
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
        first_name: John
        last_name: Doe
        state: present
      register: user_result

    - name: Print user id
      debug:
        msg: "Created user with id {{ user_result.id }}"

    - name: Delete user
      ansible.platform.user:
        gateway_hostname: https://gateway.example.com
        gateway_username: admin
        gateway_password: "{{ vault_pw }}"
        username: jdoe
        state: absent
```

### After (2.7.x)
```yaml
---
- name: User management
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
        first_name: John
        last_name: Doe
        state: present
      register: user_result

    - name: Print user id
      debug:
        msg: "Created user with id {{ user_result.user.id }}"  # changed

    - name: Delete user
      ansible.platform.user:
        username: jdoe
        state: absent
```
