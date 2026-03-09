#!/usr/bin/env bash
# Run benchmark: create N users in direct vs persistent mode and report timings.
# Usage (from ansible/platform collection root):
#   ./playbooks/benchmark/run_benchmark.sh [user_count] [mode]
#   mode: direct | persistent | both (default: both)
# Examples:
#   ./playbooks/benchmark/run_benchmark.sh              # 100 users, both modes
#   ./playbooks/benchmark/run_benchmark.sh 50            # 50 users, both modes
#   ./playbooks/benchmark/run_benchmark.sh 100 direct     # 100 users, direct only
#   ./playbooks/benchmark/run_benchmark.sh 100 persistent
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLECTION_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VARS_FILE="$SCRIPT_DIR/vars.yml"
USER_COUNT="${1:-20}"
MODE="${2:-both}"
REPORT_FILE="${BENCHMARK_REPORT_FILE:-$SCRIPT_DIR/benchmark_report.txt}"
# Stats file written by connection plugin when BENCHMARK_STATS_FILE is set (POC session counts)
STATS_FILE="${BENCHMARK_STATS_FILE:-$SCRIPT_DIR/benchmark_stats.json}"

# Normalize mode to lowercase (portable)
MODE="$(echo "$MODE" | tr '[:upper:]' '[:lower:]')"

if [[ "$MODE" != "direct" && "$MODE" != "persistent" && "$MODE" != "both" ]]; then
  echo "ERROR: mode must be 'direct', 'persistent', or 'both' (got: $MODE)"
  echo "Usage: $0 [user_count] [mode]"
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
ansible-playbook playbooks/benchmark/01_cleanup_all_except_admin.yml "${EXTRA_VARS[@]}" -e ansible_connection=local
echo ""

run_create_and_cleanup() {
  local mode_name="$1"
  local persistent_flag="$2"
  echo "--- Create $USER_COUNT users ($mode_name) ---"
  echo '{"http_sessions":0,"tls_sessions":0}' > "$STATS_FILE"
  export BENCHMARK_STATS_FILE="$STATS_FILE"
  START=$(python3 -c "import time; print(time.time())")
  # Send playbook stdout to stderr so only the duration is captured in TIME_* below
  ansible-playbook playbooks/benchmark/02_create_users.yml "${EXTRA_VARS[@]}" -e "ansible_platform_persistent=$persistent_flag" 1>&2
  END=$(python3 -c "import time; print(time.time())")
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
  ansible-playbook playbooks/benchmark/03_cleanup_bench_users.yml "${EXTRA_VARS[@]}" -e ansible_platform_persistent=false
  echo ""
fi

if [[ "$MODE" == "persistent" || "$MODE" == "both" ]]; then
  TIME_PERSISTENT=$(run_create_and_cleanup "PERSISTENT mode" "true")
  read -r HTTP_PERSISTENT TLS_PERSISTENT <<< "$(read_benchmark_stats "$STATS_FILE")"
  echo "Persistent mode: ${TIME_PERSISTENT}s (HTTP sessions: $HTTP_PERSISTENT, TLS sessions: $TLS_PERSISTENT)"
  echo "--- Cleanup $USER_COUNT users (after persistent run) ---"
  ansible-playbook playbooks/benchmark/03_cleanup_bench_users.yml "${EXTRA_VARS[@]}" -e ansible_platform_persistent=true
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
  echo "=============================================="
} | tee "$REPORT_FILE"
echo ""
echo "Report written to: $REPORT_FILE"
