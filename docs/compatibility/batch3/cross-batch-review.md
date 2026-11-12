# Cross-batch regression review - AAP-101590

This supplement checks whether the failure patterns exposed in Batch 3 also
affect the requested Batch 1 and Batch 2 modules. The baseline is platform
`f8d6c3fb099608d1bc688c84e0fcf06f9771d263`; legacy contracts use the pinned AWX
`devel` snapshot recorded in the [main review](compat-status.md). The updated
`track-module-compat` audit was rerun, supplemented by real argument validation,
transform and comparison tests, and native platform scenarios against the same
authorized disposable local AAP 2.7-next / Controller 4.8.11 environment.

These are additional **native** runs. They do not replace, or claim to rerun,
the legacy scenarios recorded in the earlier batch reviews. The review covers
the 15 requested module names plus `controller_settings`, because platform
`settings` manages Gateway while the legacy settings replacement manages
Controller. Gateway organization replacement and the historical token contract
remain supplements to the skill's migration scope, as recorded in Batch 2.

## Results

| Module | Native result | Cross-batch finding or regression coverage |
|---|---|---|
| `organization` | Pass, 22 ok | Empty-description round trip and actual argument validation; Gateway ownership differences remain. |
| `workflow_job_template` | Pass, 36 ok; persistent manager also 36 ok | Survey alias restored; surveys and associations compared without check-mode writes; repeated survey clears are unchanged. |
| `execution_environment` | Pass, 23 ok | An unused missing credential no longer blocks deletion; find/delete transform regressions cover both operations. |
| `group` | Pass, 51 ok | Shared canonical alias normalization covers `groups`/`children`; existing empty-description behavior retained. |
| `token` | Pass, 29 ok | Actual argument validation and native lifecycle; token creation remains intentionally non-idempotent. |
| `job_wait` | Pass, 20 ok | Actual argument validation and native wait behavior; documented negative-timeout rejection retained. |
| `settings` | Pass, 10 ok | Gateway native settings lifecycle; no resource associations or launch waiter apply. |
| `controller_settings` | Pass, 13 ok, persistent manager | Controller settings native lifecycle. |
| `notification_template` | Pass, 23 ok | Actual argument validation and empty-description comparison remain compatible. |
| `job_launch` | Pass, 15 ok | Alias normalization and legacy negative-timeout behavior; real shared-waiter regressions check first-poll timeout and terminal success. |
| `inventory` | Pass, 38 ok | Actual argument validation and empty-description comparison; read-only `exists` retained. |
| `host` | Pass, 22 ok | Actual argument validation and empty-description comparison; read-only `exists` retained. |
| `inventory_source_update` | Pass, 25 ok | Alias normalization, legacy negative timeout, and documented boolean/timestamp timing convention verified. |
| `schedule` | Pass, 29 ok | Empty prompt round trips, nullable relationship clears, scoped execution-environment lookup, unused write-reference handling. |
| `inventory_source` | Pass, 32 ok | Existing unused-reference protections and empty-description behavior retained; obsolete virtualenv option needs disposition below. |
| `project_update` | Pass, 14 ok | Shared alias normalization and native timing/wait behavior; documented negative-timeout rejection retained. |

Four successful scenarios contain one intentionally ignored failing task each:
token, job_wait, inventory, and inventory_source_update. Their expected-error
paths are included in the play recap. All final runs have zero failed,
unreachable, or skipped tasks. This does not imply exhaustive coverage of every
option or all AAP versions.

The Batch 3 native workflow-launch target was also rerun after the timeout
correction: 19 ok, zero failed/skipped/ignored. It verifies successful waiting
and a no-wait launch with a negative timeout. Shared-waiter unit regressions
cover the negative-timeout unfinished and terminal first-response cases.

## Problems fixed

- Shared validation retained both alias and canonical keys. Resource-model
  construction must receive canonical keys only. Cross-batch tests use real
  Ansible validation rather than mock prevalidated dictionaries.
- Workflow-template check mode assumed changes and skipped comparisons. The
  action now uses the SDK's association comparison and a check-mode-aware
  survey comparison. The direct client, persistent service, and RPC forwarding
  preserve live updates while preventing dry-run POST/DELETE requests. An
  absent or already empty survey is an unchanged clear. Survey aliases are
  retained when the action reads its original task arguments.
