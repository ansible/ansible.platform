# Migration guide: Gateway HTTP connection (AAP 2.7 / `ansible.platform`)

This guide helps you move playbooks and inventory to the supported **HTTP connection plugin** for Ansible Automation Platform Gateway traffic, configure **credentials** and **connection behavior**, and choose **persistent** versus **direct** mode.

Confirm the `ansible.platform` collection version and Red Hat release notes for your environment; details here apply to automation targeting **Ansible Automation Platform 2.7** and the collection version bundled or pinned with that release.

---

## What changed (for users)

- The collection recommends **`ansible_connection: ansible.platform.http`** for hosts that represent the Gateway API endpoint. That connection type supports **direct** mode (default, new HTTP work per task) and **persistent** mode (reuse across tasks in a play for fewer round-trips).
- Existing playbooks that use **`connection: local`** (or default local) and pass Gateway options on tasks **continue to work** for modules that ship with a matching action plugin. You can migrate inventories gradually.

---

## Before and after

### Before: local connection and task-level API variables

Typical pattern: run against `localhost` with **`ansible_connection: local`** (or implicit local) and pass hostname and auth on each task using `aap_*` names (or equivalent module parameters).

```yaml
# inventory.yml - before
all:
  hosts:
    localhost:
      ansible_connection: local

---
# playbook.yml - before
- name: Manage AAP resources
  hosts: localhost
  gather_facts: false
  tasks:
    - name: Example task
      ansible.platform.organization:
        name: Ansible
        state: present
        aap_hostname: https://gateway.example.com
        aap_username: admin
        aap_password: "{{ vault_aap_password }}"
```

### After: Gateway host with the platform HTTP connection plugin

Recommended pattern: define an inventory host (or group) for the Gateway, set **`ansible_connection: ansible.platform.http`**, put **stable** settings in **inventory or group_vars** (`gateway_*` / `aap_*` as supported by the modules), and keep task bodies focused on resource arguments.

```yaml
# inventory.yml - after
all:
  children:
    gateway:
      hosts:
        aap_gateway:
          ansible_host: gateway.example.com
          ansible_connection: ansible.platform.http
          # Optional: reuse one client across tasks in the play (see "Persistent vs direct")
          ansible_platform_use_persistent_connection: true

---
# group_vars/gateway.yml - after (example)
gateway_url: https://gateway.example.com
gateway_username: admin
gateway_password: "{{ vault_gateway_password }}"
gateway_validate_certs: true

---
# playbook.yml - after
- name: Manage AAP resources
  hosts: aap_gateway
  gather_facts: false
  tasks:
    - name: Example task
      ansible.platform.organization:
        name: Engineering
        state: present
```

You can mix styles during migration (for example, keep `localhost` + `local` in one playbook and use `ansible.platform.http` in another) while you validate **Automation Controller** job templates and credentials.

---

## Configure credentials

Supply Gateway **base URL** and **authentication** using variables that your modules accept. Common names (see individual module documentation for the full list and aliases):

| What you need | Typical variables |
|---------------|-------------------|
| Gateway URL | `gateway_url` or `gateway_hostname` |
| Username / password | `gateway_username` / `gateway_password`, or `aap_username` / `aap_password` |
| OAuth token | `gateway_token` or `aap_token` (per module docs) |
| TLS / HTTP | `gateway_validate_certs`, `gateway_request_timeout` (and `aap_*` aliases where documented) |

**Automation Controller:** map **credentials** or **extra variables** so these keys are available to the playbook for the host that runs the Gateway tasks (either the dedicated Gateway inventory host or `localhost`, depending on your layout). Align credential injectors with the variable names your playbooks use (`gateway_*` and/or `aap_*`).

---

## Connection settings: persistent vs direct

| Mode | When to use | How users enable it |
|------|-------------|---------------------|
| **Direct** (default) | Simple playbooks, or when you want each task to use a fresh client | Use `ansible.platform.http` with persistent mode **off** (default). |
| **Persistent** | Multiple tasks against the same Gateway in one play; fewer TLS/auth round-trips | Turn persistent mode **on** using one of the options below. |

You can enable persistent mode in several equivalent ways (use whichever fits your Ansible config):

1. Connection option **`persistent: true`** for the `ansible.platform.http` plugin (see the plugin's documentation under `ansible-doc -t connection ansible.platform.http`).
2. Host or task variable **`ansible_platform_use_persistent_connection: true`**.
3. Host or task variable **`ansible_platform_persistent: true`**.
4. Environment variable **`ANSIBLE_PLATFORM_PERSISTENT`**.
5. Ansible INI: **`[platform_connection]`** section, key **`persistent`** (see plugin documentation).

If none of these set persistent mode, behavior defaults to **direct** (non-persistent).

Truthy values are accepted as boolean `true` or common string forms such as `yes` / `true` / `1` (see the connection plugin documentation).

**Changing** Gateway URL or credentials **changes** which logical connection is used; do not expect reuse across different URLs or identities.

---

## Inventory and playbook parameters

**Inventory**

- Set **`ansible_connection: ansible.platform.http`** on the host (or group) that should use the Gateway connection plugin.
- Set **`ansible_host`** to a hostname or address suitable for your environment (the API target is still defined by `gateway_url` / `gateway_hostname` variables).
- Optional: set **`ansible_platform_use_persistent_connection`** (or **`ansible_platform_persistent`**) per host or group.

**Playbook / role variables**

- Prefer **group_vars**, **host_vars**, or **vars_files** for URL, credentials, TLS, and timeouts so job templates and vault stay consistent.
- Task parameters can still override or supplement variables when the module allows it - follow each module's documentation.

**Backward compatibility**

| Configuration | Persistent reuse across tasks in a play? |
|---------------|------------------------------------------|
| `ansible_connection: ansible.platform.http` and persistent **off** (default) | No |
| `ansible_connection: ansible.platform.http` and persistent **on** | Yes |
| `ansible_connection: local` (typical legacy) | Not via the HTTP connection plugin; behavior matches your current collection version |

---

## Migration checklist

- [ ] Add an inventory host (or group) for the Gateway and set **`ansible_connection: ansible.platform.http`**.
- [ ] Move or duplicate **`gateway_url`** / **`gateway_hostname`** and auth variables into inventory, **`group_vars`**, or Controller extra vars.
- [ ] Choose **persistent** vs **direct** and set **`ansible_platform_use_persistent_connection`** (or another supported switch) accordingly.
- [ ] Align **Automation Controller** credentials and injectors with the variable names your playbooks expect.
- [ ] Run your playbooks in a non-production environment and confirm results match the pre-migration behavior.

---

## Further reading

- [03-sdk-architecture.md](03-sdk-architecture.md) - architecture overview (persistent connection and manager lifecycle).
- [06-foundation-components.md](06-foundation-components.md) - framework components (for contributors and advanced troubleshooting).
