# Persistent manager idle timeout

This document describes the **control-node** idle timeout for the persistent manager process: what it controls, how it is configured, which edge cases the implementation handles, and where those behaviors are tested.

---

## Scope


| Aspect             | Behavior                                                                                                                                                           |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **What it limits** | How long the **local** persistent manager process on the Ansible control node may remain idle (no RPC / API activity) before it exits and removes its Unix socket. |
| **What it is not** | It is **not** a gateway server session timeout. The value is not sent to the gateway as a session policy; it only affects the local subprocess lifecycle.          |
| **Default**        | **3600** seconds (one hour) when the option is unset.                                                                                                              |
| **Disable**        | Set `**persistent_manager_idle_timeout: 0`** to turn off idle-based shutdown of the persistent manager.                                                            |


---

## Configuration surface

Only one Ansible variable name is honored:

- `**persistent_manager_idle_timeout**` (float), in task arguments or host/inventory variables.

**Precedence:** task arguments override host/inventory variables.

**Extraction** uses `key in dict` checks (not `a or b` chains) so a configured value of `**0`** is never dropped in favor of a fallback.

Legacy or alternate names (for example `gateway_idle_timeout`) are **not** read; they have no effect on idle timeout.

---

## Issues and scenarios this implementation addresses

The following problems are explicitly covered by code and tests.

### 1. Single, unambiguous variable name

**Issue:** Multiple overlapping names suggested different semantics (“gateway” vs “platform manager”) and made docs and inventory hard to reason about.

**Behavior:** Only `persistent_manager_idle_timeout` is documented and parsed. Misnamed keys do not configure idle timeout.

**Tests:** `test_other_keys_do_not_set_idle_timeout` in `tests/unit/plugins/plugin_utils/test_extract_gateway_config_idle.py`.

---

### 2. Preserving `0` (no accidental fallback)

**Issue:** Patterns such as `task.get("x") or host.get("x")` treat `**0`** as falsy and incorrectly fall back to a default or host value, so “disable idle shutdown” could not be expressed reliably.

**Behavior:** Extraction checks membership (`"persistent_manager_idle_timeout" in task_args`) before reading the value, so `**0`** is preserved.

**Tests:**

- Task `0` → `idle_timeout` is `0.0` (`test_task_zero_disables_idle_shutdown`).
- Task `0` wins over host non-zero (`test_task_zero_wins_over_host_nonzero`).
- Host-only `0` when task omits the key (`test_host_zero_when_not_in_task`).

---

### 3. Sensible default when unset

**Issue:** Operators need predictable behavior when nothing is configured.

**Behavior:** If the key is absent from both task args and host vars, `**3600.0`** seconds is used.

**Tests:** `test_default_3600_when_unset`, `test_gateway_config_default_idle_timeout`.

---

### 4. Task vs inventory precedence

**Issue:** It must be clear whether a play-level override or inventory wins.

**Behavior:** Task arguments take precedence over host variables for `persistent_manager_idle_timeout`.

**Tests:** `test_task_zero_wins_over_host_nonzero`, `test_extract_gateway_config_idle_timeout_from_task_args`, `test_extract_gateway_config_idle_timeout_from_host_vars`.

---

### 5. Idle decision is time-based only

**Issue:** Idle shutdown must not depend on OAuth token validity or other auth state, or behavior becomes non-deterministic.

**Behavior:** `should_exit_for_idle()` is **purely time-based** (elapsed time since last recorded activity vs `idle_timeout`). Token validity does not change the boolean result for the same timestamps.

**Tests:** `test_should_exit_for_idle_same_result_for_valid_and_expired_token`, `test_should_exit_for_idle_false_within_threshold_regardless_of_token`.

---

### 6. Expired token does not “freeze” idle exit

**Issue:** If the token expires while there is no traffic, the manager should still exit after the idle interval.

**Behavior:** With no new `record_activity()`, idle timeout still fires regardless of token expiry or `oauth_token` being cleared.

