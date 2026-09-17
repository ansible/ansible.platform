---
name: platform-onboarding
description: >
  Guided developer onboarding for the ansible.platform collection. Use this skill
  whenever a new engineer is joining the team, someone asks "where do I start" or
  "how does this collection work", or when onboarding a contributor who needs to
  understand the architecture, codebase layout, development workflow, or how to add
  new resource modules. Also trigger for phrases like "onboard me", "ramp up on
  platform", "walk me through the codebase", "I'm new to this collection", or
  "help me understand the platform SDK". Even if the person just says "I need to
  add a new module" without context, use this skill — they likely need the
  onboarding path first.
---

# Platform Collection Developer Onboarding

Guide a new engineer from zero knowledge to productive contributor on the
`ansible.platform` collection. This skill leverages the existing `docs/` directory
(11 structured documents) as progressive disclosure — read them on behalf of the
engineer and synthesize guidance rather than asking them to read everything.

## How This Skill Works

This is a **guided workflow**, not a reference doc. Walk the engineer through
five phases in order. Each phase has a learning goal, specific docs to consult,
and a hands-on exercise to confirm understanding.

Adapt pacing to the engineer's experience level:
- **Ansible-experienced, new to this collection** → move quickly through Phase 1,
  spend time on Phases 2–3; do NOT skip to Phase 4 even if they mention adding a
  module — they need the architecture context first or the seven-file workflow
  won't make sense
- **New to Ansible entirely** → spend extra time on Phase 1, provide more context
  on connection plugins and action plugins vs modules
- **Already familiar with this collection's architecture AND adding a specific
  module** → skip to Phase 4 directly; confirm they know what action plugins,
  transform mixins, and the Registry are before proceeding

If unsure which profile fits, ask one question: "Have you worked with this
collection before, or is this your first time in the codebase?" That answer
determines whether they go through Phases 1–3 or jump to Phase 4.

---

## Phase 1: Orientation (30 min)

**Goal**: Understand what this collection does, why it exists, and the problem it solves.

### What to cover

Read `docs/01-overview.md` and summarize these key points for the engineer:

1. **The problem**: Naïve 1:1 API-to-module mapping would produce 100+ modules.
   A single logical operation (create user + assign to org) would require multiple
   tasks with manual ID resolution.

2. **The solution**: The Platform SDK provides 22 action plugins (one per logical
   entity, not per endpoint), a persistent connection manager (one HTTP session per
   play), and a versioned data model (stable Ansible interface regardless of API
   version changes).

3. **Who uses it**: Playbook authors managing AAP 2.5+ Gateway resources — users,
   teams, organizations, applications, authenticators, services, etc.

Show a simple playbook example:
```yaml
- name: Ensure engineering team exists
  ansible.platform.team:
    name: engineering
    organization: Red Hat
    state: present
```

Then read `docs/02-action-plugin-pattern.md` and explain:
- The four states: `present`, `absent`, `exists`, `enforced`
- Entity-centric vs endpoint-centric design
- The convergence contract (idempotent by default)

### Exercise 1

Ask the engineer to answer:
> "If I want to create a user named `alice` in the `Engineering` org, how many
> tasks would I need with this collection vs a raw API approach?"

Expected answer: One task with `ansible.platform.user` (the collection resolves
the org name → ID automatically) vs multiple tasks with raw API calls.

---

## Phase 2: Architecture Deep Dive (45–60 min)

**Goal**: Understand the three-tier data model, persistent manager subprocess,
and RPC communication pattern.

### The Three Tiers

Read `docs/04-data-model-transformation.md` and explain:

```
Playbook task parameters
        ↓
Ansible Model (AnsibleUser — stable, user-facing dataclass)
        ↓
Transform Mixin (maps fields, resolves name→ID references)
        ↓
API Model (APIUser_v1 — version-specific, matches Gateway API)
        ↓
HTTP request to AAP Gateway
```

