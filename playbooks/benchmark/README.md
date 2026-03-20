# Benchmark: Persistent vs Direct Connection Mode

This folder contains playbooks and a runner script to compare **persistent** vs **direct** (ephemeral) manager mode when running many `ansible.platform.user` tasks (e.g. create 100 users). The results can be used for performance notes in Proposal 3 (Persistent Connection Manager).

## What it does

1. **01_cleanup_all_except_admin.yml** – Removes all Gateway users except `admin` (prep).
2. **02_create_users.yml** – Creates N users via `ansible.platform.user` (the step that is timed).
3. **03_cleanup_bench_users.yml** – Deletes the N benchmark users.

The runner script runs: prep → create N users (direct, timed) → cleanup → create N users (persistent, timed) → cleanup, then prints a short report.

## Prerequisites

- Ansible and the `ansible.platform` collection (run from the collection root).
- **Python dependency:** The platform manager subprocess needs the `requests` module. Install it in the same environment you use for `ansible-playbook`:
  ```bash
  pip install -r requirements/requirements_dev.txt
  ```
  or at least: `pip install requests`. If this is missing, you will see `ModuleNotFoundError: No module named 'requests'` when the manager starts.
- A reachable AAP Gateway.
- **Credentials:** Set one of the following (env or `vars.yml`), or you will get 401 Unauthorized:
  - **Token:** `export AAP_TOKEN=your-gateway-token`
  - **Username + password:** `export GATEWAY_USERNAME=admin` and `export GATEWAY_PASSWORD=your-password`
  (A 401 can also mean the token is expired or the password is wrong.)

## Quick run (from collection root)

```bash
cd /path/to/ansible/platform   # collection root

# Optional: set Gateway URL and token
export BENCHMARK_BASE_URL="https://your-gateway/"
export AAP_TOKEN="your-token"
# Or username/password:
export GATEWAY_USERNAME=admin
export GATEWAY_PASSWORD="your-password"

# Default: 100 users, both modes (direct then persistent)
./playbooks/benchmark/run_benchmark.sh

# Optional arguments: [user_count] [mode] [verbose]
./playbooks/benchmark/run_benchmark.sh 50              # 50 users, both modes
./playbooks/benchmark/run_benchmark.sh 100 direct       # 100 users, direct only
./playbooks/benchmark/run_benchmark.sh 100 persistent   # 100 users, persistent only
./playbooks/benchmark/run_benchmark.sh 10 both -vv     # 10 users, both modes, verbose (-v, -vv, -vvv)
# Or use env for verbose:
BENCHMARK_VERBOSE=-vv ./playbooks/benchmark/run_benchmark.sh 10
```

**Mode:** `direct` | `persistent` | `both` (default: `both`). Use `direct` or `persistent` to run and time only that mode.

**Verbose:** Optional third argument `-v`, `-vv`, or `-vvv` (passed to `ansible-playbook`). Or set `BENCHMARK_VERBOSE=-v` (or `-vv`, `-vvv`) in the environment.

**Run same tasks with connection: local:** To also run the same create/test/cleanup playbooks with `connection: local` (ephemeral manager on the controller), set `RUN_WITH_LOCAL=1`. The script will run 02, 06 (test all operations), and 03 with `-e ansible_connection=local` and report "Connection local (same tasks, ephemeral manager): OK" or "FAILED". Example:
```bash
RUN_WITH_LOCAL=1 ./playbooks/benchmark/run_benchmark.sh 10 both
```
If the connection-local run fails, the script exits with status 1.

The script writes a summary to `playbooks/benchmark/benchmark_report.txt` (override with `BENCHMARK_REPORT_FILE`).

## Running playbooks manually

From the **collection root** (directory containing `playbooks/`, `plugins/`, etc.):

```bash
# Load vars from this folder
V="-e @playbooks/benchmark/vars.yml"

# 1) Cleanup all except admin (use -e ansible_connection=local if inventory sets platform connection)
ansible-playbook playbooks/benchmark/01_cleanup_all_except_admin.yml $V -e ansible_connection=local

# 2) Create 100 users - direct mode
ansible-playbook playbooks/benchmark/02_create_users.yml $V -e ansible_platform_persistent=false

# 3) Cleanup the 100 users
ansible-playbook playbooks/benchmark/03_cleanup_bench_users.yml $V -e ansible_platform_persistent=false

# Same with persistent mode
ansible-playbook playbooks/benchmark/02_create_users.yml $V -e ansible_platform_persistent=true
ansible-playbook playbooks/benchmark/03_cleanup_bench_users.yml $V -e ansible_platform_persistent=true
```

## How the connection mode is set

The connection plugin uses the **`ansible_platform_persistent`** variable (per host):

| Value | Mode | Behavior |
|-------|------|----------|
| `false` (default) | **Direct** | New ephemeral manager process per task (or per play); no reuse. |
| `true` | **Persistent** | One manager per host; reused across tasks in the same run (and across plays when set in inventory). |

**Ways to set it:**

1. **Extra vars (recommended for benchmark):**  
   `-e ansible_platform_persistent=false` or `-e ansible_platform_persistent=true`  
   The runner script uses this for each playbook run.

2. **Inventory:**  
   e.g. `127.0.0.1 ansible_connection=ansible.platform.http ansible_platform_persistent=true`

3. **Play vars:**  
   In the playbook, `vars: ansible_platform_persistent: true`

Playbooks 02 and 03 default to `false` (direct) if not set and print **"Connection mode: direct"** or **"Connection mode: persistent"** at the start so the run output is clear.

## Notes on cleanup and "already absent"

- **Credentials:** Create (02) and cleanup (03) must use the same Gateway credentials. Both playbooks use `vars.yml` (and env) for `gateway_username`, `gateway_password`, `gateway_token`, and `base_url`. If cleanup used different auth (e.g. a wrong or empty token), the API can return an error that the user module reports as "User 'bench_user_XXX' does not exist (already absent)" even though the users exist—so you would see all 10 (or N) users reported "already absent" on the first cleanup. With matching credentials, the first cleanup after create will delete the users (changed or ok); "already absent" is then normal only when users were already removed (e.g. running cleanup twice, or the second cleanup run in `both` mode).

## Variables

- **vars.yml** (or env): `base_url`, `gateway_username`, `gateway_password`, `gateway_token`, `gateway_validate_certs`, `keep_username`, `benchmark_user_count`.
- **run_benchmark.sh** accepts two optional arguments: `[user_count] [mode]`. User count defaults to 100. Mode defaults to `both`; use `direct` or `persistent` to run only that mode.

## Metadata for reproducibility

When publishing benchmark results (e.g. in the P3 proposal or a report), document the following so runs are reproducible and auditable:

- **When run:** Date (and optionally time) of the benchmark run.
- **Versions:** ansible-core version, ansible.platform collection version, and AAP/Gateway (or target API) version.
- **Environment:** Controller and Gateway location (e.g. same region, network), and any relevant details (CPU, memory, network latency if known).
- **Workload:** This benchmark uses the create-user playbook (`02_create_users.yml`) with N users (set via `run_benchmark.sh [user_count]` or `vars.yml`). Record the user count and mode(s) run (direct / persistent / both).

Update this section or add a `benchmark_metadata.txt` (or similar) when you run and publish new results so the proposal table can reference "see playbooks/benchmark/README" for canonical metadata.

## Using the report in Proposal 3

- Attach or paste the `benchmark_report.txt` (or a short summary) into the P3 proposal where you describe performance/benchmarks.
- Example summary: "For 100 user creates, direct mode took Xs and persistent mode Ys (Zx speedup)."
