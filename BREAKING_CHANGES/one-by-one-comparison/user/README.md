# Module Comparison: ansible.platform.user

**Before:** `stable-2.6` (`platform_main_before_1640`)
**After:** `stable-2.7` / ANSTRAT-1640 branch
**Module:** `ansible.platform.user`

---

## Summary

The `user` module **arguments are largely unchanged** but the result structure changed significantly:

1. **Result structure** — all fields are now nested under `result.user` (preferred). Flat top-level keys remain for backward compatibility (deprecated, removal after 2028-04-01)
2. **Execution path** — module is now doc-only; logic runs in action plugin via manager process
3. **Internal implementation** — no longer uses `AAPUser` object; uses action plugin with `AnsibleUser` dataclass
4. **Integration tests** — assertions updated from `result.id` → `result.user.id`, etc.
5. **Test changes** — replaced `gateway_api` lookup with `state: exists` pattern; test reference to authenticator changed from `.id` → `.authenticator.id`

---

## 1. Arguments — MINIMAL CHANGES

The vast majority of arguments are identical. Only minor cosmetic documentation changes:

| Argument | Type | Required | 2.6 Default | 2.7 Default | Description |
|----------|------|----------|------------|------------|-------------|
| `username` | str | **yes** | — | — | Username; 150 chars or fewer |
| `first_name` | str | no | — | — | First name of the user |
| `last_name` | str | no | — | — | Last name of the user |
| `email` | str | no | — | — | Email address |
| `is_superuser` | bool | no | — | — | Superuser privileges (alias: `superuser`) |
| `is_platform_auditor` | bool | no | — | — | Platform auditor flag (alias: `auditor`, **deprecated**) |
| `password` | str | no | — | — | Write-only password field |
| `update_secrets` | bool | no | `true` | `true` | Force password re-push on updates |
| `organizations` | list[str] | no | — | — | Org associations (**deprecated**) |
| `authenticators` | list[str] | no | — | — | Authenticator associations (**deprecated**) |
| `authenticator_uid` | str | no | — | — | Authenticator UID (**deprecated**) |
| `associated_authenticators` | dict | no | — | — | Map of authenticator ID → {uid, email} |
| `state` | str | no | `present` | `present` | Desired state: `present`, `absent`, `exists`, `enforced` |

**Key difference:** In 2.7, the deprecated fields (`organizations`, `authenticators`, `authenticator_uid`, `is_platform_auditor`) still work but emit warnings.
The `authenticators` field changed type from `list[str]` to `list[int]` in the action plugin's internal validation.

---

## 2. Result Structure

### Before (2.6.x) — flat top-level keys

```json
{
    "changed": true,
    "id": 42,
    "username": "jdoe",
    "email": "jdoe@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "is_superuser": false,
    "is_platform_auditor": false,
    "password": "Password Disabled",
    "organizations": [],
    "associated_authenticators": {}
}
```

### After (2.7.x) — nested under `user` key

```json
{
    "changed": true,
    "user": {
        "id": 42,
        "username": "jdoe",
        "email": "jdoe@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "is_superuser": false,
        "is_platform_auditor": false,
        "password": "Password Disabled",
        "organizations": [],
        "associated_authenticators": {}
    },
}
```
> **Backward Compatibility (2.7.x):** Flat top-level keys (`result.id`, `result.username`, etc.)
> are kept alongside the nested key for backward compatibility with ≤2.6 playbooks.
> They are silently deprecated and scheduled for removal after 2028-04-01.
> Prefer `result.<module>.<field>` in new code.



### Key differences

| Field | Before | After |
|-------|--------|-------|
| `id` | `result.id` | `result.user.id` |
| `username` | `result.username` | `result.user.username` |
| `email` | `result.email` | `result.user.email` |
| `password` | `result.password` | `result.user.password` |
| `associated_authenticators` | `result.associated_authenticators` | `result.user.associated_authenticators` |
| Any other field | `result.<field>` | `result.user.<field>` |

---

## 3. Documentation Changes

The 2.7 DOCUMENTATION block is significantly improved with:
- Clearer state descriptions (includes CRUD semantics explanation)
- Explicit notes about round-trip compatibility
- Better RETURN section documenting the `user` nested key
- Password field handling documented (always returned as "Password Disabled")

The 2.6 version had minimal documentation; 2.7 is much more complete.

---

## 4. Examples — MAJOR CHANGES

### Before (2.6.x) — minimal examples

```yaml
- name: Add user
  ansible.platform.user:
    username: jdoe
    password: foobarbaz
    email: jdoe@example.org
    first_name: John
    last_name: Doe
    state: present

- name: Add user as a system administrator
  ansible.platform.user:
    username: jdoe
    password: foobarbaz
    email: jdoe@example.org
    superuser: true
    state: present
```

### After (2.7.x) — comprehensive examples with best practices

```yaml
# Create a user
- name: Create a user
  ansible.platform.user:
    username: jdoe
    first_name: Jane
    last_name: Doe
    email: jdoe@example.com
    password: "{{ vault_jdoe_password }}"
    state: present
  register: created_user

# Idempotent re-run
- name: Idempotent re-run — no change expected
  ansible.platform.user:
    username: jdoe
    first_name: Jane
    last_name: Doe
    email: jdoe@example.com
    state: present

# Round-trip pattern (2.7 NEW)
- name: Round-trip update using registered result
  ansible.platform.user: "{{ created_user.user | combine({'email': 'jdoe-updated@example.com'}) }}"

# Reference by ID (2.7 NEW)
- name: Update user by id
  ansible.platform.user:
    username: "{{ created_user.user.id }}"
    first_name: Janet

# Check existence without making changes (2.7 NEW)
- name: Check whether a user exists
  ansible.platform.user:
    username: jdoe
    state: exists
  register: user_check
```

