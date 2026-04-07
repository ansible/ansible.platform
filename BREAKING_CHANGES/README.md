# Upgrade Guide — ansible.platform collection (ANSTRAT-1640 / 2.7.x)

## Who this document is for

Operators and automation engineers upgrading existing `ansible.platform`
playbooks from **AAP 2.6.x** to **AAP 2.7.x**.

---

## TL;DR — Do my playbooks break?

**No.** Existing 2.6 playbooks run against a 2.7 collection without any
changes required.

- All module names are unchanged.
- All argument names are unchanged (`gateway_hostname` is still accepted).
- Task result keys at the top level (`result.id`, `result.name`, etc.) are
  still present — the collection continues to spread resource fields flat
  alongside the new nested key for backward compatibility.
- `state: present`, `state: absent`, `state: exists` all behave as before.

The flat top-level keys are **deprecated** (scheduled for removal
after 2028-04-01). New playbooks should use `result.<module_name>.<field>`
(e.g. `result.user.id`), but there is no urgency — old patterns keep working.

---

## What is new in 2.7.x

| Area | Before (2.6.x) | After (2.7.x) |
|------|---------------|---------------|
| **Execution** | Module runs in the Ansible worker process | Action plugin + optional persistent manager process over a Unix socket |
| **Connection** | Always `connection: local` | `connection: local` (unchanged) or new `ansible.platform.http` persistent plugin |
| **Authentication** | Re-authenticates on every task | Once per play in persistent mode; unchanged in direct mode |
| **TLS** | New handshake every task | One handshake per play in persistent mode |
| **Result keys** | Flat only (`result.id`, `result.name`, …) | Flat keys still present (backward compat) **plus** new nested key `result.<module>.id`, `result.<module>.name`, … |
| **State: enforced** | Not supported | New — sets only the fields you specify; others keep current API values |
| **Idle timeout** | N/A | `aap_manager_idle_timeout` — auto-shuts down idle manager process |
| **Persistent mode** | N/A | `ansible_platform_use_persistent_connection: true` in inventory |

---

## Files in this folder

| File | Covers |
|------|--------|
| `01_result_structure.md` | Result key changes — nested dict and backward-compat flat keys |
| `02_connection_and_credentials.md` | Connection options and credential parameters |
| `09_new_features.md` | Persistent mode, idle timeout, API version detection, `state: enforced` |

---

## Optional migration (no deadline until 2028-04-01)

Once you are ready to adopt the new result structure in your playbooks:

- Prefer `result.<module_name>.<field>` over `result.<field>` in new tasks
  (e.g. `result.user.id` instead of `result.id`)
- Prefer `gateway_url:` over `gateway_hostname:` in task arguments
- Enable persistent mode for multi-task plays targeting remote gateways
  to benefit from the 40–60% latency reduction

---

## Versions

| Collection version | AAP version | Architecture |
|-------------------|-------------|--------------|
| ≤ 2.6.x | ≤ AAP 2.6 | Legacy (`aap_module.py`, direct HTTP) |
| 2.7.x | AAP 2.7 | New (action plugin + manager process, backward compatible) |