- Execution-environment and schedule transforms resolved irrelevant write-only
  references during find/delete. Identity scopes still resolve; unused update
  values do not prevent locating or deleting an existing resource.
- Schedule transforms discarded stored empty prompt strings, causing repeated
  updates. Empty strings now round trip. Nullable inventory/environment clears
  compare equal to API nulls; this exception is restricted to those resource
  relationships and the node's execution environment. Environment lookup uses
  the existing organization-scoped resolver with its global fallback.
- Job launch, workflow launch, and inventory-source update treated negative user timeouts as
  unlimited SDK waits. They now translate those values to a first-poll timeout,
  preserving legacy behavior. A terminal first response succeeds; an unfinished
  response fails the wait after launch. Omitted/zero values remain unlimited,
  and the remote job is not cancelled. Already documented rejection in
  job_wait and project_update is unchanged. The initial local workflow-launch
  rejection proposal was removed because its original platform documentation
  did not require that difference; the user's stated policy favors legacy
  behavior unless an established platform contract says otherwise.
- Inventory-source update now preserves timing using the existing platform
  convention: boolean `finished` and timestamp `finished_at`, on completion and
  timeout. Timestamp consumers must use `finished_at`, as for the other reviewed
  platform launch/wait modules.

The architecture audit found no direct HTTP calls or hand-written polling in
the reviewed actions. HTTP and polling remain in the shared SDK/service layer.

## Initial failures and their causes

The workflow-template test's webhook notification fixture initially omitted
required `headers`. Adding `headers: {}` corrected the fixture; it was not a
workflow-template compatibility failure.

The schedule test initially created a schedule with omitted prompts, then
expected an unchanged result when explicitly passing empty prompts. A real
Controller diagnostic proved that omitted prompts return null (inherit), while
explicit empty SCM branch, tags, and limit persist as empty strings (clear).
The first clear must change the schedule. The corrected scenario verifies that
change, then verifies an identical second clear is unchanged. The diagnostic
schedule was deleted, including cleanup of its interrupted first attempt.

## Evidence and outstanding decisions

[Machine-readable evidence](cross-batch-results.json) includes every native
attempt and its private-log hash, final results, unit and baseline reproduction
counts, final implementation hashes, and the relevant skill audit rows. The
105 cross-batch regressions pass; on the isolated original baseline, 57 fail and
48 pass. Failures include missing new check-mode SDK signatures as well as
behavioral differences, so this is not a count of 57 independent defects.

The complete current unit suite passes 2,317 cases including subtests. Ruff,
mypy, action docstrings, architecture invariants, production-profile lint for
the eight changed native YAML files, and pinned Ansible 2.16 / Python 3.11
sanity checks pass. Pylint, no-smart-quotes, and validate-modules cover the
changed Python files in an isolated checkout. See the JSON for exact scope.

The agreed coverage follow-up and documented compatibility gap are:

1. **Instance-group execution-node association coverage:** local Controller has
   only a control node. The Batch 3 native association tasks remain skipped;
   passing mocked tests do not close that coverage gap. The user agreed to
   record this limitation and have M3 run the existing association scenario
   in an environment with an eligible execution or hybrid node before closing
   the ticket. This agrees the next step; it does not waive the test or record
   M3 acceptance. The follow-up remains tracked under AAP-101590.
2. **Unsupported `inventory_source.custom_virtualenv` (breaking; disposition
   requires review):** legacy AWX accepts a filesystem path to a custom Python
   virtual environment, documented as deprecated and compatible only with
   older AWX/Controller versions. `ansible.platform.inventory_source` does not
   accept this parameter; existing playbooks that supply it fail argument
   validation. Modern deployments use `execution_environment`, selecting an
   execution-environment image containing the required dependencies. This is
   not a direct parameter rename: a virtualenv filesystem path cannot be used
   as an execution-environment name or ID. The native scenario's pass does not
   cover the unsupported parameter. The user agreed to capture this difference
   in the compatibility review for team disposition. It remains tracked under
   AAP-101590 and has not been approved as an intentional contract difference.
   No module behavior was changed for this finding.

The previously recorded workflow-template graph/schema gap also remains open
in the Batch 2 review. These fixes do not implement parent graph management.
Code validation passing does not close that separate gap or substitute for
PR CI, required approvals, and M3 review.
