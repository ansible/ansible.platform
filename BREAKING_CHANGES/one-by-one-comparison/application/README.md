# Module Comparison: ansible.platform.application

**Before:** `stable-2.6` (`platform_main_before_1640`)
**After:** `stable-2.7` / ANSTRAT-1640 branch
**Module:** `ansible.platform.application`

---

## Summary

The `application` module **did not change its arguments**. All parameter names, types,
and defaults are identical between 2.6 and 2.7. What changed is:

1. **Result structure** — every field is now nested under `result.application` for round-trip safe access. Flat top-level keys (`result.id`, `result.name`, etc.) are kept for backward compatibility and silently deprecated (scheduled for removal after 2028-04-01).
2. **Execution path** — module is now "doc-only"; logic runs in the action plugin via the manager process
3. **Internal implementation** — `aap_application.py` no longer instantiates `AAPOrganization` / `AAPUser` objects; it calls `module.get_one()` directly
4. **Integration tests** — assertions updated to use nested keys: `result.application.id`, `result.application.name`, etc.
5. **`client_id` placement** — `client_id` is API-generated and NOT in the nested `application` dict. It remains at the top level flat only (never round-trip safe as a module input). `client_secret` is not returned.
6. **`redirect_uris` type** — the API stores these as space-separated strings; the 2.7 output layer converts them to lists to match the `type: list` argument spec.

---

## 1. Arguments — UNCHANGED

Both versions accept exactly the same arguments:

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `name` | str | **yes** | — | Name of the application |
| `new_name` | str | no | — | Rename the application (looked up by `name`) |
| `organization` | str | **yes** | — | Organization name or ID |
| `new_organization` | str | no | — | Move to a different organization |
| `description` | str | no | — | Description |
| `authorization_grant_type` | str | no | `password`, `authorization-code` | Grant type for token acquisition |
| `client_type` | str | no | `public`, `confidential` | Security level of the client |
| `redirect_uris` | list[str] | no | — | Allowed redirect URLs (required for `authorization-code`) |
| `post_logout_redirect_uris` | list[str] | no | — | Allowed post-logout redirect URLs |
| `app_url` | str | no | — | URL of the application |
| `skip_authorization` | bool | no | `false` | Skip authorization for trusted apps |
| `algorithm` | str | no | `""`, `RS256`, `HS256` | OIDC token signing algorithm |
| `user` | str | no | — | Name or ID of user who owns this application |
| `state` | str | no | `present` (default), `absent`, `exists`, `enforced` | Desired state |

**No arguments were added, removed, or renamed.**

---

## 2. Result Structure

### Before (2.6.x) — flat top-level keys

```json
{
    "changed": true,
    "id": 42,
    "name": "Foo",
    "description": "Foo bar application",
    "organization": 5,
    "authorization_grant_type": "password",
    "client_type": "public",
    "client_id": "AbCdEfGhIjKlMnOpQrSt",
    "client_secret": "",
    "redirect_uris": "",
    "post_logout_redirect_uris": "",
    "skip_authorization": false,
    "algorithm": "",
    "app_url": "http://example.com",
    "user": null
}
```

### After (2.7.x) — nested key + backward-compat flat keys

```json
{
    "changed": true,
    "application": {
        "id": 42,
        "name": "Foo",
        "description": "Foo bar application",
        "organization": 5,
        "authorization_grant_type": "password",
        "client_type": "public",
        "redirect_uris": ["https://tower.com/api/v2/"],
        "post_logout_redirect_uris": [],
        "skip_authorization": false,
        "algorithm": "",
        "app_url": "http://example.com",
        "user": null
    },
    "id": 42,
    "name": "Foo",
    "description": "Foo bar application",
    "organization": 5,
    "authorization_grant_type": "password",
    "client_type": "public",
    "redirect_uris": ["https://tower.com/api/v2/"],
    "post_logout_redirect_uris": [],
    "skip_authorization": false,
    "algorithm": "",
    "app_url": "http://example.com",
    "user": null,
    "client_id": "AbCdEfGhIjKlMnOpQrSt"
}
```

**Key structural points for 2.7.x:**

- `result.application` is the **round-trip safe** nested dict. It contains only argspec fields — safe to re-feed as module arguments. It does NOT contain `client_id` (not an argspec field), `created`, `modified`, or `url` (read-only metadata).
- Flat top-level keys (`result.id`, `result.name`, etc.) are kept for **backward compatibility** with ≤2.6 playbooks. They are silently deprecated and will be removed after 2028-04-01.
- `client_id` is returned **flat only** at `result.client_id`. It is NOT inside `result.application` because it is not a valid module input.
- `client_secret` is **not returned** — it is only present once on initial create in the raw API response, and is intentionally omitted.
- `redirect_uris` / `post_logout_redirect_uris` are returned as **lists** (matching `type: list` argspec), even though the API stores them as space-separated strings internally.

