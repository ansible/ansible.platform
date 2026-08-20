#!/usr/bin/env bash
# Enforce SDK execution invariants in action plugins.
# See docs/09-agent-collaboration.md §10 and docs/05-design-principles.md §3a.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION_DIR="${ROOT}/plugins/action"

if [[ ! -d "${ACTION_DIR}" ]]; then
    echo "ERROR: Action plugin directory not found: ${ACTION_DIR}" >&2
    exit 1
fi

# grep -R: status 0 = match, 1 = no match, 2+ = error (fail closed).
grep_action_plugins() {
    local pattern="$1"
    local matches=""
    local status=0
    matches="$(grep -R -n -E "${pattern}" "${ACTION_DIR}" --include='*.py' 2>/dev/null)" || status=$?
    if [[ "${status}" -ge 2 ]]; then
        echo "ERROR: Failed to scan ${ACTION_DIR} for pattern: ${pattern}" >&2
        exit 1
    fi
    if [[ -n "${matches}" ]]; then
        printf '%s\n' "${matches}"
    fi
}

# Invariant 2: no direct HTTP in action plugins.
HTTP_PATTERN='manager\.session|import requests|from requests import|from requests\.'
HTTP_MATCHES="$(grep_action_plugins "${HTTP_PATTERN}")"

if [[ -n "${HTTP_MATCHES}" ]]; then
    echo "ERROR: Action plugins must not perform HTTP directly." >&2
    echo "Use PlatformService.execute() and transform mixins instead." >&2
    echo "See docs/09-agent-collaboration.md section 10 (invariant 2)." >&2
    printf '%s\n' "${HTTP_MATCHES}" >&2
    exit 1
fi

# Invariant 7: job wait/poll logic belongs in PlatformService, not action plugins.
# base_action.py may use time.sleep for process lifecycle (not API polling).
POLL_PATTERN='_wait_for|wait_for_completion'
sleep_action_plugins() {
    local matches=""
    local status=0
    matches="$(grep -R -n -E 'time\.sleep' "${ACTION_DIR}" --include='*.py' 2>/dev/null)" || status=$?
    if [[ "${status}" -ge 2 ]]; then
        echo "ERROR: Failed to scan ${ACTION_DIR} for time.sleep" >&2
        exit 1
    fi
    if [[ -n "${matches}" ]]; then
        printf '%s\n' "${matches}" | grep -v 'plugins/action/base_action.py:' || true
    fi
}

POLL_MATCHES="$(grep_action_plugins "${POLL_PATTERN}")"
POLL_MATCHES="$(printf '%s\n' "${POLL_MATCHES}" | grep -v 'plugins/action/base_action.py:' || true)"

SLEEP_MATCHES="$(sleep_action_plugins)"

if [[ -n "${POLL_MATCHES}" || -n "${SLEEP_MATCHES}" ]]; then
    echo "ERROR: Action plugins must not implement job wait/poll logic." >&2
    echo "Move wait, interval, and timeout handling to PlatformService.execute()" >&2
    echo "(shared wait_for_completion helper). See docs/09-agent-collaboration.md" >&2
    echo "section 10 (invariant 7) and docs/07-adding-resources.md section 4c." >&2
    echo "Example: https://github.com/ansible/ansible.platform/pull/227" >&2
    if [[ -n "${POLL_MATCHES}" ]]; then
        printf '%s\n' "${POLL_MATCHES}" >&2
    fi
    if [[ -n "${SLEEP_MATCHES}" ]]; then
        printf '%s\n' "${SLEEP_MATCHES}" >&2
    fi
    exit 1
fi

echo "check_action_plugin_invariants: OK"