Key concepts to emphasize:
- **Ansible Models** never change across API versions (user-facing stability)
- **API Models** are version-specific (`v1/`, `v2/` directories)
- **Transform Mixins** contain the business logic (field mapping, ref resolution)
- The **Registry** auto-detects the Gateway API version and routes to the correct
  mixin — no action plugin changes needed for new API versions

### The Persistent Manager

Read `docs/03-sdk-architecture.md` and explain:

- Action plugins spawn a **manager subprocess** (`PlatformManager`) via Python
  `multiprocessing`
- The manager owns the HTTP session (one per play, solving fork-safety on
  macOS + Python 3.12)
- Action plugins communicate via **Unix domain socket RPC** using
  `ManagerRPCClient`
- Two connection modes: **persistent** (recommended, manager lives across tasks)
  and **direct** (ephemeral, higher latency, fallback)
- The manager auto-terminates after an idle timeout (prevents orphans)

### Exercise 2

Ask the engineer to trace a request mentally:
> "When a playbook runs `ansible.platform.team: name: engineering state: present`,
> what happens step by step? Name the key classes involved."

Expected trace: ActionModule → base_action.py `_get_or_spawn_manager()` →
ManagerRPCClient → Unix socket → PlatformService.execute() → Transform Mixin
(AnsibleTeam → APITeam_v1) → HTTP to Gateway API.

---

## Phase 3: Codebase Navigation (30 min)

**Goal**: Know where everything lives and how to find things.

### Directory Map

Present this layout and explain each directory's purpose:

```
plugins/
  action/              # Action plugins (one per resource entity)
    base_action.py     # Base class — ALL action plugins inherit from this
    organization.py    # Pattern A: 3 lines (simplest)
    user.py            # Pattern C: thin run() orchestration (still uses manager.execute())
  modules/             # Module doc stubs (DOCUMENTATION + EXAMPLES only)
  connection/
    http.py            # Connection plugin — persistent vs direct mode routing
  plugin_utils/
    manager/
      platform_manager.py   # PlatformService + PlatformManager (subprocess)
      process_manager.py    # Spawning, socket management, cleanup
      manager_process.py    # Subprocess entry point (main())
      rpc_client.py         # Client-side RPC stub
    ansible_models/         # Stable Ansible-facing dataclasses
    api/
      v1/                   # Version-specific API models + transform mixins
    platform/
      registry.py           # Auto-discovers modules and API versions

tests/
  unit/                # Layer 1: pytest, mocked, no network
  integration/         # Layer 3: live AAP instance
extensions/
  molecule/            # Layer 2: mock Gateway server tests

docs/                  # 11 structured documents (you're using them now)
tools/
  generate_resource.py # Boilerplate generator for new modules
```

### The Three Plugin Patterns

Read `docs/07-adding-resources.md` briefly and explain:

- **Pattern A** (declarative): 3-line action plugin, no custom logic. Example:
  `organization.py`. Used when fields map 1:1 to API.
- **Pattern B** (hook-based): Overrides specific hooks (`_pre_create`,
  `_post_update`). Used when you need side effects or extra validation.
- **Pattern C** (orchestration): Overrides `run()` for multi-step workflows that still
  call `manager.execute()` only. Example: `user.py`. **Not** for HTTP, associations,
  or secondary endpoints — those belong in the transform mixin (see
  `docs/09-agent-collaboration.md` §10 and `docs/07-adding-resources.md` §4a).

### Exercise 3

Ask the engineer to:
> "Open `plugins/action/organization.py` and `plugins/action/user.py`.
> What pattern does each use? Why is `user.py` more complex?"

Then have them find:
> "Where does the AnsibleTeam dataclass live? Where is its v1 API counterpart?"

Expected: `plugins/plugin_utils/ansible_models/team.py` and
`plugins/plugin_utils/api/v1/team.py`.

---

## Phase 4: Adding a New Resource Module (1–2 hours)

**Goal**: Walk through the seven-file workflow to add a new resource.

Read `docs/07-adding-resources.md` in full — it contains the step-by-step guide.
Also read `references/cheatsheet.md` from this skill for a condensed summary.

### The Seven Files