### Key differences

| Field | Before (2.6.x) | After (2.7.x) |
|-------|---------------|---------------|
| `id` | `result.id` | `result.application.id` (preferred) or `result.id` (deprecated) |
| `name` | `result.name` | `result.application.name` (preferred) or `result.name` (deprecated) |
| `client_id` | `result.client_id` | `result.client_id` (unchanged — NOT nested) |
| `redirect_uris` | `result.redirect_uris` (str) | `result.application.redirect_uris` (list) |
| Any other argspec field | `result.<field>` | `result.application.<field>` (preferred) or `result.<field>` (deprecated) |
| `elapsed_ms` | not present | not present (not returned by this collection) |

> **Note on `client_id`:** This OAuth credential is API-generated (not user-supplied). In both
> 2.6.x and 2.7.x it is at `result.client_id`. It does NOT appear inside `result.application`
> because passing it back as a module argument would cause an unknown-argument error.

---

## 3. Documentation — UNCHANGED

The `DOCUMENTATION` block in `plugins/modules/application.py` is identical between 2.6 and 2.7.
Only cosmetic formatting changed (single-quoted docstring → double-quoted).

The `extends_documentation_fragment: ansible.platform.auth` reference is identical.

The `doc_fragments/auth.py` fragment is **byte-for-byte identical** between the two versions.
All auth params (`aap_hostname`, `aap_username`, `aap_password`, `aap_token`,
`aap_validate_certs`, `aap_request_timeout`) and their aliases (`gateway_hostname`, etc.)
are unchanged.

---

## 4. Examples — UNCHANGED (but best practice updated)

Both versions ship these identical examples in `EXAMPLES`:

```yaml
- name: Add Foo application
  ansible.platform.application:
    name: "Foo"
    description: "Foo bar application"
    organization: "test"
    state: present
    authorization_grant_type: password
    client_type: public
    app_url: http://example.com

- name: Add Foo application
  ansible.platform.application:
    name: "Foo"
    description: "Foo bar application"
    organization: "test"
    state: present
    authorization_grant_type: authorization-code
    client_type: confidential
    redirect_uris:
      - http://example.com/api/gateway/v1/
    app_url: http://example.com
```

**New recommended pattern for 2.7.x** using `module_defaults`:

```yaml
---
- name: Manage platform applications
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"
      gateway_validate_certs: true

  tasks:
    - name: Create a confidential application with authorization-code grant
      ansible.platform.application:
        name: "My OAuth App"
        description: "Production OAuth2 application"
        organization: "Default"
        authorization_grant_type: authorization-code
        client_type: confidential
        redirect_uris:
          - https://myapp.example.com/callback
          - https://myapp.example.com/auth/complete
        app_url: https://myapp.example.com
        state: present
      register: app_result

    # client_id is at app_result.client_id in BOTH 2.6.x and 2.7.x (not nested in 2.7)
    - name: Store client_id for OAuth configuration
      ansible.builtin.debug:
        msg: "OAuth client_id: {{ app_result.client_id }}"

    - name: Create a public application (password grant)
      ansible.platform.application:
        name: "Internal Script"
        organization: "Default"
        authorization_grant_type: password
        client_type: public
        state: present
      register: public_app

    - name: Delete an application
      ansible.platform.application:
        name: "Old App"
        organization: "Default"
        state: absent
```

---

## 5. Integration Test Comparison

### Test coverage — same scenarios in both versions

Both versions test the same 20 scenarios:

| # | Test | Notes |
|---|------|-------|
| 1 | Create app with `check_mode: true` | Dry run — must not create |
| 2 | Verify app does not exist after check_mode | |
| 3 | Create app1 (password grant, public) | |
| 4 | Assert app1 `changed: true` | |
| 5 | Recreate app1 (idempotency) | |
| 6 | Assert idempotent (no change) | |
| 7 | Create app2 (authorization-code, confidential, redirect URIs) | |
| 8 | Create app3 (user-owned application) | |
| 9 | Create app4 (skip_authorization, confidential) | |
| 10 | Create app5 (confidential, no URL) | |
| 11 | Create app6 (with app_url) | |
| 12 | `state: exists` — verify no change | |
| 13 | Update redirect_uris | |
| 14 | Change user ownership | |
| 15 | Rename application (`new_name`) | |
| 16 | Move to new org (`new_organization`) | |
| 17 | Update app_url | |
| 18 | Blank out app_url | |
| 19 | Delete non-existent application | |
| 20 | Delete real application | |

### Key test assertion changes

Every result reference changed from flat to nested:

