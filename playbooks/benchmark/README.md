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

# Optional arguments: [user_count] [mode]
./playbooks/benchmark/run_benchmark.sh 50              # 50 users, both modes
./playbooks/benchmark/run_benchmark.sh 100 direct     # 100 users, direct only
./playbooks/benchmark/run_benchmark.sh 100 persistent  # 100 users, persistent only
```

**Mode:** `direct` | `persistent` | `both` (default: `both`). Use `direct` or `persistent` to run and time only that mode.

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