| # | File | Generated? |
|---|------|-----------|
| 1 | `plugins/modules/<resource>.py` | Yes — DOCUMENTATION scaffold |
| 2 | `plugins/plugin_utils/ansible_models/<resource>.py` | Yes — AnsibleFoo dataclass |
| 3 | `plugins/plugin_utils/api/v1/<resource>.py` | Partial — skeleton + manual mixin |
| 4 | `plugins/action/<resource>.py` | Yes — ActionModule skeleton |
| 5 | `tests/integration/targets/<resource>s_test/` | Scaffold — manual completion |
| 6 | `extensions/molecule/<resource>_mock/` | Manual |
| 7 | `tests/unit/` (optional) | Manual |

### Generator Command — Use It First

**IMPORTANT**: Before hand-writing any files, always try the generator. It reads
the OpenAPI spec and produces correctly structured files that follow existing
patterns. Hand-writing skips established conventions and introduces bugs
(wrong paths, missing FK resolution, incorrect read-only field classification).

```bash
# Gateway resources (default)
python tools/generate_resource.py \
    --tag <openapi_tag> \
    --spec ../aap-openapi-specs/2.6/gateway.json \
    --dry-run

# EDA resources — service label auto-detected from /api/eda/ path prefix
python tools/generate_resource.py \
    --tag projects \
    --spec ../aap-openapi-specs/eda.json \
    --dry-run

# Hub resources
python tools/generate_resource.py \
    --tag <tag> \
    --spec ../aap-openapi-specs/hub.json \
    --dry-run

# List available tags in any spec
python tools/generate_resource.py --spec <spec.json> --list-tags
```

Always run with `--dry-run` first to preview output. The generator auto-detects
the service type (gateway/eda/hub/controller) from the API path prefix and
adjusts docstrings accordingly. Use `--service <label>` to override if needed.

After generation, review and customize the output — especially the transform
mixin's `from_ansible_data()` method, which may need manual FK resolution logic
for reference fields (e.g., `organization` name → `organization_id`).

### Service-Specific Path Prefixes

Different AAP services use different API path prefixes. The generator detects
these automatically, but when writing or reviewing transform mixins, verify
the `get_endpoint_operations()` paths match the correct service:

| Service | API Prefix | Example |
|---------|-----------|---------|
| Gateway | `/api/gateway/v1/` | `/api/gateway/v1/teams/` |
| EDA | `/api/eda/v1/` | `/api/eda/v1/projects/` |
| Hub | `/api/hub/v3/` | `/api/hub/v3/namespaces/` |
| Controller | `/api/controller/v2/` | `/api/controller/v2/job_templates/` |

Getting this prefix wrong is a common mistake — EDA resources routed to
`/api/gateway/v1/` will return 404s silently.

### Key Decisions the Engineer Must Make

When implementing the transform mixin, they need to understand:

1. **Lookup field**: What uniquely identifies this resource? (e.g., `username`
   for user, `name` for team)
2. **Ref fields**: Which fields reference other resources by name that need
   name→ID resolution? (e.g., `organization` on team)
3. **Write-only fields**: Fields accepted on create/update but never returned
   by GET (e.g., `password` on user)
4. **Identity category**: Check `docs/10-case-study-aap-platform.md` to find
   where the resource fits in the module map

### Exercise 4

If a real module needs adding, use that. Otherwise, use a hypothetical:
> "Walk through what files you'd create for a `notification_template` resource.
> Which pattern (A, B, or C) would you choose and why?"

---

## Phase 5: Testing & PR Workflow (30–45 min)

**Goal**: Understand the three testing layers and how to get a PR merged.

### Testing Strategy

Read `docs/08-testing-strategy.md` and explain the three layers:

| Layer | Tool | What it catches |
|-------|------|----------------|
| 1: Unit | `pytest tests/unit/ -v` | Framework logic bugs, mocked |
| 2: Molecule | `molecule test -s <resource>_mock` | Idempotency, state machine, no live AAP |
| 3: Integration | Live AAP + `safe to test` label | End-to-end against real Gateway API |

### PR Checklist

