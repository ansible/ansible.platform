# Breaking Change: Connection and credential configuration

## Affects

All modules. The change is in how you configure the gateway connection,
not in what the modules do.

---

## What changed

### 1. `gateway_hostname` → `gateway_url`

The primary credential variable was renamed from `gateway_hostname` to `gateway_url`.
Both are accepted in 2.7.x (backward compatible), but `gateway_url` is the
canonical name going forward.

### 2. Connection plugin (optional, new)

A new `ansible.platform.http` connection plugin is available. It is **not required**
— `connection: local` continues to work. The connection plugin enables persistent
mode (one manager process per play, fewer TLS handshakes).

### 3. Credential passing via `module_defaults` (recommended pattern)

The recommended pattern shifts from passing credentials on every task to using
`module_defaults` with the `ansible.platform.gateway` group, or setting credentials
in inventory host vars.

---

## Before (2.5.x) — credentials on every task

```yaml
---
- name: Manage platform resources
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:
    - name: Create organisation
      ansible.platform.organization:
        gateway_hostname: https://gateway.example.com    # on every task
        gateway_username: admin
        gateway_password: "{{ vault_gateway_password }}"
        gateway_validate_certs: false
        name: "Engineering"
        state: present
      register: org_result

    - name: Create user
      ansible.platform.user:
        gateway_hostname: https://gateway.example.com    # repeated again
        gateway_username: admin
        gateway_password: "{{ vault_gateway_password }}"
        gateway_validate_certs: false
        username: jdoe
        email: jdoe@example.com
        state: present
      register: user_result
```

---

## After (2.7.x) — credentials in inventory, connection via module_defaults

### Option A: `connection: local` (unchanged behaviour, no migration needed)

```yaml
---
- name: Manage platform resources
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:
    - name: Create organisation
      ansible.platform.organization:
        gateway_url: https://gateway.example.com         # gateway_url preferred
        gateway_username: admin
        gateway_password: "{{ vault_gateway_password }}"
        gateway_validate_certs: false
        name: "Engineering"
        state: present
      register: org_result
```

### Option B: credentials via `module_defaults` group (recommended)

```yaml
---
- name: Manage platform resources
  hosts: localhost
  connection: local
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_gateway_password }}"
      gateway_validate_certs: false

  tasks:
    - name: Create organisation
      ansible.platform.organization:
        name: "Engineering"                              # no credentials needed
        state: present
      register: org_result

    - name: Create user
      ansible.platform.user:
        username: jdoe
        email: jdoe@example.com
        state: present
      register: user_result
```

### Option C: credentials in inventory (recommended for persistent mode)

```yaml
# inventory/host_vars/gateway.example.com.yml
ansible_connection: ansible.platform.http
ansible_platform_use_persistent_connection: true

gateway_url: https://gateway.example.com
gateway_username: admin
gateway_password: "{{ vault_gateway_password }}"
gateway_validate_certs: false
aap_manager_idle_timeout: 600      # manager shuts down after 10 min idle
```

```yaml
---
# playbook.yml
- name: Manage platform resources
  hosts: gateway.example.com       # targets the gateway inventory host
  gather_facts: false

  tasks:
    - name: Create organisation
      ansible.platform.organization:
        name: "Engineering"
        state: present
      register: org_result

    - name: Create user
      ansible.platform.user:
        username: jdoe
        email: jdoe@example.com
        state: present
      register: user_result
```

---

## Credential variable name reference

All old names continue to work. New canonical names are listed first.

| Purpose | Canonical (2.7.x) | Aliases (still work) |
|---------|------------------|----------------------|
| Gateway URL | `gateway_url` | `gateway_hostname`, `aap_hostname` |
| Username | `gateway_username` | `aap_username` |
| Password | `gateway_password` | `aap_password` |
| OAuth token | `gateway_token` | `aap_token` |
| TLS verification | `gateway_validate_certs` | `aap_validate_certs`, `validate_certs` |
| Request timeout | `gateway_request_timeout` | `aap_request_timeout`, `request_timeout` |
| Manager idle timeout | `aap_manager_idle_timeout` | *(new, no alias)* |

---

## Automation Controller — credential injector mapping

If your job templates use a **Gateway credential type**, verify that the
credential injector maps to the variable names above. The recommended
injector configuration for 2.7.x:

```yaml
# Credential type injector (extra_vars)
extra_vars:
  gateway_url: "{{ gateway_hostname }}"
  gateway_username: "{{ username }}"
  gateway_password: "{{ password }}"
  gateway_validate_certs: "{{ verify_ssl }}"
```
