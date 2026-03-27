# Performance Test Logs

This directory contains detailed Ansible logs from performance benchmark runs.

## Latest Run Results

**Speedup**: 5.53x faster  
**Improvement**: 81.9% time reduction  
**Time Saved**: 53.60s per run

## Log Files

### Baseline (Old Architecture - Modules)
- `baseline_run_1_*.log` - First baseline run with detailed -vvv output
- `baseline_run_2_*.log` - Second baseline run with detailed -vvv output

**Key things to look for in baseline logs:**
- Module loading: `Loading module_utils file .../aap_module.py`
- Process creation: Each task creates new process
- TLS handshakes: New connection for each task
- Authentication: Auth happens for each task

### New Architecture (Action Plugin + Manager)
- `newarch_run_1_*.log` - First new architecture run with detailed -vvv output
- `newarch_run_2_*.log` - Second new architecture run with detailed -vvv output

**Key things to look for in new architecture logs:**
- Action plugin loading: `Loading action plugin user from ...`
- Manager spawning: `Spawning new Platform Manager`
- Manager reuse: `Connected to existing manager`
- Session reuse: No repeated TLS handshakes
- RPC communication: `ManagerRPCClient` calls

## Analyzing the Logs

### Baseline Log Analysis

Search for:
```bash
# Module loading (happens every task)
grep "Loading module_utils" logs/baseline_run_1_*.log

# Process creation
grep "fork" logs/baseline_run_1_*.log

# TLS/Connection creation
grep "TLS\|SSL\|connection" logs/baseline_run_1_*.log

# Authentication
grep "auth\|authenticate" logs/baseline_run_1_*.log
```

### New Architecture Log Analysis

Search for:
```bash
# Action plugin usage
grep "action plugin" logs/newarch_run_1_*.log

# Manager lifecycle
grep "Platform Manager\|manager\|ManagerRPCClient" logs/newarch_run_1_*.log

# Session reuse (should see only one TLS handshake)
grep "TLS\|SSL\|session" logs/newarch_run_1_*.log

# RPC calls
grep "RPC\|execute" logs/newarch_run_1_*.log
```

## Performance Comparison

| Metric | Baseline | New Architecture | Improvement |
|--------|----------|------------------|-------------|
| Average Time | 65.43s | 11.83s | **5.53x faster** |
| Consistency (StdDev) | ~0.3s | ~0.08s | More consistent |
| Process Creation | 10 processes | 1 process | 90% reduction |
| TLS Handshakes | 10 handshakes | 1 handshake | 90% reduction |
| Module Loading | 10 times | 1 time | 90% reduction |

## What the Logs Show

### Baseline Logs Show:
1. **Repeated Module Loading**: Each task loads `aap_module.py`, `aap_user.py`, etc.
2. **Process Overhead**: New Python process for each task
3. **Connection Creation**: New HTTPS connection per task
4. **TLS Handshakes**: Full TLS negotiation for each task
5. **Authentication**: Auth happens repeatedly

### New Architecture Logs Show:
1. **Action Plugin**: Uses `plugins/action/user.py` instead of module
2. **Manager Spawning**: First task spawns manager (one-time cost)
3. **Manager Reuse**: Subsequent tasks connect to existing manager
4. **Session Reuse**: Single TLS handshake, reused across all tasks
5. **RPC Communication**: Fast local RPC calls instead of full process creation

## Viewing Logs

```bash
# View baseline log
less logs/baseline_run_1_*.log

# View new architecture log
less logs/newarch_run_1_*.log

# Compare key sections
diff <(grep "Loading" logs/baseline_run_1_*.log) <(grep "Loading" logs/newarch_run_1_*.log)

# Count module loads
grep -c "Loading module_utils" logs/baseline_run_1_*.log  # Should be ~10
grep -c "Loading module_utils" logs/newarch_run_1_*.log    # Should be ~1 or 0
```

## Report

See `performance_report_with_logs.json` for complete performance metrics and log file references.

