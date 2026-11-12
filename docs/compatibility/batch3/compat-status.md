# Batch 3 compatibility review - AAP-101590

Snapshot: 2026-11-12. **Open: all seven modules have live legacy and native results; execution-node association coverage and M3 acceptance remain outstanding.**

The subsequent [cross-batch regression review](cross-batch-review.md) records
additional fixes and native validation for the 15 requested Batch 1/2 module
names plus Controller settings. Its evidence supplements the historical
seven-module results below; it includes the final combined implementation
hashes and validation counts, and records the unsupported legacy inventory-source
virtualenv option as a breaking gap awaiting team disposition.

This review covers seven requested AWX/Controller modules. The updated
`track-module-compat` workflow was run against AWX `devel` at
`72a1922a9cdc7c877c91d2e97d0c53ed34b437f4` and the new platform branch
`AAP-101590-batch3-compat`, based on `f8d6c3fb099608d1bc688c84e0fcf06f9771d263`.
The required ancillary EDA snapshot is `origin/main` at
`7512a84083337d22e713f1c94492fa10a17cf729`. EDA modules are outside this batch.
The initial audit reads the fixed platform commit; the post-fix audit reads
the working tree. [Contract evidence](contract-audit.json) records both
snapshots, source provenance, and hashes of the changed implementation.

The skill reports six planned Controller migrations. Its scope manifest
explicitly excludes legacy `team` in favor of Gateway RBAC, so this review
also compares that replacement using the skill's contract extraction and diff
functions. This is an explicit supplement, not a change to the migration plan.
The plan's AWX summary/detailed-row count conflict remains unresolved; detailed
rows are provisional. Neither that conflict nor a clean contract diff proves
runtime parity.

## Module results

| Legacy module | Contract classification and disposition | Architecture | Legacy AAP run | Native AAP run |
|---|---|---|---|---|
| `team` | Review: Gateway replacement; options retained, `new_organization`, nested result and `enforced` added | Shared CRUD SDK | Strict: expected `exists` recreation fails; adapted: pass (18 ok) | Pass (37 ok) |
| `workflow_launch` | Review: wait metadata and structured prompt errors restored; `job_info.id` retained | SDK launch and shared waiter | Strict: alias defect fixed; timeout text differs; adapted: pass (34 ok) | Pass (19 ok) |
| `export` | Breaking selector gap fixed: numeric IDs and named URLs; review: Gateway asset ownership and documented retrieval cap | SDK search/lookup; no transport calls in action | Pass (19 ok) after migration unlocked | Pass (73 ok; export/import round trip) |
| `workflow_job_template_node` | Breaking drops `approval_node` and `lookup_organization` restored; review: numeric verbosity coercion; association and lookup fixes below | Shared CRUD, association and approval SDK | Strict: approval-name error text differs; adapted: pass (112 ok, 4 skipped) | Pass (46 ok), including approval idempotency and dry run |
| `label` | Safe: documented nested result and `changed` additions; shared state/auth differences still apply | Shared CRUD SDK | Strict: legacy error metadata missing; adapted: pass (9 ok) | Pass (9 ok) |
| `job_list` | Review: URL pagination types correct legacy documentation; reduced all-pages cap restored to 10,000 | SDK pagination | Pass (9 ok) | Pass (3 ok) |
| `instance_group` | Safe documented additions; functional check-mode write defect fixed | Shared CRUD and association SDK | Strict: expected `exists` recreation fails; adapted: pass (19 ok) | Pass (34 ok), 12 skipped; see coverage limit |

Contract extraction succeeded for every module, including the manual `team`
comparison. The architecture audit found no direct HTTP transport calls or
hand-written polling in these actions. Shared SDK code owns approval writes,
association changes, retries, and polling; the new approval method is exposed
through the persistent manager RPC client as well as the direct client.

## Confirmed problems fixed locally

Live scenario results and focused regressions provide evidence for these fixes;
coverage limits are recorded below.