---

## 5. Integration Test Comparison

### Changes to test file structure

The tests remained logically identical but with these concrete changes:

| Aspect | Before (2.6) | After (2.7) |
|--------|---------|---------|
| Check-mode verification | Uses `ansible.platform.gateway_api` lookup | Uses `state: exists` pattern |
| Test authenticator reference | `test_authenticator.id` | `test_authenticator.authenticator.id` |
| Cleanup conditional checks | `when: "item in vars and 'id' in vars[item]"` | `when: "item in vars and vars[item].user is defined and 'id' in vars[item].user"` |

### Example test assertion changes

```yaml
# BEFORE (2.6.x) — flat result
- name: Assert the creation of the user changed the system
  ansible.builtin.assert:
    that:
      - joe is changed
      - joe.id is defined
      - joe.username == username

# AFTER (2.7.x) — nested result
- name: Assert the creation of the user changed the system
  ansible.builtin.assert:
    that:
      - joe is changed
      - joe.user.id is defined
      - joe.user.username == username
```

### Specific test changes

**Before (2.6) — check_mode verification:**
```yaml
- name: Search for Joe user and assert that it does not exist
  ansible.builtin.set_fact:
    item_that_should_not_exist: "{{ lookup('ansible.platform.gateway_api', 'users',
      query_params={'username': '{{ username }}'}, **connection_info) }}"

- name: Assert that Joe user does not exist
  ansible.builtin.assert:
    that:
      - item_that_should_not_exist is not defined or item_that_should_not_exist | length == 0
```

**After (2.7) — check_mode verification:**
```yaml
- name: Check that Joe user does not exist
  ansible.platform.user:
    username: "{{ username }}"
    state: exists
  register: joe_search

- name: Assert that Joe user does not exist
  ansible.builtin.assert:
    that:
      - not joe_search.exists | default(false)
```

**Before (2.6) — authenticator reference in test:**
```yaml
- name: Update Joe with associated_authenticators
  ansible.platform.user:
    username: "{{ username }}"
    associated_authenticators: "{{ { test_authenticator.id: {'uid': username, 'email': username ~ '@example.com'} } }}"
```

**After (2.7) — authenticator reference in test:**
```yaml
- name: Update Joe with associated_authenticators
  ansible.platform.user:
    username: "{{ username }}"
    associated_authenticators: "{{ { test_authenticator.authenticator.id: {'uid': username, 'email': username ~ '@example.com'} } }}"
```

---

## 6. Internal Implementation Changes

### plugins/modules/user.py

| Aspect | Before (2.6.x) | After (2.7.x) |
|--------|---------------|---------------|
| Execution | `AAPModule` with `AAPUser(module).manage()` runs inline | Doc-only stub; action plugin executes |
| Functions | `process_organizations()`, `cleanup_user()`, `audit_user()` | Removed; all logic in action plugin |
| Imports | `from ..module_utils.aap_module import AAPModule` | None (doc-only) |
| Authentication handling | Handled inline | Handled by action plugin base class |

### plugins/module_utils/aap_user.py

**Removed entirely in 2.7** — replaced by action plugin pattern.

### plugins/action/user.py (NEW in 2.7)

```python
class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "user"
    MODEL_CLASS = AnsibleUser
    LOOKUP_FIELD = "username"

    _WRITE_ONLY_FIELDS = frozenset({"update_secrets"})
    _DEPRECATED_FIELDS = {
        "authenticators": (..., "4.0.0"),
        "authenticator_uid": (..., "4.0.0"),
    }
```

Key features:
- **Numeric username lookup:** If `username` is a digit string (e.g., from `user.id`), treat it as ID-based lookup
- **Selective field handling:** `_build_ansible_data()` sends only explicitly-provided fields (prevents clearing org memberships accidentally)
- **Password handling:** `_pre_execute_hook()` strips password on updates when `update_secrets=False`

### plugins/plugin_utils/ansible_models/user.py (NEW in 2.7)

```python
@dataclass
class AnsibleUser:
    # Required
    username: str

    # Optional
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    is_superuser: Optional[bool] = None
    is_platform_auditor: Optional[bool] = None
    organizations: Optional[List[str]] = None
    associated_authenticators: Optional[Dict[str, Any]] = None
    state: str = "present"

    # Read-only (populated from API)
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None

    def __post_init__(self):
        if self.organizations is None:
            self.organizations = []
```

### plugins/plugin_utils/api/v1/user.py (NEW in 2.7)

Handles transformation between Ansible format and API format:
- Simple field mappings (1:1)
- Complex transformations: `organizations` (list of names) → `organization_ids` (list of IDs)
- Password special handling: never sends on update; skips "Password Disabled" placeholder
- Field mapping registry with forward/reverse transforms

---

## 7. Migration Checklist for user module

- [ ] Replace all `result.id` → `result.user.id`
- [ ] Replace all `result.username` → `result.user.username`
- [ ] Replace all `result.email` → `result.user.email`
- [ ] Replace all `result.<field>` → `result.user.<field>`
- [ ] Replace `gateway_api` lookup for check_mode verification → use `state: exists` pattern
- [ ] Update cleanup block conditionals: `'id' in vars[item]` → `vars[item].user is defined and 'id' in vars[item].user`
- [ ] Update cross-module authenticator references: `test_authenticator.id` → `test_authenticator.authenticator.id`
- [ ] Test password handling: `update_secrets: false` prevents password from being sent on updates (useful for non-interactive user creation)
- [ ] For numeric username usage (ID-based lookup), the action plugin handles this transparently; behavior is backward-compatible
- [ ] If storing org associations, remember they are now deprecated — use `role_user_assignment` module instead
