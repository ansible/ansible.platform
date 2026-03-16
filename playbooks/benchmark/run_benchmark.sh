#!/usr/bin/env bash
# Run benchmark: create N users in direct vs persistent mode and report timings.
# Also runs 06_test_all_operations.yml to verify all user operations:
#   present (create/update, idempotent), absent (delete, idempotent),
#   exists (read-only find), enforced (merge + update, can clear optional fields).
# Usage (from ansible/platform collection root):
#   ./playbooks/benchmark/run_benchmark.sh [user_count] [mode] [verbose]
#   mode: direct | persistent | both (default: both)
#   verbose: optional -v, -vv, -vvv, or set BENCHMARK_VERBOSE=-v (or -vv, -vvv)
#   RUN_WITH_LOCAL=1: also run same playbook tasks with connection: local (ephemeral manager).
# Examples:
#   ./playbooks/benchmark/run_benchmark.sh              # 20 users, both modes
#   ./playbooks/benchmark/run_benchmark.sh 50            # 50 users, both modes
#   ./playbooks/benchmark/run_benchmark.sh 100 direct    # 100 users, direct only
#   RUN_WITH_LOCAL=1 ./playbooks/benchmark/run_benchmark.sh 10 both  # same tasks with connection local too
#   BENCHMARK_VERBOSE=-vv ./playbooks/benchmark/run_benchmark.sh 10
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLECTION_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VARS_FILE="$SCRIPT_DIR/vars.yml"
USER_COUNT="${1:-20}"
MODE="${2:-both}"
# Verbose: third arg (-v, -vv, -vvv) or BENCHMARK_VERBOSE env
if [[ "$3" == -v || "$3" == -vv || "$3" == -vvv ]]; then
  VERBOSE_OPT=("$3")
elif [[ -n "${BENCHMARK_VERBOSE}" ]]; then
  VERBOSE_OPT=("${BENCHMARK_VERBOSE}")
else
  VERBOSE_OPT=()
fi
REPORT_FILE="${BENCHMARK_REPORT_FILE:-$SCRIPT_DIR/benchmark_report.txt}"
# Stats file written by connection plugin when BENCHMARK_STATS_FILE is set (POC session counts)
STATS_FILE="${BENCHMARK_STATS_FILE:-$SCRIPT_DIR/benchmark_stats.json}"

# Normalize mode to lowercase (portable)
MODE="$(echo "$MODE" | tr '[:upper:]' '[:lower:]')"

if [[ "$MODE" != "direct" && "$MODE" != "persistent" && "$MODE" != "both" ]]; then
  echo "ERROR: mode must be 'direct', 'persistent', or 'both' (got: $MODE)"
  echo "Usage: $0 [user_count] [mode] [verbose]"
  echo "  verbose: optional -v, -vv, -vvv (or set BENCHMARK_VERBOSE)"
  exit 1
fi

cd "$COLLECTION_ROOT"

if [[ ! -f "$VARS_FILE" ]]; then
  echo "ERROR: vars.yml not found at $VARS_FILE"
  exit 1
fi

EXTRA_VARS=(-e "@$VARS_FILE" -e "benchmark_user_count=$USER_COUNT")
echo "=== Benchmark: create $USER_COUNT users (mode: $MODE) ==="
echo "Collection root: $COLLECTION_ROOT"
echo "Report file: $REPORT_FILE"
echo ""

# Step 1: Remove all users except admin (force local connection - uses uri, not platform)
echo "--- Step 1: Cleanup all users except admin ---"
ansible-playbook playbooks/benchmark/01_cleanup_all_except_admin.yml "${EXTRA_VARS[@]}" -e ansible_connection=local "${VERBOSE_OPT[@]}"
echo ""

run_create_and_cleanup() {
  local mode_name="$1"
  local persistent_flag="$2"
  # Echo to stderr so only the numeric duration is captured when we assign TIME_*=$(run_create_and_cleanup ...)
  echo "--- Create $USER_COUNT users ($mode_name) ---" >&2
  echo '{"http_sessions":0,"tls_sessions":0}' > "$STATS_FILE"
  export BENCHMARK_STATS_FILE="$STATS_FILE"
  START=$(python3 -c "import time; print(time.time())")
  # Send playbook stdout to stderr so only the duration is captured in TIME_* below
  ansible-playbook playbooks/benchmark/02_create_users.yml "${EXTRA_VARS[@]}" -e "ansible_platform_persistent=$persistent_flag" "${VERBOSE_OPT[@]}" 1>&2
  END=$(python3 -c "import time; print(time.time())")
  echo "--- Test all operations: present, absent, exists, enforced ($mode_name) ---" >&2
  ansible-playbook playbooks/benchmark/06_test_all_operations.yml "${EXTRA_VARS[@]}" -e "ansible_platform_persistent=$persistent_flag" "${VERBOSE_OPT[@]}" 1>&2
  python3 -c "print(round($END - $START, 2))"
}

# Read session counts from stats file written by connection plugin (POC)
read_benchmark_stats() {
  local f="$1"
  if [[ -f "$f" ]]; then
    python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as fp:
        d = json.load(fp)
    print(d.get('http_sessions', 'N/A'), d.get('tls_sessions', 'N/A'))
except Exception:
    print('N/A', 'N/A')
" "$f"
  else
    echo "N/A N/A"
  fi
}

