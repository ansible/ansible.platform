# Batch 2 compatibility audit — AAP-101589

Snapshot: 2026-11-11. Branch: `AAP-101589-batch2-compat`.

**The ticket is not ready to close.** All nine platform-native scenarios passed against local AAP, but the legacy workflow graph interface is missing and has no approved disposition. Passing native tests does not establish legacy parity.

## Baselines and scope

| Input | Revision / treatment |
|---|---|
| Platform baseline | `0d5514b50281fef9e0953584340426886a07a182`, plus this branch's working changes |
| AWX legacy modules and scenarios | `devel`, pinned at `72a1922a9cdc7c877c91d2e97d0c53ed34b437f4`; exported without switching the user's AWX checkout |
| Legacy token | Absent from AWX `devel`. Supplemented with the available Controller `stable-2.6` checkout at `798a79d8800d6bbd42d1714d13cd60febb9a0032` |
| Workflow | Updated `track-module-compat` skill, including its contract comparison, scope manifest, architecture checks, and legacy-target adapter |
| Runtime | Disposable local `aap-dev` AAP 2.7-next, Gateway `http://localhost:44927`; ansible-core 2.21.5, Python 3.14.6 |

The skill classifies seven Batch 2 modules as planned migrations. Its manifest excludes Controller `organization` in favor of the Gateway replacement. This audit explicitly compares that replacement because the ticket includes it. The absent AWX `token` is also audited explicitly, using the skill's comparison helpers against the stable baseline. Neither supplement is represented as a normal migrated AWX-develop row.

The manifest's collection-wide AWX summary counts conflict with its detailed rows (35/8 versus 38/7). This audit follows the detailed rows and evaluates all nine requested modules. [Contract evidence](contract-audit.json) records the skill hashes, source revisions, per-module differences, and platform code hashes.

## Live results

"Original" preserves the legacy inputs and assertions, substituting platform module names. Setup dependencies were additionally isolated with legacy modules for workflow, job wait, and project update, so unrelated migrations would not mask the subject module. "Adapted" is a diagnostic continuation with the explicit changes below; it is not an unchanged legacy pass.

| Legacy → platform module | Original legacy outcome | Adapted legacy outcome | Platform-native outcome |
|---|---|---|---|
| `organization` → `organization` | Stops on unsupported `galaxy_credentials` | No equivalent Controller-association scenario for the Gateway replacement | Pass: `organizations_test` |
| `workflow_job_template` | Stops where `exists` is expected to recreate a deleted workflow | Graph creation is rejected; the source masks this failure and later errors on missing launch `job_info` | Pass: `workflow_job_templates_test`, including invalid-reference deletion regression |
| `execution_environment` | Stops where `exists` is expected to recreate a deleted environment | Pass after adapting the creation task | Pass: `execution_environment_test` |
| `group` | Stops where `exists` is expected to recreate a deleted group | Pass after adapting creation and legacy error-payload assertions | Pass: `groups_test`, including scoped associations and check mode |
| `token` | Legacy `job_list` setup receives HTTP 401 for an invalid list token instead of its expected validation text; token tasks are not reached | Pass after separating error wording and adapting auth/fact names; stable-2.6 baseline | Pass: `tokens_test` |
| `job_wait` | Stops on exact not-found message; legacy cleanup also references an undefined workflow variable | Pass after separating message wording from failure behavior | Pass: `job_waits_test` |
| `settings` → `controller_settings` | Stops on exact API-error message | Pass after separating message wording from failure behavior | Pass: `controller_settings_test`, in HTTP persistent mode |
| `notification_template` | Stops where `exists` is expected to recreate a deleted notification | Pass after adapting creation and restoring `copied` | Pass: `notification_templates_test` |
| `project_update` | Pass | No adaptation needed | Pass: `project_updates_test` |

The adapted scenarios change `exists` to `present` only for the tasks that create after deletion, retaining existing-resource read-only checks. Token fact references change from `controller_token` to `aap_token`, and platform token calls use `aap_token` instead of `controller_oauthtoken`. Exact `.msg` assertions are separated from functional failure assertions. The group continuation additionally omits the legacy-only `total_results` error-field assertion. Resource inputs, ordinary changed/unchanged assertions, and the remaining scenario flow are retained.

The token baseline failure is a legacy-helper/test-environment mismatch before the module under review, not evidence of a platform token defect. Its adapted continuation exercises creation, use, deletion, repeat creation, and rejection of insufficient privileges. Token runs reference the matching stable collection for legacy dependencies; other targets reference AWX `devel`.

[Omitted diagnostic assertions](diagnostic-assertions.json) records the exact conditions removed. Some message-only assertions become empty and provide no functional coverage. The workflow source also uses `failed_when: false` on graph creation, so its later "not failed" assertion cannot establish successful creation. Direct validation confirms `Input validation failed: workflow_nodes`; the later launch error is a consequence, not evidence of another migrated module's return contract.