**Tests:** `test_expired_token_alone_does_not_suppress_idle_exit`, `test_expired_token_does_not_prevent_idle_exit_when_no_traffic`.

---

### 7. User-facing requests reset the idle clock (including failures)

**Issue:** Activity should reflect “something tried to use the gateway,” including failed HTTP calls where the client still did work.

**Behavior:** `record_activity()` runs at the start of the request path (before the HTTP call), so a **401** still resets the idle timer for that attempt.

**Tests:** `test_401_response_still_resets_idle_timer`, `test_idle_not_exceeded_immediately_after_request_with_expired_token`.

---

### 8. Internal re-auth must not extend the idle lease

**Issue:** Background token refresh or re-authentication should not keep the manager alive when there is no real user/module traffic.

**Behavior:** `_re_authenticate()` and `_refresh_token()` (when not going through the normal request path that records activity) do **not** reset the idle timer.

**Tests:** `test_re_authenticate_alone_does_not_reset_idle_timer`, `test_refresh_token_alone_does_not_reset_idle_timer`.

---

### 9. Shutdown already requested

**Issue:** After a graceful shutdown is requested, the idle monitor should not keep driving exit logic in a confusing way.

**Behavior:** When shutdown has been requested, `should_exit_for_idle()` returns false (idle-based exit is not the path).

**Tests:** `test_should_exit_for_idle_false_after_shutdown_requested`.

---

### 10. Poll interval derived from timeout (no hidden env override)

**Issue:** The manager needs a check interval that scales with the configured timeout without requiring extra environment variables.

**Behavior:** `_compute_poll_interval(idle_timeout)` uses **10%** of `idle_timeout`, clamped to **[5, 60]** seconds. For `**idle_timeout <= 0`** (disabled), the returned interval is a fixed **60** s (the idle monitor path treats shutdown as disabled separately).

**Tests:** `TestComputePollInterval` in `tests/unit/plugins/plugin_utils/manager/test_manager_process_redaction.py`.

---

### 11. Subprocess receives idle timeout and defaults safely

**Issue:** The manager runs as a separate process with CLI arguments; the parent must pass the configured value and default the optional argument.

**Behavior:** `ProcessManager.spawn_manager_process` appends `gateway_config.idle_timeout` as the last argv element. The child parses an optional 10th argument and defaults to **3600.0** if missing.

**Tests:** `test_spawn_manager_includes_idle_timeout_in_command`.

---

### 12. Credential argv redaction (security)

**Issue:** Logging `sys.argv` must not leak username, password, or token.

**Behavior:** Positions **5, 6, 7** (username, password, token) are replaced with `<redacted>` in logged argv copies. The idle timeout value (position **10**) is not treated as a secret.

**Tests:** `test_manager_process_redaction.py` (`TestRedactArgv`, `TestSensitiveArgvPositions`).

---

### 13. End-to-end: manager exits after idle (integration)

**Issue:** The full stack (spawn → idle → socket removal) should be verifiable without a real gateway.

**Behavior:** The Molecule scenario `**extensions/molecule/idle_timeout_mock`** sets `persistent_manager_idle_timeout: 15` and asserts the manager exits and cleans up after the idle window.

---

## Quick reference: unit test modules


| Module                                                                      | Focus                                                                              |
| --------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `tests/unit/plugins/plugin_utils/test_extract_gateway_config_idle.py`       | Extraction, `0`, defaults, legacy keys ignored                                     |
| `tests/unit/plugins/plugin_utils/manager/test_platform_service_idle.py`     | `GatewayConfig`, `PlatformService` idle logic, OAuth/401/re-auth cases, argv spawn |
| `tests/unit/plugins/plugin_utils/manager/test_manager_process_redaction.py` | Poll interval math, argv redaction                                                 |


---

## Related user-facing documentation

- `plugins/doc_fragments/auth.py` — `persistent_manager_idle_timeout` option text for modules that include the auth fragment.

