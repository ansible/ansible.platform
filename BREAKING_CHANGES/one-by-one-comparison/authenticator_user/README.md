# Module Documentation: ansible.platform.authenticator_user

**Status:** NEW in 2.7 (ANSTRAT-1640)
**Module:** `ansible.platform.authenticator_user`

---

## Summary

The `authenticator_user` module is **NEW in 2.7**. It manages user authenticator assignments and migrations. No migration needed from 2.6 (module did not exist).

This module handles moving authenticator users to new authenticators, with options to:
- Merge accounts with same UID
- Preserve or reset RBAC memberships
- Remove secondary authenticator entries
- Specify new UID values during migration

---

## 1. Module Arguments

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `authenticator_user_id` | str | **yes** | — | The authenticator user ID to manage |
| `authenticator` | str | **yes** | — | Primary key of the authenticator to assign |
| `new_uid` | str | no | — | New UID for the user (matches auth provider login) |
| `keep_memberships` | bool | no | `false` | Retain RBAC memberships (vs. let authenticator_map manage) |
| `merge_with_user` | str | no | — | User ID to merge this account with |
| `merge_accounts_with_same_uid` | bool | no | `false` | Auto-merge accounts with matching UID |
| `remove_other_authenticators` | bool | no | `false` | Delete secondary authenticator_user entries |
| `state` | str | no | `present` (default), `exists` | Desired state |

---

## 2. Result Structure

### After (2.7.x) — nested under `authenticator_user` key

```json
{
    "changed": true,
    "authenticator_user": {
        "id": 9,
        "authenticator": 2,
        "user": 42,
        "uid": "jdoe",
        "created": "2025-04-06T12:34:56.000Z",
        "modified": "2025-04-06T12:34:56.000Z"
    },
}
```

### Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Numeric primary key assigned by the gateway |
| `authenticator` | int | ID of the authenticator this user is assigned to |
| `user` | int | ID of the associated user |
| `uid` | str | The UID value linking login to this user account |
| `created` | str | ISO 8601 timestamp when record was created |
| `modified` | str | ISO 8601 timestamp of last modification |

---

## 3. Documentation

The module documentation includes:
- Clear examples of account migration scenarios
- Options for handling RBAC memberships during migration
- Merge semantics and deduplication
- State descriptions (`present` vs `exists`)

---

## 4. Examples

```yaml
# Migrate authenticator user to a new authenticator
- name: Move authenticator user to new authenticator
  ansible.platform.authenticator_user:
    authenticator_user_id: 9
    authenticator: 2
    new_uid: jdoe
    merge_with_user: 149
    state: present
  register: migrated_user

# Auto-merge accounts with same UID
- name: Auto-merge with same UID
  ansible.platform.authenticator_user:
    authenticator_user_id: 4
    authenticator: 1
    merge_accounts_with_same_uid: true
    keep_memberships: true
    remove_other_authenticators: true
    state: present

# Verify authenticator user setup
- name: Check authenticator user exists
  ansible.platform.authenticator_user:
    authenticator_user_id: 4
    authenticator: 1
    state: exists
  register: user_check
```

---

## 5. Internal Implementation

| Aspect | Details |
|--------|---------|
| Execution | Action plugin via manager process |
| Module type | Doc-only stub (2.7) |
| Dataclass | `AnsibleAuthenticatorUser` |
| Lookup field | `authenticator_user_id` |

---

## 6. Notes

- **New in 2.7:** This module did not exist in 2.6
- **No migration needed:** If you're upgrading from 2.6, this module provides new functionality
- **Account management:** Used for authenticator user lifecycle and migrations
- **Merge semantics:** Provides multiple strategies for deduplicating accounts
- **RBAC handling:** Can preserve existing RBAC assignments or defer to authenticator_map rules

---

## 7. First-use Checklist

- [ ] Understand authenticator_user_id vs user_id distinction
- [ ] Review merge options (with_user vs merge_accounts_with_same_uid)
- [ ] Test membership preservation strategy
- [ ] Verify new_uid matches the target authenticator's format
- [ ] Check result at `result.authenticator_user.*` (nested key structure)