```yaml
# BEFORE (2.6.x)
- recreate_app1.id == app1.id
- change_app1.id == app1.id
- rename_app4.id == app4.id
- app1.name          # direct field access
- org1.id            # org result was also flat

# AFTER (2.7.x)
- recreate_app1.application.id == app1.application.id
- change_app1.application.id == app1.application.id
- rename_app4.application.id == app4.application.id
- app1.application.name      # nested under application key
- org1.organization.id       # org result also nested
```

### Lookup change in check_mode test

The 2.6 test used the `ansible.platform.gateway_api` lookup plugin to verify
the application wasn't created by check_mode. The 2.7 test uses `state: exists`
on the module itself, which is more portable and doesn't require the lookup plugin.

```yaml
# BEFORE — gateway_api lookup
- name: Search for Application 1
  ansible.builtin.set_fact:
    item_that_should_not_exist: "{{ lookup('ansible.platform.gateway_api', 'applications',
      query_params={'name': '{{ name_prefix }}-app1'}, **connection_info) }}"

# AFTER — state: exists pattern
- name: Check that Application 1 does not exist
  ansible.platform.application:
    name: "{{ name_prefix }}-app1"
    organization: "{{ name_prefix }}-Organization-1"
    state: exists
  register: app1_search

- name: Assert that Application 1 does not exist
  ansible.builtin.assert:
    that:
      - not app1_search.exists | default(false)
```

### Cleanup block changes

The `always:` cleanup block updated all conditional guards and field references:

```yaml
# BEFORE
- name: Delete Applications in Org1
  ansible.platform.application:
    name: "{{ vars[item].id }}"
    organization: "{{ org1.id }}"
    state: absent
  loop: [...]
  when: "item in vars and 'id' in vars[item]"

# AFTER
- name: Delete Applications in Org1
  ansible.platform.application:
    name: "{{ vars[item].application.id }}"
    organization: "{{ org1.organization.id }}"
    state: absent
  loop: [...]
  when: "item in vars and vars[item].application is defined and 'id' in vars[item].application"
```

---

## 6. Internal Implementation Changes

### plugins/modules/application.py

| Aspect | Before (2.6.x) | After (2.7.x) |
|--------|---------------|---------------|
| Execution | `AAPModule` + `AAPApplication(module).manage(...)` runs HTTP calls inline | Doc-only stub; logic runs via action plugin in manager process |
| `manage()` call | `AAPApplication(module).manage(json_output_fields=['client_id', 'client_secret'])` | Removed — action plugin handles this |
| Import | `from ..module_utils.aap_module import AAPModule` | No imports (stub) |

### plugins/module_utils/aap_application.py

| Method | Before (2.6.x) | After (2.7.x) |
|--------|---------------|---------------|
| `_get_organization()` | Creates `AAPOrganization(module, params)` and calls `.manage()` | Calls `module.get_one("organizations", name_or_id)` directly |
| `get_user()` | Creates `AAPUser(module, params)` and calls `.manage()` | Calls `module.get_one("users", username)` directly |
| Return type | `AAPOrganization` / `AAPUser` objects (have `.data` attr) | `_Result(data)` wrapper (also has `.data` attr) |
| Interface to caller | Same `.data` dict access pattern | Same `.data` dict access pattern |

The `_Result` class is a lightweight wrapper introduced to maintain the same `.data`
interface without the overhead of full `AAPOrganization`/`AAPUser` object lifecycle:

```python
# AFTER: new _Result class
class _Result(object):
    """Simple holder for .data (used for organization/user lookup results)."""
    def __init__(self, data):
        self.data = data
```

---

## 7. Migration Checklist for application module

> The flat top-level keys (`result.id`, `result.name`, etc.) still work in 2.7.x for backward
> compatibility. Migration is recommended before the 2028-04-01 removal date.

- [ ] Migrate `result.id` → `result.application.id` (flat `result.id` still works but deprecated)
- [ ] Migrate `result.name` → `result.application.name`
- [ ] Migrate `result.<field>` → `result.application.<field>` for any argspec field
- [ ] **`result.client_id` stays as-is** — it is NOT nested in 2.7.x (no migration needed)
- [ ] **`result.client_secret` is gone** — was only returned on initial create; remove any code that reads it
- [ ] `result.redirect_uris` is now a list, not a string — update any code that split it manually
- [ ] Update `gateway_api` lookup usage → use `state: exists` pattern instead
- [ ] Update cross-module references: `org_result.id` → `org_result.organization.id`
- [ ] Update cross-module references: `user_result.username` → `user_result.user.username`
- [ ] Update `when:` guards in cleanup/always blocks to check `vars[item].application is defined`
- [ ] Test round-trip: `result.application` contents can be fed directly back as module arguments
