# Migration guide: persistent Gateway connections (AAP 2.7 / `ansible.platform`)

This document describes backward compatibility, the recommended migration path, and an optional phased deprecation plan for the **persistent manager / connection-plugin** work in the `ansible.platform` collection. It applies to automation targeting **Ansible Automation Platform 2.7** and the `ansible.platform` collection version bundled or pinned with that release.

Confirm the exact collection version and any Red Hat release notes for your environment; behavior described here follows the current collection implementation.

---

## What changed (summary)

- **Connection plugin `ansible.platform.http`** is the supported way to route Gateway traffic. It implements `get_client()`, which chooses **direct** (ephemeral manager per task) or **persistent** (reuse one manager process and HTTP session across tasks in a play) mode.
- **Action plugins** for platform modules call `_get_or_spawn_manager()`, which **prefers** the connection plugin's `get_client()` when `ansible_connection` is `ansible.platform.http`. They still work with **`ansible_connection: local`** by spawning an **ephemeral** manager (`spawn_ephemeral_client()`), but that path does **not** integrate with the connection plugin's persistent lifecycle or facts in the same way.
- **Direct mode** (default) still uses the same manager-based stack as persistent mode; the difference is **lifecycle** (new ephemeral manager per task vs reuse). Performance tuning is primarily about **persistent** mode and fewer TLS/auth round-trips.
- **Stale socket recovery**: when reusing a persistent manager, if the socket file exists but the process is gone, the connection plugin detects a **stale socket**, removes it, and spawns a new manager.

---

## Backward compatibility (today)

| Configuration | Behavior | Persistent reuse across tasks? |
|---------------|----------|--------------------------------|
| `ansible_connection: ansible.platform.http` and `persistent: false` (default) | Ephemeral manager per task via connection plugin | No |
| `ansible_connection: ansible.platform.http` and `persistent: true` (or equivalent vars, see below) | One manager per play/host/credential set; facts cache socket + authkey | Yes |

Existing playbooks that use **`connection: local`** and pass Gateway options continue to run **without** switching the connection plugin, as long as they use modules that have a matching **action plugin** (the normal case for resource modules in this collection).

---

## Migration path

### 1. Use the platform HTTP connection plugin (recommended)

Set the inventory host (or group vars) that represents the Gateway to use the collection connection plugin:

```yaml
# inventory.yml (example)
all:
  children:
    gateway_hosts:
      hosts:
        aap_gateway:
          ansible_host: gateway.example.com   # informational; API target is still gateway_url
          ansible_connection: ansible.platform.http
          # Optional: enable persistent mode for this host
          ansible_platform_use_persistent_connection: true
```

FQCN for the plugin transport is **`ansible.platform.http`** (see `transport` in `plugins/connection/http.py`).

### 2. Gateway URL and credentials

The action layer builds a `GatewayConfig` via `extract_gateway_config()` from **task arguments** and **host/task variables**. At minimum you must supply a Gateway base URL:

| Purpose | Task / host variables (priority order in code) |
|---------|------------------------------------------------|
| Gateway URL | `gateway_url` or `gateway_hostname` |
| Username / password | `gateway_username` / `gateway_password`, or aliases `aap_username` / `aap_password` |
| OAuth token | `gateway_token` or `aap_token` (with special handling so a module-created `aap_token` dict does not override user/password auth) |
| TLS / timeout | `gateway_validate_certs`, `gateway_request_timeout` (and `aap_*` aliases where documented in fragments) |

**Automation Controller (AAP) job templates:** map your **credential** or **extra variables** so the above keys are present for the Gateway host (or for `localhost` if you use a single inventory host for API tasks). The exact credential type and injectors depend on your Controller version; align injectors with the variable names this collection reads (`gateway_*` / `aap_*`).

### 3. Enabling persistent vs direct mode

Resolution order for **persistent** behavior (connection plugin `get_client()`):

1. Connection option **`persistent`** if Ansible supplies it for `ansible.platform.http` (for example via plugin configuration that maps to `get_option('persistent')`).
2. If that option is unset, **`ansible_platform_use_persistent_connection`** from host vars or task vars (and a host-var form under `hostvars[inventory_hostname]`).
3. Else **`ansible_platform_persistent`** (same scoping as above).
4. Else environment **`ANSIBLE_PLATFORM_PERSISTENT`**.
5. Else INI **`[platform_connection] persistent=`** (see plugin `DOCUMENTATION`).
6. Default: **false** (direct / ephemeral per task).

In practice, most playbooks use **`ansible_platform_use_persistent_connection`** or **`ansible_platform_persistent`** (as in integration and Molecule scenarios).

Truthy values are boolean `true` or strings `true`, `yes`, `1` (see `_truthy()` in the connection plugin).

When persistent mode spawns a manager, the action plugin result may include **cacheable facts**:

- `platform_manager_socket`
- `platform_manager_authkey`
- `gateway_url` (when returned by the connection plugin)

These allow the next task to reuse the same manager. Changing **URL or credentials** changes the derived socket identity; do not expect reuse across different Gateway identities.

### 4. Operational notes

- **Socket locations**: persistent managers use `$(TMPDIR or system temp)/ansible_platform/`; ephemeral paths used by direct mode may use short paths under `/tmp/ap/` (see connection plugin and `spawn_ephemeral_client()`).
- **AF_UNIX**: if Unix domain sockets are unavailable, the local fallback can use `DirectHTTPClient` without a manager process (see `spawn_ephemeral_client()`).
- **`platform_connection_mode`**: still parsed into `GatewayConfig` for compatibility; routing between persistent and direct is controlled by the **connection plugin** options/vars above, not by switching this field alone.

---

## Parallel support: modules and action plugins

- Platform **resource modules** in this collection are intended to run with their **action plugins**, which perform validation, manager acquisition, and API execution.
- **Parallel support** means you may keep **`connection: local`** during a transition while you test **`ansible.platform.http`** on staging inventories. Both paths use the manager architecture (except AF_UNIX fallback), but only the HTTP connection plugin provides **centralized** persistent vs direct policy and stale-socket handling aligned with connection-level configuration.

---

## Quick checklist

- [ ] Set `ansible_connection: ansible.platform.http` on the Gateway inventory host (or group).
- [ ] Supply `gateway_url` / `gateway_hostname` and auth (`gateway_username`/`gateway_password` or token vars).
- [ ] Decide on **persistent** (`ansible_platform_use_persistent_connection: true` or connection option `persistent: true`) vs **direct** (default).
- [ ] Validate job templates and credentials inject the same variable names your playbooks expect.
- [ ] After upgrade, run a multi-task playbook once with persistent mode and confirm fact-driven reuse (or benchmark latency improvement).

For architecture background, see `docs/03-sdk-architecture.md` and `docs/06-foundation-components.md` in this repository.
