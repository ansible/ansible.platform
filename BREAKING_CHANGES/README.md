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
| **Timing info** | Not present | `elapsed_ms` and `api_version` included in result |
| **New option: idle_timeout** | Not present | `aap_manager_idle_timeout` controls manager process lifetime |
| **New option: persistent mode** | Not present | `ansible_platform_use_persistent_connection: true` in inventory |

---

## Files in this folder

| File | Covers |
|------|--------|
| `01_result_structure.md` | The universal change — result keys for every module |
| `02_connection_and_credentials.md` | How to configure connection, credentials, and inventory |
| `03_module_user.md` | `ansible.platform.user` before/after |
| `04_module_organization.md` | `ansible.platform.organization` before/after |
| `05_module_team.md` | `ansible.platform.team` before/after |
| `06_module_application.md` | `ansible.platform.application` before/after |
| `07_module_role_assignments.md` | `role_user_assignment` and `role_team_assignment` before/after |
| `08_module_authenticator.md` | `authenticator` and `authenticator_map` before/after |
| `09_new_features.md` | Persistent mode, idle timeout, API version detection |
| `10_module_authenticator_user.md` | `ansible.platform.authenticator_user` — new in 2.7.x |
| `11_module_ca_certificate.md` | `ansible.platform.ca_certificate` — new in 2.7.x |
| `12_module_feature_flag.md` | `ansible.platform.feature_flag` — new in 2.7.x |
| `13_module_http_port.md` | `ansible.platform.http_port` — new in 2.7.x |
| `14_module_role_definition.md` | `ansible.platform.role_definition` — new in 2.7.x |
| `15_module_route.md` | `ansible.platform.route` — new in 2.7.x |
| `16_module_service.md` | `ansible.platform.service` — new in 2.7.x |
| `17_module_service_cluster.md` | `ansible.platform.service_cluster` — new in 2.7.x |
| `18_module_service_key.md` | `ansible.platform.service_key` — new in 2.7.x |
| `19_module_service_node.md` | `ansible.platform.service_node` — new in 2.7.x |
| `20_module_service_type.md` | `ansible.platform.service_type` — new in 2.7.x |
| `21_module_settings.md` | `ansible.platform.settings` before/after |
| `22_module_token.md` | `ansible.platform.token` before/after |
| `23_module_ui_plugin_route.md` | `ansible.platform.ui_plugin_route` — new in 2.7.x |

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