From `CONTRIBUTING.md` and `docs/07-adding-resources.md`:

1. Reference a Jira issue: `[AAP-XXXXX] Short description`
2. Fill the PR template completely
3. All three test layers pass
4. Apply `safe to test` label to trigger integration CI
5. Minimum 2 approvals required
6. If the change affects modules, auth, or return values → tag CasC team

### Design Principles

Read `docs/05-design-principles.md` and highlight the top rules:
- Idempotent by default (`state: present` returns `changed: false` if already matching)
- One module per logical entity (not per endpoint)
- Ansible Model never changes (API version changes go in new `api/vN/` directories)
- Fail loudly on unknown states (no silent defaults)

### Exercise 5

Ask the engineer:
> "You've added a new `notification_template` module. Write the pytest command to
> run just unit tests. Then describe what a Molecule mock scenario would verify
> that unit tests can't."

Expected: `pytest tests/unit/ -v -k notification` for unit tests. Molecule verifies
idempotency (run twice, second run shows `changed: false`) and the full
create→update→delete state machine against the mock server.

---

## Completion Checklist

After all five phases, the engineer should be able to answer:

- [ ] What problem does this collection solve vs raw API modules?
- [ ] What are the three data tiers (Ansible Model → Transform Mixin → API Model)?
- [ ] How does the persistent manager subprocess work?
- [ ] Where do action plugins, ansible models, and API models live in the tree?
- [ ] What are the three plugin patterns (A, B, C) and when to use each?
- [ ] What are the SDK execution invariants (no HTTP in action plugins; MCP parity)?
- [ ] What are the seven files needed for a new resource module?
- [ ] How to run unit tests, Molecule tests, and integration tests?
- [ ] What's the PR workflow (Jira reference, labels, approvals, CasC)?

---

## Additional Resources

For deeper dives beyond onboarding, point the engineer to:

| Topic | Document |
|-------|----------|
| Foundation framework internals | `docs/06-foundation-components.md` |
| AI agent collaboration | `docs/09-agent-collaboration.md` |
| Module map & API quirks | `docs/10-case-study-aap-platform.md` |
| Manager idle timeout | `docs/11-persistent-manager-idle-timeout.md` |
| Quick reference cheatsheet | `references/cheatsheet.md` (in this skill) |
| Reading paths by role | `docs/README.md` |

---

## Notes for the Guiding Agent

- Always read the relevant `docs/` file before explaining a topic — don't rely
  on memory alone, the docs may have been updated
- Adapt depth to the engineer's questions. If they ask "why Unix sockets instead
  of HTTP?", that's a sign they want the architecture deep dive. If they ask
  "just show me how to add a module", skip to Phase 4.
- Use real code examples from the collection whenever possible (e.g., show the
  actual `organization.py` which is only 14 lines)
- The exercises are not tests — they're comprehension checks. Help the engineer
  arrive at the answer rather than quizzing them
- **When adding a new module, always use `tools/generate_resource.py` first.**
  Run with `--dry-run` to preview, then generate, then customize. Do NOT
  hand-write files from scratch — the generator ensures correct path prefixes,
  field classification, and adherence to existing patterns. Hand-written files
  consistently produce bugs: wrong endpoint paths, missing FK resolution,
  read-only fields misclassified as writable, and `logger.info` where existing
  code uses `logger.debug`.
- **Verify endpoint paths match the service type.** EDA uses `/api/eda/v1/`,
  not `/api/gateway/v1/`. This is the single most common mistake when adding
  non-Gateway modules. The generator handles this automatically.
- **Never add HTTP to action plugins.** No `manager.session`, no `import requests`.
  Associations, surveys, and copy workflows go in the transform mixin so MCP (#206)
  and other SDK consumers stay in parity. Run `make check_action_plugin_invariants`.
  Read `docs/09-agent-collaboration.md` §10 before customizing `plugins/action/`.
- **Never poll job status in action plugins.** `wait` / `interval` / `timeout` belong in
  `PlatformService.execute()` (see `docs/07-adding-resources.md` §4c and PR #227).