| Finding | Original behavior | Change and reproducible evidence |
|---|---|---|
| B3-001 - node approval parameters | `approval_node` rejected validation; approval creation/update unavailable | Restore dictionary documentation, required name and mutual exclusion; shared SDK reconciles approval templates idempotently, preserves empty descriptions and zero expiry, and avoids check-mode writes. Tests: `test_workflow_approval_reconciliation.py`, real argspec cases in `test_batch3_compatibility.py`; native approval scenario added. |
| B3-002 - independent organization scopes | `lookup_organization` rejected; the action removed `organization` before constructing its model | Restore the target lookup parameter and retain the parent scope; parent workflow and target template can belong to different organizations. Test: `test_node_parent_and_target_use_independent_organization_scopes`. |
| B3-003 - node environment clearing and deletion | An explicit empty execution environment triggered an empty-name lookup; find/delete resolved unused update references | Preserve the legacy empty clear value; omit unused target/inventory/environment lookup work for find/delete. Transform regressions cover both behaviors. |
| B3-004 - instance-group check-mode writes | Existing groups could reconcile instances with live association writes in check mode | Pass check mode to the existing SDK comparison. Regression tests cover changed and unchanged associations; native assertions were added but skipped locally because no eligible execution/hybrid node is available. |
| B3-005 - node check-mode accuracy | Supplying any association forced `changed: true` without comparison | Compare resolved associations through the SDK in check mode; predict changes for missing workflow-node dependencies without writing. Existing scoped numeric-identifier handling is retained. |
| B3-006 - workflow launch results | Waited workflows omitted timing and failed-workflow data; prompt failures omitted legacy `errors` | Reuse the base action timing helper on completion and timeout; restore `job_data` on terminal failure and the prompt error list. Legacy `job_info` remains an ID dictionary. |
| B3-007 - job-list pagination limit | `all_pages` inherited the SDK's 1,000-object cap; legacy supports up to 10,000 | Pass the legacy 10,000 cap explicitly. SDK pagination unit tests retrieve 1,001 mocked jobs through both transports. |
| B3-008 - export selectors | Numeric IDs and named URLs were queried literally as names and could return no assets | Preserve ordinary exact-name queries; use ID queries for numeric selectors and SDK lookup for named URLs. Unit regressions and [read-only real AAP probes](selector-live.json) cover both selector forms. |
| B3-009 - negative workflow timeout | Negative user timeouts became unlimited waits; legacy polling instead timed out after launching | Preserve legacy behavior: translate a negative user timeout to a first-poll SDK timeout. Unit tests cover terminal and unfinished responses, ordinary/check-mode execution, and launching without waiting. |
| B3-010 - legacy workflow aliases | Ansible retained `workflow_template`/`workflow` alongside canonical keys, causing resource-model constructor errors | Normalize validated aliases centrally before building models. Real preparation tests exercise both aliases; the adapted legacy workflow-launch scenario passes on AAP. |

Permanent tests are under `tests/unit/plugins/action/test_batch3_compatibility.py`
and `tests/unit/plugins/plugin_utils/platform/test_workflow_approval_reconciliation.py`,
alongside the existing module-specific tests. Nine selected regressions fail
against an isolated copy of the original platform commit and pass with the
fixes. The two additional real alias-preparation tests also fail on that base
and pass with the fix. The source checkout was not changed for either comparison.

## Compatibility differences for documentation

- **Gateway teams:** names and organization options remain available, but the
  resource and its IDs belong to Gateway. This is the plan's RBAC replacement,
  not proof of identical Controller team permissions or association behavior.
- **Export service ownership:** organizations, users and teams come from
  Gateway; Controller resources still come from Controller. Native export/import
  round trips must not be presented as proof of identical legacy Controller
  backup semantics. Export's documented `max_objects` default is 10,000 per
  endpoint and raises instead of truncating; raise it explicitly for larger
  exports. Unrelated endpoint caches also use this limit.
- **Pagination links:** `job_list.next` and `previous` are URLs or null in
  actual API responses. Both legacy and platform forward them; the legacy
  integer return documentation was inaccurate. No runtime conversion is needed.
