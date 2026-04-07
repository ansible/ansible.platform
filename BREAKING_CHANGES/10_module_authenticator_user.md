# Module: ansible.platform.authenticator_user

Manage user authenticators — move a user to a new authenticator with optional account merging.

## Note: Module is new in 2.7.x

This module did not exist in 2.5.x. No migration needed — use directly in new playbooks.

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `authenticator_user_id` | str | yes | The authenticator user ID of the user to update |
| `authenticator` | str | yes | The primary key of the authenticator to move the user to |
| `new_uid` | str | no | The new UID for the user (must match login in new auth provider) |
| `keep_memberships` | bool | no | Retain RBAC memberships when moving to new authenticator. Default: `false` |
| `merge_with_user` | str | no | User ID of another user to merge with |
| `merge_accounts_with_same_uid` | bool | no | Auto-merge accounts with same UID. Default: `false` |
| `remove_other_authenticators` | bool | no | Delete other authenticator entries for this user. Default: `false` |
| `state` | str | no | Desired state: `present` (default) or `exists` |

## Result structure

### Example result (2.7.x)

```json
{
    "changed": true,
    "authenticator_user": {
        "id": 9,
        "user": 42,
        "authenticator": 2,
        "uid": "jdoe",
        "provider": "github",
        "created_at": "2025-01-15T10:30:00Z",
        "modified_at": "2025-01-15T11:00:00Z"
    },
}
```

## State: exists — example

```yaml
- name: Check if authenticator user exists
  ansible.platform.authenticator_user:
    authenticator_user_id: 9
    authenticator: 2
    state: exists
  register: result

# result:
# {
#   "changed": false,
#   "authenticator_user": {
#     "id": 9,
#     "user": 42,
#     "authenticator": 2,
#     "uid": "jdoe"
#   }
# }
```

## Full example playbook

```yaml
---
- name: Manage authenticator users
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Move user to new authenticator with merge
      ansible.platform.authenticator_user:
        authenticator_user_id: 9
        authenticator: 2
        new_uid: jdoe
        merge_with_user: 149
        state: present
      register: auth_result

    - name: Print authenticator user ID
      debug:
        msg: "Authenticator user ID: {{ auth_result.authenticator_user.id }}"

    - name: Move user and auto-merge with same UID
      ansible.platform.authenticator_user:
        authenticator_user_id: 4
        authenticator: 1
        merge_accounts_with_same_uid: true
        keep_memberships: true
        remove_other_authenticators: true
        state: present
```

## Common patterns

### Chain into user lookup

```yaml
- name: Move authenticator user and fetch full user details
  block:
    - name: Move authenticator user
      ansible.platform.authenticator_user:
        authenticator_user_id: "{{ auth_user_id }}"
        authenticator: "{{ new_auth_id }}"
        new_uid: "{{ new_username }}"
        state: present
      register: auth_result

    - name: Get user details from the returned ID
      ansible.platform.user:
        username: "{{ auth_result.authenticator_user.uid }}"
        state: exists
      register: user_details
```

### Verify before/after migration

```yaml
- name: Check before migration
  ansible.platform.authenticator_user:
    authenticator_user_id: "{{ user_id }}"
    authenticator: "{{ current_auth }}"
    state: exists
  register: before_state

- name: Migrate authenticator
  ansible.platform.authenticator_user:
    authenticator_user_id: "{{ user_id }}"
    authenticator: "{{ new_auth }}"
    new_uid: "{{ new_uid }}"
    state: present
  register: migrate_result
  when: before_state.authenticator_user.authenticator != new_auth

- name: Verify migration
  assert:
    that:
      - migrate_result.authenticator_user.authenticator == new_auth
    fail_msg: "Authenticator migration failed"
```
