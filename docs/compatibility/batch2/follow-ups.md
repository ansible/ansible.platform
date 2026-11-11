# Additional findings identified during the Batch 2 audit

These records retain the evidence and disposition of findings discovered beyond the original Batch 2 module list. Local identifiers are not Jira issue numbers or approved compatibility exceptions.

## B2-FOLLOWUP-001: bulk launch treats zero as an immediate client timeout

Status: **fixed in this branch**, following the user's request to address it here. The proposed separate follow-up is no longer needed for this defect. No external issue was created.

Classification before correction: **breaking runtime compatibility difference**, with incomplete documentation of zero's behavior. The correction restores the legacy behavior.

### Trigger and user impact

```yaml
- name: Launch jobs and wait without a time limit
  ansible.platform.bulk_job_launch:
    jobs:
      - unified_job_template: 7
    wait: true
    timeout: 0
```

Before correction, if the first poll reported a running job, the action failed with a client-side timeout. The remote job was not canceled and could continue running. If the first response was already terminal, it could complete successfully, so the defect was sensitive to job timing.

AWX's legacy bulk action invokes `ControllerAPIModule.wait_on_url`, whose timeout test is conditional on the supplied value being truthy. An omitted timeout or zero therefore means unlimited waiting. See the pinned [legacy bulk action](https://github.com/ansible/awx/blob/72a1922a9cdc7c877c91d2e97d0c53ed34b437f4/awx_collection/plugins/modules/bulk_job_launch.py#L278) and [legacy waiter](https://github.com/ansible/awx/blob/72a1922a9cdc7c877c91d2e97d0c53ed34b437f4/awx_collection/plugins/module_utils/controller_api.py#L1187).

### Cause and correction

- The [platform action](../../../plugins/action/bulk_job_launch.py) originally mapped only an omitted timeout to `-1`, the SDK's unlimited-wait value, but forwarded explicit zero as `0.0`. It now maps both omitted and zero to `-1.0`, retaining positive deadlines and negative-input rejection.
- The [shared waiter](../../../plugins/plugin_utils/platform/base_client.py) treats zero as a zero-second deadline and raises after its first nonterminal poll. A negative SDK timeout means unlimited waiting.
- The [module documentation](../../../plugins/modules/bulk_job_launch.py) now explains omitted/zero behavior, that it applies when waiting, and that a client timeout does not cancel the remote job.
- This is the top-level client wait timeout. The separate `jobs[].timeout` option is a server-side job limit and should not be changed as part of the client-wait correction.

### Evidence before correction

The real bulk action and shared polling helper were executed with stubbed API responses: first `running`, then `successful`. Sleep was disabled. No request was sent to AAP, no job was launched, and no live cancellation behavior was tested by this diagnostic.

| Supplied timeout | Forwarded SDK timeout | Polls | Outcome |
|---|---|---|---|
| Omitted | `-1.0` | 2 | Successful |
| `0` | `0.0` | 1 | Failed while status remains `running` |
| `30` | `30.0` | 2 | Successful |

Machine-readable results before correction are retained under `precommit_review.bulk_zero_timeout_probe` in [execution evidence](execution-results.json). The original bulk-launch unit tests passed, including omission and negative-input validation, but did not cover zero as an unlimited wait. Two added regression cases failed before correction: explicit-zero sentinel conversion and a zero-timeout wait crossing a running response.

The permanent regression `test_zero_timeout_waits_across_a_running_response` in `tests/unit/plugins/action/test_bulk_job_launch.py` invokes the real SDK waiter with stubbed running/successful responses and disabled sleep. Before correction it failed after one poll; after correction it consumes both responses and succeeds. It sends no requests to AAP. Run this test and `test_unlimited_wait_timeout_preserves_indefinite_wait` to reproduce the corrected behavior.

### Implemented correction and validation

1. Both omitted and zero client timeouts now map to the SDK's unlimited sentinel. Positive deadlines and negative-input rejection are retained; per-job server-side timeouts are untouched.
2. The module documentation explains the corrected client-wait semantics.
3. All 25 bulk-action tests pass, including the new zero-timeout regression, positive-timeout behavior, invalid arguments, terminal failures, and client timeout handling. The full unit suite passes 1,450 tests plus subtests.
4. The native `bulk_job_launches_test` scenario includes a zero-timeout launch alongside its positive-timeout and no-wait launches, using real jobs in disposable local AAP and the scenario's cleanup. Its final result is recorded under `bulk_zero_timeout_fix` in the execution evidence.

The change is included in [the changelog](../../../changelogs/fragments/aap-101589-bulk-launch-timeout.yml). It resolves this finding without accepting a compatibility exception. The separate Batch 1 timeout integrations and workflow graph decision remain as recorded in the main audit.