Native targets use their existing platform task format. Most runs use local connections and the collection's ephemeral manager; Controller settings uses `ansible.platform.http` with persistence enabled. This is not a complete three-connection-mode or supported-Python/Ansible matrix.

[Execution evidence](execution-results.json) records final exit codes, recaps, task counts, and failed task/error summaries. It excludes credentials and token values. Earlier harness failures are not module failures: the initial collection import path and authentication were corrected; the first native settings invocation skipped by design; persistent-mode setup then required a short temporary path for macOS's Unix socket limit.

The nine identified leftovers from failed legacy runs were removed, and a subsequent scoped API check found none remaining. Native and focused regression scenarios use their own cleanup blocks.

## Defects fixed in this branch

These are compatibility defects repaired here, rather than remaining migration requirements for end users.

| Finding | Evidence and correction | Validation |
|---|---|---|
| Omitted/zero `project_update.timeout` changed unlimited legacy waiting into a default limit/immediate timeout | Legacy `ControllerAPIModule.wait_on_url` tests timeout truthiness. Platform now maps omitted/zero to the SDK's indefinite sentinel and preserves explicit nonzero values. | Focused timeout tests; legacy and native project-update scenarios |
| `project_update` omitted legacy runtime timing and failed-job data | Legacy `wait_output` returns elapsed/start/finish data and failed waits return `job_data`. Restored timing and failed-job data, with the finish timestamp at `finished_at` for Ansible result compatibility. | Success, canceled, and timeout unit cases; native runtime |
| Token deletion accepted missing or conflicting identifiers | Legacy token argspec has mutually exclusive identifiers and a conditional requirement. Restored both constraints. | Real argspec tests for invalid arguments and both valid identifier forms in check mode; adapted legacy token scenario |
| Group association lookups ignored inventory scope | Legacy `group` resolves hosts/children with an inventory filter. A live case with duplicate names in two inventories failed as ambiguous. Both association lookups now use the selected inventory ID. | Live reproduction failed before and passed after; permanent native regression |
| Group check mode ignored association-only changes | The action skipped association reconciliation entirely in check mode. SDK association reconciliation now supports a read-only comparison, and the group action uses it. | Both client implementations, RPC forwarding, action tests; live checks verify predicted changes, unchanged remote associations, and subsequent idempotency |
| Notification/workflow copies omitted `result.copied` | Both legacy scenarios use this runtime field, supplied by `ControllerAPIModule.copy_item`. Restored true for an actual copy and false for an existing destination. | Both action types tested; adapted notification scenario completes |
| Workflow deletion with unused invalid inventory/webhook references incorrectly reported "already absent" | The legacy workflow scenario expects deletion to succeed. Resolving unrelated references during find raised a not-found error that the absent flow interpreted as a missing workflow. Find/delete now omit those write-only FK resolutions while retaining organization scope. | Transform regression and native deletion scenario |

Implementation and focused tests are linked by the [changelog fragment](../../../changelogs/fragments/aap-101589-batch2-compat.yml). The shared SDK additions preserve the default write behavior for callers that do not request check mode.

## End-user compatibility differences

These entries describe the current migration contract. They must be carried into user-facing migration documentation separately from the fixed defects above.

| Difference | Classification | Explanation / migration action |
|---|---|---|
| `controller_*` authentication options and variables | Breaking, documented collection interface | Use the platform `aap_*` authentication interface or its documented `gateway_*` aliases. Replacing the module FQCN alone does not translate legacy authentication arguments. |
| `state: exists` | Breaking behavior, documented collection state model | For organization, workflow templates, execution environments, groups, and notifications, `exists` reads one resource and makes no changes. A missing resource returns `exists: false`; it is not recreated. Use `state: present` to create or update it. Legacy creation-after-deletion assertions therefore need an explicit migration. |
| Controller organization replaced by Gateway organization | Breaking replacement, explicit skill scope decision | Platform `organization` manages Gateway name, description, and rename operations. It does not accept legacy `max_hosts`, `default_environment`, `galaxy_credentials`, `instance_groups`, notification association options, or deprecated `custom_virtualenv`. Existing Controller organization playbooks need redesign; this audit does not claim association parity. |
| Controller settings module name | Breaking naming change, explicit skill mapping | Use `ansible.platform.controller_settings`. `ansible.platform.settings` manages Gateway settings and is not the replacement for `awx.awx.settings`. The legacy `name`/`value` and `settings` forms are retained by `controller_settings`. |
| Token endpoint and fact name | Breaking replacement | Platform creates Gateway tokens and exports `aap_token`, replacing the legacy `controller_token` fact. Update subsequent authentication and deletion references. Both implementations intentionally create a new token on each present invocation. |
| Token scope type and choices | Review-level type change; safe choice additions | Platform accepts a list and adds `openid`/`roles`. Legacy single-string `read` and `write` inputs still work through Ansible coercion; the legacy adapted runtime and native token tests cover these inputs. |
| Finish timestamp result key | Review-level return change with a concrete migration requirement | Legacy `job_wait.finished` is a timestamp; platform `finished` is boolean and the timestamp is `finished_at`. Project-update timing uses the same naming. Change timestamp consumers to `finished_at`. The tested Ansible core action-result model declares `finished` as boolean, supporting this naming choice. |
| Error wording and auxiliary fields | Review-level error contract change | Use task success/failure and resource state rather than exact legacy strings. For example, group lookup failures do not provide the legacy `total_results` field. The legacy message/payload assertions were recorded separately, not treated as successful unchanged scenarios. |
| Nested CRUD resource results and `enforced` state | Safe additions | Platform adds nested resource dictionaries and the documented `enforced` state. These additions alone do not prove parity; ordinary legacy changed/idempotency checks and native nested-result assertions were executed separately. |

