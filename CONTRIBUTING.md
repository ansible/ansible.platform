# Contributing to ansible.platform

This collection is governed by [ANSTRAT-1640](https://redhat.atlassian.net/browse/ANSTRAT-1640). Contributions come from Gateway, Controller, EDA, and Hub PDTs, coordinated by Collection Stewards under TSC Platform Collections oversight.

---

## Quick start

| Task | Where to go |
|------|-------------|
| Add a new module | [docs/07-adding-resources.md](docs/07-adding-resources.md) |
| Architecture overview | [docs/01-overview.md](docs/01-overview.md) |
| SDK / action plugin pattern | [docs/02-action-plugin-pattern.md](docs/02-action-plugin-pattern.md) · [docs/03-sdk-architecture.md](docs/03-sdk-architecture.md) |
| Testing | [docs/08-testing-strategy.md](docs/08-testing-strategy.md) |
| Data model and transforms | [docs/04-data-model-transformation.md](docs/04-data-model-transformation.md) |
| Design principles | [docs/05-design-principles.md](docs/05-design-principles.md) |

---

## Governance model

Three-tier ownership (ANSTRAT-1640 P2):

- **TSC Platform Collections** — sets direction, arbitrates cross-team disputes, approves SDPs
- **Collection Stewards** — own CI health, releases, triage, quality gatekeeping, collection-wide docs
- **Component PDTs** (Gateway, Controller, EDA, Hub) — own the correctness of their modules and tests

Ownership is encoded in `CODEOWNERS`. Shared infrastructure (`plugin_utils`, CI, docs) requires Steward approval. Component modules require the relevant PDT. Cross-domain PRs require both.

---

## Definition of Done

When your work introduces or changes an API or collection behavior, the PR scope **MUST** include all of:

- [ ] `ansible.platform` module/plugin code updated
- [ ] `DOCUMENTATION` string updated (params, return values, examples)
- [ ] Integration test added or updated, passing in CI
- [ ] All CI checks green (unit, mock, integration — all 3 connection modes)
- [ ] CasC notification completed (if applicable — see below)

**This is not optional and not a follow-up ticket.** API-changing work that lands without the corresponding collection update is an immediate regression for CasC and downstream users.

---

## Before opening a PR

1. Reference a Jira issue in the PR title: `[AAP-XXXXX] Short description`
2. Fill the PR template completely — particularly the CasC Notification and Definition of Done sections
3. Apply the `safe to test` label to trigger integration CI (review the diff before adding this label — it grants access to secrets)
4. Minimum **2 approvals** required (at least one from each CODEOWNERS domain touched)

---

## UX standards (P2R5)

All plugins **MUST** follow these conventions. Do not invent one-off patterns.

### Parameter naming

Use parameters from `plugins/doc_fragments/auth.py`. Do not invent new top-level auth params.

| Parameter | Description | Env var |
|-----------|-------------|---------|
| `aap_hostname` | URL to AAP Gateway | `AAP_HOSTNAME` |
| `aap_username` | Username | `AAP_USERNAME` |
| `aap_password` | Password | `AAP_PASSWORD` |
| `aap_token` | OAuth/API token | `AAP_TOKEN` |
| `aap_validate_certs` | SSL verification | `AAP_VALIDATE_CERTS` |
| `aap_request_timeout` | Request timeout (float, seconds) | `AAP_REQUEST_TIMEOUT` |

`gateway_*` aliases are provided for backward compatibility. New code must use `aap_*` names.

Include auth params via: `extends_documentation_fragment: ansible.platform.auth`

### State values

Use `extends_documentation_fragment: ansible.platform.state`. State is defined in `plugins/doc_fragments/state.py`.

| Value | Meaning |
|-------|---------|
| `present` | Create if absent; update to match |
| `absent` | Delete if present |
| `exists` | Assert exists; read but do not modify |
| `enforced` | Create/update; API-defaults all fields not explicitly provided |

### Return values

Every plugin **MUST** define a `RETURN` block. The return structure must use the shared shape from `plugin_utils` — do not invent module-specific return formats.

For idempotent round-trips: output from `state: exists` must be usable as input to `state: present` without modification.

### Idempotency

All operations must be idempotent: running the same task twice produces no change on the second run.

**`$encrypted$` exception:** When a field is returned as `$encrypted$` it cannot be compared for equality. Convention: exclude that field from the idempotency check (treat masked value as "no change"). Document this in the module's `DOCUMENTATION` notes.

### Error messages

Use the shared error taxonomy from `plugin_utils`. Provide context: what was expected, what was found, what the user should do. Do not swallow errors silently.

---

## Coding standards (P1R9–R10)

Detailed standards are in [docs/02-action-plugin-pattern.md](docs/02-action-plugin-pattern.md). Summary of what CI enforces:

- **Type hints** mandatory on all functions (`mypy`)
- **Docstrings** mandatory on all classes and functions (`pydoclint`)
- **Argspecs derived from `DOCUMENTATION`** — no manual duplication
- **Linting**: `ruff` (replaces flake8, black, isort)

Run before pushing:

```bash
make lint        # ruff + mypy + pydoclint + ansible-lint
make unit        # pytest tests/unit/
```

---

## CasC notification (P2R4)

You **MUST** notify the CasC collections team when your PR:

| Trigger | Example |
|---------|---------|
| Adds a new module or action plugin | New file in `plugins/modules/` or `plugins/action/` |
| Changes `aap_*` / `gateway_*` auth or connection params | Edit to `plugins/doc_fragments/auth.py` |
| Changes the `RETURN` documentation or actual return structure | Modified `RETURN =` in a plugin |
| Adds a `deprecated:` block to any `DOCUMENTATION` | New deprecation notice |
| Removes or renames a parameter | Backward-incompatible param change |
| Removes a module or plugin | Deleted file in `plugins/modules/` or `plugins/action/` |

The `casc-notify-check` CI workflow detects these automatically and posts a reminder comment. **For breaking changes it will fail the check until you acknowledge notification in the PR description.**

### Notification steps

1. Create a Jira ticket in the CasC project with label `ansible.platform`
2. Tag the CasC collections team in this PR
3. For breaking changes: include a migration guide (or explicitly state no migration path exists)
4. Check the relevant boxes in the PR description **CasC Notification** section

### SLA and escalation

CasC will respond within **5 business days**. If no response, escalate to Collection Stewards or TSC. A lack of CasC bandwidth does not block merge indefinitely — Stewards can approve escalation with a follow-up ticket.

---

## Breaking changes policy (Decision 2)

- Minimum **12-month deprecation window** (unless security or critical bug)
- Add a `deprecated:` block in `DOCUMENTATION` with `removed_in: "X.Y"` and `why:`
- Add a `CHANGELOG` entry under `breaking_changes:`
- CasC team **must approve** before merge (the CasC check fails until acknowledged)
- Provide a migration guide, or explicitly state there is no migration path

---

## FQCN and backward compatibility

Existing module FQCNs (e.g. `ansible.platform.organization`) must remain stable. **Never rename a module without:**

1. Adding a redirect in `meta/routing.yml`
2. Marking the old name deprecated per the breaking changes policy above
3. Steward + TSC approval (both are CODEOWNERS on `meta/`)

---

## Review process (P2R3)

- Minimum **2 reviewers**. CODEOWNERS are auto-assigned.
- Component Leads identify appropriate reviewers if they cannot review themselves.
- Reviewers verify (where CI cannot): cross-component impact, CasC trigger completion, FQCN stability, architectural fit.
- Cross-domain PRs (shared infra + component code) need approval from **both** domains — a single reviewer cannot cover both.

### SDP and proposal reviews

Architecture changes, new connection modes, or anything with cross-PDT impact **must** have a proposal or SDP in the [ansible handbook](https://handbook.eng.ansible.com/) before the implementation PR is opened. All PDTs (Controller, Gateway, EDA, Hub) must approve the proposal. Link the handbook PR from your collection PR description.

---

## Cross-domain modules — DAB RBAC (P2 §1.5)

Several modules in this collection look like Gateway modules but are actually **cross-service**. They call DAB (django-ansible-base) RBAC endpoints that Gateway proxies, but their effect is felt inside Controller, EDA, and Hub. A change that appears to be a minor Gateway-side fix can silently break Controller inventory permissions, EDA rulebook access, or Hub namespace RBAC.

These modules require **all affected PDT approvals** before merge, not just Gateway PDT + Stewards:

| Module | Why cross-domain |
|--------|-----------------|
| `organization` | Orgs scope resources in Controller, EDA, and Hub — deleting or renaming an org cascades across all services |
| `team` | Teams govern RBAC inside Controller, EDA, and Hub — changes to membership or team resolution affect access across all services |
| `user` | Users span all services — changes to user creation, deactivation, or attribute handling have multi-service impact |
| `role_definition` | The `content_type` field references service-specific permission namespaces: `awx.*` (Controller), `eda.*` (EDA), `galaxy.*` (Hub) — a bug here grants or denies permissions inside another service |
| `role_team_assignment` | Assigns team roles such as "Organization Inventory Admin" that grant access inside Controller; also assigns EDA and Hub roles — logic errors silently drop or escalate RBAC |
| `role_user_assignment` | Same as `role_team_assignment` but for individual users |

**If your PR touches any of these six modules:**

1. CODEOWNERS will require approval from all PDTs (Controller, EDA, Hub, Gateway, Stewards)
2. In the PR description, explicitly state which services are affected and how you tested cross-service RBAC behaviour
3. For `role_definition` changes: list which `content_type` namespaces are affected
4. For assignment changes: confirm idempotency against Controller, EDA, and Hub role endpoints — not just the Gateway list endpoint

**`feature_flag` and `settings`** are Gateway-only in their API but platform-wide in their effect. They require TSC oversight on top of the normal Gateway PDT + Stewards review.

---

## Dispute resolution

When PDTs disagree on a PR: escalate to the **TSC Platform Collections**. TSC Chairs coordinate and facilitate resolution. If consensus fails, TSC makes a binding decision.

---

## Testing requirements (P2R9)

Three layers are required. All must pass before merge. See [docs/08-testing-strategy.md](docs/08-testing-strategy.md) for details.

| Layer | Runner | Requires |
|-------|--------|----------|
| Unit tests | `pytest tests/unit/` | No network; mocked dependencies |
| Molecule mock tests | `molecule test -s <scenario>_mock` | Mock Gateway server |
| Integration tests | `ansible-test integration` | Live Gateway in Docker |

Integration CI uses `pull_request_target` + `safe to test` label. Review the diff before adding the label — it grants CI access to repo secrets.

---

## OpenAPI alignment (P1R13, P2R10)

New modules should align with the OpenAPI-first strategy (ANSTRAT-1738). The central spec repo is [aap-openapi-specs](https://github.com/ansible-automation-platform/aap-openapi-specs). If your module introduces a non-spec-driven approach, document the deviation in the PR description. The Feature Architect will review for alignment during SDP/proposal approval.

---

## Platform API issues (P1R16)

Do not work around platform API shortcomings in collection code. If you encounter a missing endpoint, incorrect behavior, or API limitation:

1. Document the issue (what was expected, what happened, which endpoint)
2. File a Jira blocker against the responsible platform team
3. Reference the blocker in the collection PR — do not merge a workaround

---

## Steward team responsibilities

Stewards (not PDTs) own: CI pipeline health, collection releases and release notes, triage of incoming issues, quality gatekeeping, and collection-wide documentation. If CI is broken or a release is needed, ping the Stewards.

PDTs own: correctness of their modules, updating their modules when their component API changes, and fixing component-domain test failures.
