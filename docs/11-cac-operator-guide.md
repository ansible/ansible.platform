# ansible.platform — Operator and CaC Author Guide

This guide is for **CaC content authors** writing `infra.*` roles or playbooks, and **AAP operators** managing an AAP instance using Ansible. If you are contributing to the collection itself, see [07-adding-resources.md](07-adding-resources.md).

---

## Prerequisites

| Requirement | Notes |
|---|---|
| AAP 2.6 or later | Gateway endpoint must be reachable from where Ansible runs |
| `ansible.platform` collection | `ansible-galaxy collection install ansible.platform` |
| Service account or OAuth token | Created in AAP → Access → Users or via `settings.py` bootstrap |
| Python 3.10+ | Required by the collection |

---

## Inventory and Credential Setup

The collection needs two pieces of information at runtime: where the gateway is and how to authenticate.

### Option 1 — `ansible.platform.http` connection plugin (recommended for long playbooks)

```ini
# inventory/hosts
[aap_gateway]
aap.example.com

[aap_gateway:vars]
ansible_connection=ansible.platform.http
gateway_hostname=https://aap.example.com
gateway_oauth_token={{ lookup('env', 'AAP_OAUTH_TOKEN') }}
```

This connection plugin keeps a persistent manager process alive across all tasks in a play, which is significantly faster than spawning a new HTTPS session per task.

### Option 2 — `connection: local` with `gateway_*` task vars (simple / CI use)

```yaml
- name: Manage AAP resources
  hosts: localhost
  connection: local
  vars:
    gateway_hostname: https://aap.example.com
    gateway_oauth_token: "{{ lookup('env', 'AAP_OAUTH_TOKEN') }}"
  tasks:
    - name: Ensure org exists
      ansible.platform.organization:
        name: MyOrg
        state: present
```

Each task in this mode creates a fresh HTTPS connection. Fine for short plays or CI pipelines where the overhead is acceptable.

### Credentials — What the collection accepts

| Variable | Description | Required |
|---|---|---|
| `gateway_hostname` | Base URL of the AAP gateway, e.g. `https://aap.example.com` | Yes |
| `gateway_oauth_token` | OAuth2 bearer token | One of these |
| `gateway_username` + `gateway_password` | Basic auth (service account) | One of these |
| `gateway_verify_ssl` | Set `false` to skip cert validation (dev only) | No, default `true` |

**Best practice:** Store credentials in an Ansible Vault file or pull them from AAP's own credential store via `ansible.builtin.lookup('env', ...)`. Never hardcode tokens in playbooks committed to source control.

---

## Writing Your First Playbook

A complete, idempotent playbook that creates an organization, a team, and assigns a user:

```yaml
---
- name: Bootstrap AAP organizations and teams
  hosts: localhost
  connection: local
  vars:
    gateway_hostname: "{{ lookup('env', 'AAP_HOSTNAME') }}"
    gateway_oauth_token: "{{ lookup('env', 'AAP_TOKEN') }}"

  tasks:
    - name: Ensure platform organization exists
      ansible.platform.organization:
        name: "Platform Engineering"
        description: "Manages platform tooling and AAP itself"
        state: present
      register: org_result

    - name: Ensure platform team exists
      ansible.platform.team:
        name: "Platform Admins"
        organization: "Platform Engineering"
        description: "Admins for the Platform Engineering org"
        state: present

    - name: Ensure service account user exists
      ansible.platform.user:
        username: "svc-platform-bot"
        first_name: "Platform"
        last_name: "Bot"
        email: "platform-bot@example.com"
        is_superuser: false
        state: present

    - name: Assign user to team
      ansible.platform.team_member:
        team: "Platform Admins"
        user: "svc-platform-bot"
        state: present
```

Run it:

```bash
export AAP_HOSTNAME=https://aap.example.com
export AAP_TOKEN=<your-oauth-token>
ansible-playbook bootstrap_aap.yml
```

Run it again — nothing changes. Every task is idempotent.

---

## Understanding Idempotency

The collection guarantees idempotency through its four states:

| State | What it does | `changed` if... |
|---|---|---|
| `present` | Creates if missing, updates if different | Object was created or any field changed |
| `absent` | Deletes if it exists | Object existed and was deleted |
| `exists` | Fails if the object does not exist; never modifies it | Never changes; use for conditional assertions |
| `enforced` | Like `present` but also removes child objects not in the task | Child objects were removed |

**Safe to run repeatedly in pipelines.** A fully converged environment produces zero `changed` tasks.

### What triggers `changed: true`

The collection compares the desired state from your task arguments against the current state returned by the AAP API. If any declared field differs, the API is called and `changed` is set.

**Exception — write-only fields:** Some fields (e.g., `password`, `client_secret`) are never returned by the API for security reasons. The collection cannot detect changes to these fields after initial creation. If you update a password and re-run, the task will report `changed: false` even though a change was made. This is a known AAP API limitation.

---

## Error Handling Patterns

### Check if a resource exists before acting on it