### Open: legacy workflow graph options

**Breaking; unresolved.** AWX documents `workflow_nodes` (alias `schema`) and `destroy_current_nodes` (alias `destroy_current_schema`): [node contract](https://github.com/ansible/awx/blob/72a1922a9cdc7c877c91d2e97d0c53ed34b437f4/awx_collection/plugins/modules/workflow_job_template.py#L171), [destruction contract](https://github.com/ansible/awx/blob/72a1922a9cdc7c877c91d2e97d0c53ed34b437f4/awx_collection/plugins/modules/workflow_job_template.py#L429). The platform module declares none of those options, and its action has no equivalent graph orchestration. The skill reports all four as breaking drops. No changelog entry approving their removal was found.

Separate `workflow_job_template_node` tasks are a possible redesign, not an established substitute for the whole legacy graph contract, including approval nodes, associations, and graph replacement. The native workflow-template scenario does not exercise this interface.

**Disposition required before closure:** restore the interface, obtain an explicit accepted migration decision with end-user guidance, or link an owner-approved follow-up issue. This finding remains tracked by the current audit ticket; no follow-up issue has been created or represented as approved.

## Architecture and validation

The skill found no direct HTTP calls or hand-rolled polling in the nine subject action plugins, including the two explicit supplements. Manual inspection confirms the wait actions use the shared SDK. The repository action-plugin invariant check also passes. The skill's regex checks are tripwires, not proof of all architectural properties.

Completed checks: 1,430 unit tests plus their subtests; Ruff lint and format; mypy; pydoclint on changed action plugins; action-plugin invariants; `ansible-doc` parsing; production-profile Ansible lint for changed integration tasks. Test counts and runtime recaps are recorded in the execution evidence.

## Batch 1 follow-ups discovered during this audit

These additional fixes are included on `AAP-101589-batch2-compat` following the cross-check against `ANSTRAT-1874-batch1-compat`. They are fixes absent from that branch, rather than another claim that the entire Batch 1 audit was rerun.

| Module | Additional correction | Regression coverage |
|---|---|---|
| `inventory` | Return `copied` for copy requests; compare actual associations in check mode instead of unconditionally reporting changed. | Copy result tests; native copy assertion; live check-mode prediction, unchanged remote associations, and unchanged repeated associations |
| `schedule` | Compare actual associations in check mode. | Action tests for changed/unchanged/clear requests; native empty-credentials check verifies unchanged |
| `inventory_source` | Compare notification associations in check mode; omit unused credential, execution-environment, and project lookups during find/delete while preserving inventory scope. | Action and transform tests; live no-write/idempotency checks; deletion with invalid unused references |
| `job_launch` | Return elapsed/start/finish timing and failed `job_data` when waiting. As with Batch 2 waits, the finish timestamp is `finished_at`, with a boolean `finished`. | Success, failed-job, timeout, and non-wait unit cases; native job run checks returned timing |

`host` has no equivalent defect identified in this comparison. Existing Batch 1 timeout corrections for `job_launch` and `inventory_source_update`, and existing inventory-update timing/failure-result fixes, remain on the separate Batch 1 branch; they have not been duplicated here. This branch therefore still needs those existing changes through the normal integration of that work.

The follow-up full unit suite passes **1,448 tests**, plus subtests. Ruff, mypy, changed-action pydoclint, action-plugin invariants, and production-profile Ansible lint pass. The four changed modules have dedicated native AAP regression runs recorded separately under `batch1_followups` in the execution evidence. These follow-ups do not resolve the workflow graph blocker above.

## Pre-commit timeout review

The subsequent documentation review found another difference outside the original Batch 2 module list: `bulk_job_launch` forwarded zero as an immediate client deadline, whereas the legacy helper treated zero as unlimited. The user requested that it be addressed here. It is now **fixed in this branch**, with explicit omitted/zero documentation and regression coverage. [B2-FOLLOWUP-001](follow-ups.md#b2-followup-001-bulk-launch-treats-zero-as-an-immediate-client-timeout) retains the original diagnostic evidence and records the correction; no separate issue or compatibility exception is needed for this defect.

All **65 focused tests** for bulk launch, project update, job launch, inventory-source update, and job wait pass. `ansible-doc` parses all 13 reviewed module documents; all 29 recorded production-code hashes match; Ruff, mypy, changed-action pydoclint, action-plugin invariants, and diff checks pass. Results are recorded separately in `precommit_review` in the execution evidence. They supplement the existing 1,448-test full-suite result and the recorded live AAP runs; neither the full suite nor live integration runs were repeated for this documentation-only review.

Those counts describe the review before the bulk runtime correction. After correction, all **25 bulk-action tests** and **1,450 full-suite unit tests**, plus subtests, pass. The two added bulk regression cases failed before the correction and passed afterward. The native bulk scenario additionally exercises zero-timeout waiting against local AAP; its final recap and the updated validation are recorded under `bulk_zero_timeout_fix` in the execution evidence. Historical pre-fix evidence is retained rather than presented as current behavior.

The other timeout-documentation gaps remain open. In particular, the existing Batch 1 timeout corrections still need integrating before this branch can promise unlimited omitted/zero waiting for both `job_launch` and `inventory_source_update`. Those runtime integrations and wording changes for other modules were not included in the bulk fix. The workflow graph decision also remains unresolved. This validation pass does not declare the ticket ready to close.

The native scenarios passed on one real disposable AAP environment. This does not establish all supported versions, every notification backend, every secret replacement, long waits beyond manager idle limits, or the missing workflow graph interface. No compatibility concern is silently waived by a clean documentation diff.

## Reproduce

1. Export AWX `devel` at the recorded SHA and retain the separate stable-2.6 token baseline. Do not switch or modify either user's source checkout.
2. Run the updated skill against that AWX snapshot and the platform branch. For an uncommitted fix, omit `--platform-ref` so the script reads the working tree; for a committed rerun, pass its fixed ref. The contract artifact records exactly which mode was used.
3. Use the skill's `prepare_platform_integration_targets.py` for the seven planned targets. Include organization and token explicitly as the documented supplements. Map `settings` to `controller_settings`. Keep unchanged legacy runs separate from adapted diagnostic runs.
4. Reference the current checkout through `ANSIBLE_COLLECTIONS_PATH`; also put its collection root on `PYTHONPATH` so manager subprocesses can import it. For the token target, put a separate collection root referencing stable-2.6 `awx.awx` first in the collection search path; use the pinned AWX `devel` collection for other targets. Supply local Gateway credentials through a private extra-vars file or environment. For legacy setup calls, set `CONTROLLER_OPTIONAL_API_URLPATTERN_PREFIX=/api/controller/`. Never store authentication in audit artifacts.
5. Run each legacy target separately using AWX's `awx_collection/tools/integration_testing.yml` and the generated target overlay. Retain every scenario's exit code and recap. Apply only the adaptations listed above to a separate copy when continuing past known migration differences.
6. Run the native targets listed in the results table with the same disposable AAP credentials. `groups_test` needs the environment's `controller_demo_inventory_id`; organization lookups use a `connection_info` mapping with `host`, `username`, `password`, and `verify_ssl`. Controller settings requires HTTP persistent mode and a separate local delegation host. Use a short `TMPDIR` on macOS.
7. Run `python -m pytest tests/unit/`, `make check_ruff check_mypy check_pydoclint check_action_plugin_invariants`, and lint/documentation checks. Review remote resource cleanup and record environment failures separately from module differences.

The compatibility PR publishes these fixes and audit artifacts together. Link that PR and this audit from Jira; publication does not close the unresolved compatibility findings above. The execution evidence retains the original pre-commit snapshots and code hashes used during validation.

The included [scenario preparation wrapper](prepare_legacy_targets.py) uses the updated skill's task rewriter, includes the two explicit supplements, and isolates setup dependencies. It makes no API calls and requires a new output directory. Run it from the skill's shared `uv` environment, for example:

```sh
uv run python /path/to/ansible.platform/docs/compatibility/batch2/prepare_legacy_targets.py \
  --skill-dir /path/to/track-module-compat \
  --awx-repo /path/to/pinned-awx-snapshot \
  --token-repo /path/to/pinned-stable-controller \
  --output-dir /tmp/batch2-strict
```

Run the emitted per-module playbooks with private authentication and collection paths configured. To reproduce the diagnostic continuations, use a separate output directory and add `--adapt-known-differences`; inspect the emitted assertion-omission manifest before interpreting results.