TIME_DIRECT=""
TIME_PERSISTENT=""
HTTP_DIRECT="" TLS_DIRECT=""
HTTP_PERSISTENT="" TLS_PERSISTENT=""

if [[ "$MODE" == "direct" || "$MODE" == "both" ]]; then
  TIME_DIRECT=$(run_create_and_cleanup "DIRECT mode" "false")
  read -r HTTP_DIRECT TLS_DIRECT <<< "$(read_benchmark_stats "$STATS_FILE")"
  echo "Direct mode: ${TIME_DIRECT}s (HTTP sessions: $HTTP_DIRECT, TLS sessions: $TLS_DIRECT)"
  echo "--- Cleanup $USER_COUNT users (after direct run) ---"
  ansible-playbook playbooks/benchmark/03_cleanup_bench_users.yml "${EXTRA_VARS[@]}" -e ansible_platform_persistent=false "${VERBOSE_OPT[@]}"
  echo ""
fi

if [[ "$MODE" == "persistent" || "$MODE" == "both" ]]; then
  TIME_PERSISTENT=$(run_create_and_cleanup "PERSISTENT mode" "true")
  read -r HTTP_PERSISTENT TLS_PERSISTENT <<< "$(read_benchmark_stats "$STATS_FILE")"
  echo "Persistent mode: ${TIME_PERSISTENT}s (HTTP sessions: $HTTP_PERSISTENT, TLS sessions: $TLS_PERSISTENT)"
  echo "--- Cleanup $USER_COUNT users (after persistent run) ---"
  ansible-playbook playbooks/benchmark/03_cleanup_bench_users.yml "${EXTRA_VARS[@]}" -e ansible_platform_persistent=true "${VERBOSE_OPT[@]}"
  echo ""
fi

# Optional: run same playbook tasks with connection: local (ephemeral manager)
CONNECTION_LOCAL_OK=""
if [[ -n "${RUN_WITH_LOCAL:-}" && "${RUN_WITH_LOCAL}" != "0" ]]; then
  echo "=== Run same playbook tasks with connection: local (ephemeral manager) ==="
  echo "--- Create $USER_COUNT users (connection=local) ---"
  if ansible-playbook playbooks/benchmark/02_create_users.yml "${EXTRA_VARS[@]}" -e ansible_connection=local "${VERBOSE_OPT[@]}"; then
    echo "--- Test all operations (connection=local) ---"
    if ansible-playbook playbooks/benchmark/06_test_all_operations.yml "${EXTRA_VARS[@]}" -e ansible_connection=local "${VERBOSE_OPT[@]}"; then
      echo "--- Cleanup $USER_COUNT users (connection=local) ---"
      if ansible-playbook playbooks/benchmark/03_cleanup_bench_users.yml "${EXTRA_VARS[@]}" -e ansible_connection=local "${VERBOSE_OPT[@]}"; then
        CONNECTION_LOCAL_OK="OK"
        echo "Connection local (ephemeral): OK"
      fi
    fi
  fi
  if [[ -z "$CONNECTION_LOCAL_OK" ]]; then
    CONNECTION_LOCAL_OK="FAILED"
    echo "Connection local (ephemeral): FAILED" >&2
  fi
  echo ""
fi

# Report (session counts from POC connection plugin when BENCHMARK_STATS_FILE was set)
{
  echo "=============================================="
  echo "Benchmark report: create $USER_COUNT users (mode=$MODE)"
  echo "=============================================="
  if [[ -n "$TIME_DIRECT" ]]; then
    echo "Direct mode (ephemeral manager per task): ${TIME_DIRECT}s"
    echo "  HTTP sessions: ${HTTP_DIRECT:-N/A}  TLS sessions: ${TLS_DIRECT:-N/A}"
  fi
  if [[ -n "$TIME_PERSISTENT" ]]; then
    echo "Persistent mode (reused manager):         ${TIME_PERSISTENT}s"
    echo "  HTTP sessions: ${HTTP_PERSISTENT:-N/A}  TLS sessions: ${TLS_PERSISTENT:-N/A}"
  fi
  if [[ -n "$TIME_DIRECT" && -n "$TIME_PERSISTENT" ]] && command -v python3 &>/dev/null; then
    echo ""
    RATIO=$(python3 -c "
d = $TIME_DIRECT
p = $TIME_PERSISTENT
if p > 0:
    print(round(d / p, 2))
else:
    print('N/A')
")
    echo "Speedup (direct / persistent): ${RATIO}x"
    SAVED=$(python3 -c "print(round($TIME_DIRECT - $TIME_PERSISTENT, 2))")
    echo "Time saved with persistent:    ${SAVED}s"
  fi
  if [[ -n "$CONNECTION_LOCAL_OK" ]]; then
    echo ""
    echo "Connection local (same tasks, ephemeral manager): $CONNECTION_LOCAL_OK"
  fi
  echo "=============================================="
} | tee "$REPORT_FILE"
echo ""
echo "Report written to: $REPORT_FILE"
if [[ -n "${RUN_WITH_LOCAL:-}" && "${RUN_WITH_LOCAL}" != "0" && "$CONNECTION_LOCAL_OK" == "FAILED" ]]; then
  exit 1
fi
