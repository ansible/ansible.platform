# Breaking Changes — ansible.platform collection (ANSTRAT-1640 / 2.7.x)

## Who this document is for

Operators and automation engineers who have existing playbooks targeting
**Ansible Automation Platform 2.5.x or earlier** using the `ansible.platform`
collection and who are migrating to **AAP 2.7.x**.

---

## TL;DR — Do my playbooks break?

**Mostly no.** All module names, argument names, and credential variable names
are unchanged. Existing playbooks continue to run without modification under
`connection: local`.

However, **the task result structure changed** for every module. If your
playbooks or roles reference `result.id`, `result.changed`, or any top-level
result key other than `changed`, they will need updating.

See the table below and the per-module files for the exact before/after.

---

## What changed — summary

| Area | Before (2.5.x) | After (2.7.x) |
|------|---------------|---------------|
| **Execution** | Module runs directly in the Ansible worker process, makes HTTP calls via `ansible.module_utils.urls.Request` | Action plugin intercepts the module, delegates to a persistent manager process over a Unix socket |
| **Connection** | Always `connection: local` | `connection: local` (still works) or new `ansible.platform.http` plugin |
| **Authentication** | Re-authenticates on every task | Authenticates once per play (persistent mode) or per task (direct mode) |
| **TLS** | New TLS handshake every task | One handshake per play (persistent mode) |
| **Result keys** | `changed`, `id` at top level | `changed` at top level, resource data nested under a module-named key (e.g. `result.user`, `result.organization`) |
| **State: exists** | Returned `id` at top level | Returns full resource dict under module-named key, no change recorded |
| **State: enforced** | Not supported | Supported — omitted fields are reset to API defaults |
| **New option: idle_timeout** | Not present | `aap_manager_idle_timeout` controls manager process lifetime |
| **New option: persistent mode** | Not present | `ansible_platform_use_persistent_connection: true` in inventory |

---

## Files in this folder

| File | Covers |
|------|--------|
| `01_result_structure.md` | The universal change — result keys for every module |
| `02_connection_and_credentials.md` | How to configure connection, credentials, and inventory |
| `09_new_features.md` | Persistent mode, idle timeout, API version detection |

---

## Quick migration checklist

- [ ] Update any `register` result references from `result.id` → `result.<module_name>.id`
- [ ] Update any references to top-level fields like `result.username` → `result.user.username`
- [ ] Test `state: exists` tasks — they now return a full resource dict, not just `id`
- [ ] If using persistent mode: add `ansible_connection: ansible.platform.http` and
      `ansible_platform_use_persistent_connection: true` to inventory
- [ ] Review `aap_manager_idle_timeout` for playbooks with long pauses between tasks

---

## Versions

| Collection version | AAP version | Architecture |
|-------------------|-------------|--------------|
| ≤ 2.5.x | ≤ AAP 2.5 | Legacy (`aap_module.py`, direct HTTP) |
| 2.7.x | AAP 2.7 | New (action plugin + manager process) |