```yaml
- name: Check if organization exists
  ansible.platform.organization:
    name: "MyOrg"
    state: exists
  register: org_check
  failed_when: false   # don't fail the play if it doesn't exist

- name: Create org if it was missing
  ansible.platform.organization:
    name: "MyOrg"
    description: "Created by bootstrap playbook"
    state: present
  when: org_check.failed
```

### Handle expected failures gracefully

```yaml
- name: Remove user from team (may already be removed)
  ansible.platform.team_member:
    team: "Platform Admins"
    user: "departed-user"
    state: absent
  register: remove_result
  failed_when:
    - remove_result.failed
    - '"Not found" not in remove_result.msg'
```

---

## Reference-by-Name Convention

All relationship fields use **names, not numeric IDs**. The collection resolves names to IDs internally before calling the API.

```yaml
# Correct — use name
- ansible.platform.team:
    name: "Platform Admins"
    organization: "Platform Engineering"   # name, not organization_id: 42
    state: present

# Wrong — do not use internal IDs
- ansible.platform.team:
    name: "Platform Admins"
    organization_id: 42   # this field doesn't exist
    state: present
```

This means your playbooks are portable across AAP instances where the numeric IDs will differ.

---

## Connection Modes and Performance

### When to use the `ansible.platform.http` persistent connection

- Playbooks with **10 or more AAP tasks**
- Roles that run in a loop over many objects
- Any scenario where startup latency is noticeable

The persistent connection mode spawns a single manager process per play that stays alive across all tasks. Startup cost (~1–2 seconds) is paid once. Idle timeout defaults to 3600 seconds.

```ini
[aap_gateway:vars]
ansible_connection=ansible.platform.http
# Optional: tune idle timeout (seconds, 0 = never timeout)
persistent_manager_idle_timeout=1800
```

### When ephemeral (per-task) mode is fine

- Short playbooks with fewer than 5 AAP tasks
- CI pipelines running occasionally
- Tasks where you want strict isolation between operations

No configuration needed for ephemeral mode — `connection: local` gives you ephemeral behavior automatically.

---

## Integration with infra.* Collections

`ansible.platform` is the low-level resource management collection. If you are using an `infra.*` validated content collection that manages AAP (such as `infra.platform` or `infra.aap_configuration`), that collection likely uses `ansible.platform` under the hood.

**Declaring the dependency in your role or collection:**

```yaml
# meta/requirements.yml
collections:
  - name: ansible.platform
    version: ">=2.6.0"
```

**Mixing direct `ansible.platform` tasks with `infra.*` roles:**
This is fully supported. The `infra.*` role and your direct tasks share the same connection and manager process if both run in the same play against the same inventory host.

**Reporting integration issues:**
If you find a behavior difference between what `ansible.platform` documents and what you observe when called through an `infra.*` role, please open an issue on the `ansible.platform` repository and tag it `infra-compat`. See also [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## Troubleshooting

### `gateway_hostname` not set / connection refused

```
TASK [ansible.platform.organization] ****
fatal: [localhost]: FAILED! => {"msg": "gateway_hostname is required"}
```

Make sure `gateway_hostname` is set either as a task var, host var, or environment variable `GATEWAY_HOSTNAME`.

### SSL certificate errors

```
fatal: [localhost]: FAILED! => {"msg": "SSL: CERTIFICATE_VERIFY_FAILED"}
```

For development against self-signed certificates: set `gateway_verify_ssl: false`. For production: ensure your AAP gateway certificate is signed by a CA trusted by the Python environment running Ansible.

### `changed: true` on every run for the same task

Most common cause: a field is set in your task that the API returns in a different format. For example, if you pass `description: ""` (empty string) but the API returns `null` for unset descriptions, the collection sees a diff on every run.

Fix: omit optional fields from your task rather than setting them to empty strings. Let the API default apply.

### Task takes 5–10 seconds to start

You are likely using ephemeral mode (`connection: local`) and the manager process startup cost is showing. Switch to `ansible.platform.http` persistent connection for multi-task playbooks.

---

## Quick Reference

### Supported states

| State | Use when... |
|---|---|
| `present` | You want the object to exist with these attributes |
| `absent` | You want the object removed |
| `exists` | You want to assert the object exists without changing it |
| `enforced` | You want the object to exist AND remove any children not in your task |

### Environment variables

| Variable | Description |
|---|---|
| `GATEWAY_HOSTNAME` | Fallback for `gateway_hostname` |
| `GATEWAY_OAUTH_TOKEN` | Fallback for `gateway_oauth_token` |
| `GATEWAY_USERNAME` | Fallback for `gateway_username` |
| `GATEWAY_PASSWORD` | Fallback for `gateway_password` |
| `GATEWAY_VERIFY_SSL` | Fallback for `gateway_verify_ssl` |

### Getting help

- GitHub Issues: `ansible/ansible.platform`
- Slack: `#wg-ansible-platform-collection` on Red Hat Ansible Community Slack
- CaC integration questions: tag `@sean-m-sullivan` or `@djdanielsson` in issues
