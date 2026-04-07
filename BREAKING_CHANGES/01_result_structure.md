# Breaking Change: Task result structure

## Affects

Every module in the `ansible.platform` collection.

## What changed

In 2.5.x, module results returned `id` and a handful of fields at the **top level**
of the result dict alongside `changed`.

In 2.7.x, the resource data is nested under a **module-named key**
(e.g. `user`, `organization`, `team`). The top level contains only `changed`
and optional metadata fields.

---

## Before (2.5.x)

```yaml
- name: Create a user
  ansible.platform.user:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    username: jdoe
    email: jdoe@example.com
    state: present
  register: result

# result looks like:
# {
#   "changed": true,
#   "id": 42
# }

- name: Use the id in the next task
  ansible.platform.role_user_assignment:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    role_definition: "Platform Auditor"
    user: "{{ result.id }}"           # <-- top-level id
    state: present
```

**Sample output (2.5.x):**
```json
{
    "changed": true,
    "id": 42
}
```

---

## After (2.7.x)

```yaml
- name: Create a user
  ansible.platform.user:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    username: jdoe
    email: jdoe@example.com
    state: present
  register: result

# result looks like:
# {
#   "changed": true,
#   "user": {
#     "id": 42,
#     "username": "jdoe",
#     "email": "jdoe@example.com",
#     "first_name": "",
#     "last_name": "",
#     "is_superuser": false,
#     "is_platform_auditor": false,
#     "password": "Password Disabled",
#     "organizations": [],
#     "associated_authenticators": {}
#   }
# }

- name: Use the id in the next task
  ansible.platform.role_user_assignment:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    role_definition: "Platform Auditor"
    user: "{{ result.user.id }}"      # <-- nested under 'user'
    state: present
```

**Sample output (2.7.x):**
```json
{
    "changed": true,
    "user": {
        "id": 42,
        "username": "jdoe",
        "email": "jdoe@example.com",
        "first_name": "",
        "last_name": "",
        "is_superuser": false,
        "is_platform_auditor": false,
        "password": "Password Disabled",
        "organizations": [],
        "associated_authenticators": {}
    }
}
```

---

## Module-to-result-key mapping

| Module | Old top-level key | New nested key |
|--------|------------------|----------------|
| `ansible.platform.user` | `id` | `result.user.id` |
| `ansible.platform.organization` | `id` | `result.organization.id` |
| `ansible.platform.team` | `id` | `result.team.id` |
| `ansible.platform.application` | `id` | `result.application.id` |
| `ansible.platform.authenticator` | `id` | `result.authenticator.id` |
| `ansible.platform.authenticator_map` | `id` | `result.authenticator_map.id` |
| `ansible.platform.role_user_assignment` | `id` | `result.role_user_assignment.id` |
| `ansible.platform.role_team_assignment` | `id` | `result.role_team_assignment.id` |
| `ansible.platform.route` | `id` | `result.route.id` |
| `ansible.platform.http_port` | `id` | `result.http_port.id` |
| `ansible.platform.service` | `id` | `result.service.id` |
| `ansible.platform.service_cluster` | `id` | `result.service_cluster.id` |
| `ansible.platform.service_node` | `id` | `result.service_node.id` |
| `ansible.platform.service_key` | `id` | `result.service_key.id` |
| `ansible.platform.service_type` | `id` | `result.service_type.id` |
| `ansible.platform.ui_plugin_route` | `id` | `result.ui_plugin_route.id` |
| `ansible.platform.ca_certificate` | `id` | `result.ca_certificate.id` |
| `ansible.platform.feature_flag` | `id` | `result.feature_flag.id` |
| `ansible.platform.settings` | `id` | `result.settings.id` |
| `ansible.platform.token` | `id` | `result.token.id` |

---

## New fields in the result (2.7.x only)

Every result in 2.7.x also includes:

```json
{
    "changed": true,
    "user": { ... },
    "elapsed_ms": 143,
    "api_version": "1"
}
```

- `elapsed_ms` — total time taken for the API operation in milliseconds
- `api_version` — the API version used for the request (`"1"` or `"2"`)

These are purely additive and will not break existing playbooks.

---

## How to find affected tasks in your playbooks

```bash
# Find all register + result.id patterns
grep -rn "\.id\b" your_playbooks/ | grep -v "\.user\.id\|\.org\|\.team"

# Find tasks using result keys at top level
grep -rn "result\.\(username\|name\|email\|changed\)" your_playbooks/
```

---

## State: exists — changed behaviour

In 2.5.x, `state: exists` returned only `id` and set `changed: false`.

In 2.7.x, `state: exists` returns the **full resource dict** under the module key,
with `changed: false`. This is additive (more data), but if your playbook checked
`result.id` directly on an `exists` task it now needs to use `result.<module>.id`.

**Before:**
```json
{ "changed": false, "id": 42 }
```

**After:**
```json
{
    "changed": false,
    "user": {
        "id": 42,
        "username": "jdoe",
        "email": "jdoe@example.com",
        ...
    }
}
```
