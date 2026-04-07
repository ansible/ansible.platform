# New features in 2.7.x (ANSTRAT-1640)

These features are entirely new and do not break existing playbooks.
They are documented here so testathon participants know what to exercise.

---

## 1. Persistent connection mode

### What it is

A single manager process is reused across all tasks in a play. Eliminates
repeated TLS handshakes and re-authentication between tasks. Benchmark
shows 40-60% latency reduction on multi-task playbooks against remote gateways.

### How to enable

```yaml
# inventory/host_vars/gateway.example.com.yml
ansible_connection: ansible.platform.http
ansible_platform_use_persistent_connection: true

gateway_url: https://gateway.example.com
gateway_username: admin
gateway_password: "{{ vault_pw }}"
gateway_validate_certs: true
aap_manager_idle_timeout: 600
```

```yaml
# playbook.yml
- name: Platform setup
  hosts: gateway.example.com
  gather_facts: false

  tasks:
    - name: Create org          # manager spawned here, reused below
      ansible.platform.organization:
        name: Engineering
        state: present

    - name: Create team         # same manager, no new TLS handshake
      ansible.platform.team:
        name: Backend
        organization: Engineering
        state: present

    - name: Create user         # same manager again
      ansible.platform.user:
        username: jdoe
        email: jdoe@example.com
        state: present
```

### Cacheable facts

When a persistent manager is spawned, the following facts are set
on the host and cached across tasks:

```yaml
platform_manager_socket: /tmp/ansible_platform/abc123.sock
platform_manager_authkey: base64encodedkey==
gateway_url: https://gateway.example.com
```

These allow the next task to reuse the same manager process without
spawning a new one. Do not pass these as task arguments — they are
managed automatically.

---

## 2. Idle timeout for the manager process

### What it is

The persistent manager process automatically shuts down after a
configurable period of inactivity. Prevents stale background processes
accumulating on the Ansible controller.

### Configuration

```yaml
# inventory/host_vars/gateway.example.com.yml
aap_manager_idle_timeout: 600     # shut down after 10 min idle (default)
aap_manager_idle_timeout: 0       # never auto-shutdown (not recommended)
aap_manager_idle_timeout: 1800    # keep alive for 30 min between tasks
```

Or per-task (overrides inventory):
```yaml
- name: Long-running task
  ansible.platform.user:
    username: jdoe
    state: present
    aap_manager_idle_timeout: 3600   # this task needs manager alive for 1h
```

### What counts as "activity"

The idle clock resets on every API call the manager makes, including:
- Resource operations (create, update, delete, find)
- Token refresh operations

The idle clock does **not** reset during Ansible play pauses
(e.g. `ansible.builtin.pause`, `ansible.builtin.wait_for`). If your
playbook has long pauses between platform tasks, raise `aap_manager_idle_timeout`
to cover the longest expected gap.

---

## 3. API version auto-detection

The collection now detects whether your gateway supports API v1 or v2
and selects the correct endpoints automatically. No configuration required.

The detected version is included in every task result:
```json
{
    "changed": false,
    "user": { ... },
    "api_version": "1"
}
```

---

## 4. State: enforced (new)

Sets only the fields you specify. Other fields retain their current values.
Useful for ensuring specific attributes without risk of overwriting unrelated settings.

```yaml
# Ensure superuser is disabled — leave all other user fields untouched
- name: Revoke superuser
  ansible.platform.user:
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
        "email": "jdoe@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "is_superuser": false
    }
}
```

---

## 5. Performance timing in results

Every task result now includes:
- `elapsed_ms` — total API operation time in milliseconds
- `api_version` — API version used

Useful for benchmarking and performance regression detection.

```yaml
- name: Create organisation
  ansible.platform.organization:
    name: Engineering
    state: present
  register: result

- debug:
    msg: "Operation took {{ result.elapsed_ms }}ms using API v{{ result.api_version }}"
```

---

## Testathon scenarios to exercise

| Scenario | What to verify |
|----------|---------------|
| Persistent mode — multi-task play | Manager spawned once, reused across 5+ tasks |
| Persistent mode — token refresh | Manager survives token expiry mid-play without dying |
| Idle timeout fires | Set `aap_manager_idle_timeout: 30`, pause 35s, next task spawns a new manager |
| Idle timeout disabled | Set `aap_manager_idle_timeout: 0`, play completes, manager process still running |
| `connection: local` unchanged | Old-style playbook runs without any modification |
| `state: enforced` | Only specified field changes, others preserved |
| Stale socket recovery | Kill manager PID manually, next task auto-recovers |
| Loop tasks in http-direct mode | All loop iterations succeed (regression: KeyError in multiprocessing) |
| Credential safety | `/tmp/ansible_platform_manager_started.txt` contains no plaintext passwords |