- **Workflow timing:** `workflow_launch` now follows the platform convention
  already reviewed in Batches 1/2: boolean `finished`, timestamp `finished_at`.
  Legacy timestamp consumers must use `finished_at`. Omitted/zero timeout
  continues to mean unlimited waiting; a positive client timeout does not
  cancel the remote workflow. Negative timeouts retain legacy behavior: launch
  first, then fail the wait after the first unfinished response. With
  `wait: false`, the timeout is ignored. They are not a way to request unlimited
  waiting. This supersedes the initial local proposal to reject negative
  values; no new negative-timeout migration difference is introduced here.
- **Node verbosity:** legacy documents a string and platform an integer.
  Ansible accepts numeric strings such as `"3"`; real argument validation
  verifies that coercion. Non-numeric strings are invalid verbosity values.
- **Explicit empty workflow overrides:** platform preserves supplied empty
  tag, limit and SCM-branch values and checks the template's prompt settings
  for them. Legacy workflow launch dropped these falsey overrides. Omit an
  override when it should not be supplied; an empty value is not an omission.
  This follows the explicit-value and prompt-validation behavior already
  reviewed for job launch in Batch 1.
- Existing migration requirements still apply: canonical `aap_*` auth with
  supported `gateway_*` aliases, no `controller_*` auth aliases, potentially
  different error text/auxiliary fields, and read-only `state: exists`.
  Legacy scenarios that create a missing resource using `exists` need `present`.
  New nested resource returns and applicable `enforced` states are additive.

The Batch 2 parent `workflow_job_template` graph-option gap is separate:
restoring `workflow_job_template_node.approval_node` does not restore parent
`workflow_nodes`/`schema` orchestration. This batch must not claim otherwise.

## Integration preparation and current environment failure

[prepare_legacy_targets.py](prepare_legacy_targets.py) copies pinned AWX targets
and uses the updated skill's task-rewriting function. It changes only the
subject module/FQCN and supplies platform authentication through module defaults.
Legacy inputs, assertions, dependencies and cleanup remain unchanged. Source
tests and the user's AWX checkout remain untouched.

| Subject | Legacy scenario | Native scenario |
|---|---|---|
| `team` | `team` | `teams_test` |
| `workflow_launch` | `workflow_launch` | `workflow_launchs_test` |
| `export` | `export` | `export_import_test` |
| `workflow_job_template_node` | Node tasks embedded in `workflow_job_template` | `workflow_job_template_nodes_test` |
| `label` | `label` | `label_test` |
| `job_list` | `job_list` | `job_lists_test` |
| `instance_group` | `instance_group` | `instance_groups_test` |

AWX devel has no standalone node integration target; its workflow-template
target contains the ordinary-node, approval, prompt and graph-edge scenarios.
Only node calls in that copied target are replaced; its parent workflow and
other dependencies remain legacy to avoid conflating migrations. Similarly,
the workflow-launch scenario retains legacy node/approval setup so it exercises
the launch module independently.

**B3-ENV-001: resolved environment failure.** The initial environment was
offline. After startup, Controller ping returned HTTP 200 (version 4.8.11), but
Gateway resource synchronization remained locked with HTTP 423 until
`migrate_service_data` finished. Bootstrap repeatedly failed because metrics
returned HTTP 503 through Gateway. Metrics health requests measured about six
seconds against a five-second Kubernetes readiness/liveness timeout. Increasing
both probe timeouts to 15 seconds in the disposable deployment allowed metrics
to become Ready. A retry of the standard service migration completed for all
four services and re-enabled service authentication. This was an environment
adjustment, not an ansible.platform code change; a fresh aap-dev deployment may
need the same adjustment until its probe configuration is corrected.

Strict runs preserve the legacy inputs and assertions. Separate diagnostic
copies account for established state/error-contract differences; their exact
changes are recorded in [legacy-adaptations.json](legacy-adaptations.json).
They must not be described as unchanged legacy passes. Native runs exercise the
platform playbooks, including the new approval and timing assertions.

