#!/usr/bin/env bash
# Enforce SDK execution invariants: no HTTP in action plugins.
# See docs/09-agent-collaboration.md §10 and docs/05-design-principles.md §3a.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION_DIR="${ROOT}/plugins/action"

if ! command -v rg >/dev/null 2>&1; then
    echo "ERROR: ripgrep (rg) is required to run check_action_plugin_invariants" >&2
    exit 1
fi

PATTERN='manager\.session|import requests|from requests import|from requests\.'

if rg -q "${PATTERN}" "${ACTION_DIR}"; then
    echo "ERROR: Action plugins must not perform HTTP directly." >&2
    echo "Use PlatformService.execute() and transform mixins instead." >&2
    echo "See docs/09-agent-collaboration.md section 10." >&2
    rg -n "${PATTERN}" "${ACTION_DIR}" >&2 || true
    exit 1
fi

echo "check_action_plugin_invariants: OK"
