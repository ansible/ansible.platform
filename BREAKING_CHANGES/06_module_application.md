# Module: ansible.platform.application

## Arguments — full comparison table

| Argument | Type | Required | Old (2.5.x) | New (2.7.x) | Notes |
|----------|------|----------|-------------|-------------|-------|
| `name` | str | yes | ✓ same | ✓ same | Must be unique within organization |
| `description` | str | no | ✓ same | ✓ same | Application description |
| `organization` | str | yes | ✓ same | ✓ same | Organization name or ID |
| `authorization_grant_type` | str | yes | ✓ same | ✓ same | One of: `authorization-code`, `implicit`, `password`, `client-credentials` |
| `client_type` | str | yes | ✓ same | ✓ same | One of: `confidential`, `public` |
| `redirect_uris` | str | no | ✓ same | ✓ same | Newline-separated redirect URIs |
| `skip_authorization` | bool | no | ✓ same | ✓ same | Default: `false` |
| `state` | str | no | present/absent/exists | present/absent/exists/enforced | `enforced` is new |
| `gateway_hostname` | str | no | ✓ old credential | deprecated | Use `gateway_url` instead |
| `gateway_url` | str | no | N/A | ✓ new credential | Replaces `gateway_hostname` |

## Result structure — breaking change

### Before (2.5.x)

**Sample result:**
```json
{
    "changed": true,
    "id": 23
}
```

```yaml
- name: Create application
  ansible.platform.application:
    gateway_hostname: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    name: "My OAuth App"
    organization: Engineering
    authorization_grant_type: authorization-code
    client_type: confidential
    redirect_uris: "https://myapp.example.com/callback"
    state: present
  register: app_result

- debug:
    msg: "Application ID: {{ app_result.id }}"
```

---

### After (2.7.x)

**Sample result:**
```json
{
    "changed": true,
    "application": {
        "id": 23,
        "name": "My OAuth App",
        "description": "",
        "organization": 7,
        "authorization_grant_type": "authorization-code",
        "client_type": "confidential",
        "redirect_uris": ["https://myapp.example.com/callback"],
        "skip_authorization": false
    },
    "client_id": "abc123clientid"
}
```

> **Note:** `client_id` is returned **flat** at the top level (not inside `application`).
> It is API-generated and is never a round-trip input field.
> `client_secret` is **not** returned by the collection.

```yaml
- name: Create application
  ansible.platform.application:
    gateway_url: https://gateway.example.com
    gateway_username: admin
    gateway_password: secret
    name: "My OAuth App"
    organization: Engineering
    authorization_grant_type: authorization-code
    client_type: confidential
    redirect_uris: "https://myapp.example.com/callback"
    state: present
  register: app_result

- debug:
    msg: "Application ID: {{ app_result.application.id }}, client_id: {{ app_result.client_id }}"
```

---

## Notable improvement: client_id now in result

In 2.5.x you had to make a separate API call to retrieve `client_id` after
creating an application. In 2.7.x it is included directly in the result at
`result.client_id` (flat — **not** nested inside `result.application`).

---

## Full example playbook — before and after

### Before (2.5.x)
```yaml
---
- name: OAuth application setup
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:
    - name: Create OAuth application
      ansible.platform.application:
        gateway_hostname: https://gateway.example.com
        gateway_username: admin
        gateway_password: "{{ vault_pw }}"
        name: CI Pipeline App
        organization: Engineering
        authorization_grant_type: client-credentials
        client_type: confidential
        state: present
      register: app

    - name: Store application id for token creation
      set_fact:
        app_id: "{{ app.id }}"           # top-level id
```

### After (2.7.x)
```yaml
---
- name: OAuth application setup
  hosts: localhost
  connection: local
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Create OAuth application
      ansible.platform.application:
        name: CI Pipeline App
        organization: Engineering
        authorization_grant_type: client-credentials
        client_type: confidential
        state: present
      register: app

    - name: Store application details for token creation
      set_fact:
        app_id: "{{ app.application.id }}"              # changed
        app_client_id: "{{ app.client_id }}"              # new — flat at top level (NOT nested)
```