The initial native node prerequisite also exposed **B3-T01, a test assumption**:
a Gateway organization ID was passed into Controller's workflow API. The fixture
now creates and deletes its prerequisite through Controller and uses the ID
returned by that service. Gateway and Controller organization IDs are separate
namespaces even when names refer to corresponding organizations.

The native node scenario also passed using `ansible.platform.http` with persistent
connections: 46 tasks passed, with no failures or skips. The legacy node target
skipped four optional GitHub PAT setup/webhook/cleanup tasks; none of those
were migrated node calls. Its diagnostic adaptation changes one literal
approval-name error assertion and no scenario inputs.

The local Controller has only a control node. The native instance-group
scenario passed its executed checks but skipped 12 tasks, including instance
association and association check-mode tests requiring a hybrid/execution node.
Unit regressions cover both changed and unchanged association predictions; live
association validation still requires an eligible node. The coverage gap is
tracked by this ticket, [AAP-101590](https://issues.redhat.com/browse/AAP-101590);
no separate Jira issue was created or marked approved. The user agreed to
record the limitation and have M3 run the association scenario in a suitable
environment before ticket closure; the missing coverage has not been waived.

[Cleanup evidence](cleanup-results.json) records removal of an earlier failed
workflow-cleanup resource and two credentials left by legacy cleanup. Test
labels remain because the label API does not support deletion, as the native
label scenario already documents.

Reproduce preparation with the pinned AWX snapshot and the updated skill:

```sh
python docs/compatibility/batch3/prepare_legacy_targets.py \
  --skill-dir "$COMPAT_SKILL" --awx-repo "$AWX_REPO" \
  --output-dir /tmp/platform-batch3-legacy
ansible-playbook -i localhost, /tmp/platform-batch3-legacy/workflow_launch.yml \
  -e @/path/to/private-aap-vars.json
```

Use the isolated snapshot as the `awx.awx` collection and this branch as
`ansible.platform` in `ANSIBLE_COLLECTIONS_PATH`. Keep credentials and raw live
logs outside the repository. The changed node client-side option exemptions also passed a focused check
against real Controller OPTIONS metadata using the actual completeness checker;
an unknown sentinel field was still rejected. This does not claim the full
collection completeness suite passed.

Native scenarios can be run using their normal
collection integration targets against the same disposable environment. For
legacy dependencies, also set `CONTROLLER_HOST`, `CONTROLLER_USERNAME`,
`CONTROLLER_PASSWORD`, `CONTROLLER_VERIFY_SSL=false`, and
`CONTROLLER_OPTIONAL_API_URLPATTERN_PREFIX=/api/controller/`. Use a private
Ansible temporary directory; on macOS keep `TMPDIR` short enough for Unix
sockets and set `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`. The exact Ansible
version used here was 2.21.5 on Python 3.14; pinned sanity checks additionally
used Ansible 2.16 and Python 3.11.

## Validation and ticket status

[Execution evidence](execution-results.json) records local validation and the
environment history and live runs. The final unit suite passed 2,212 cases
including subtests, with no failures, errors or skips. Targeted transport regressions, Ruff,
mypy, action docstrings, action-plugin invariants, seven-module `ansible-doc`
parsing and changed-playbook lint are checked locally. These checks do not
replace real AAP execution, version coverage, or legacy integration assertions.

All currently confirmed implementation concerns are addressed locally under
**AAP-101590**, with the documented live association coverage limit. No Jira tickets were created or
updated. Gateway ownership and shared state/auth differences are existing
plan-level decisions; no new module Jira is recommended solely for them.
The wider migration-scope count conflict needs its plan owner's reconciliation.
Any additional runtime gap requires a fix, an explicit acceptance rationale,
or an approved linked follow-up before this ticket closes. **The ticket stays open until live association coverage is resolved or accepted with a recorded rationale and M3 has reviewed the documented differences.**
