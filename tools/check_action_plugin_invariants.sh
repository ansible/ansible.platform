#!/usr/bin/env bash
# Enforce SDK execution invariants: no HTTP in action plugins.
# See docs/09-agent-collaboration.md §10 and docs/05-design-principles.md §3a.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION_DIR="${ROOT}/plugins/action"
PATTERN='manager\.session|import requests|from requests import|from requests\.'

MATCHES="$(grep -R -n -E "${PATTERN}" "${ACTION_DIR}" --include='*.py' 2>/dev/null || true)"

if [[ -n "${MATCHES}" ]]; then
    echo "ERROR: Action plugins must not perform HTTP directly." >&2
    echo "Use PlatformService.execute() and transform mixins instead." >&2
    echo "See docs/09-agent-collaboration.md section 10." >&2
    printf '%s\n' "${MATCHES}" >&2
    exit 1
fi

echo "check_action_plugin_invariants: OK"
