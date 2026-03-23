# Overview — `ansible.platform` Collection

## The Problem

Ansible Automation Platform (AAP) Gateway exposes a REST API that covers dozens of
resource types: users, organizations, teams, authenticators, service clusters, routes,
HTTP ports, role definitions, application registrations, and more. A naive approach to
building an Ansible collection for this API would be to generate one module per endpoint
— producing a collection with 100+ modules where configuring a single logical resource
like "create a user and assign it to an organization" requires chaining multiple tasks
with manual ID lookups.

The result is an API client with YAML syntax, not infrastructure automation.

Users are forced to understand the Gateway's internal REST structure, handle pagination,
resolve names to IDs, manage multi-step operations in the correct order, and write their
own idempotency guards. This is not a sustainable pattern.

There is a second problem: **connection lifecycle**. Gateway API calls from Ansible
workers spawn a new HTTP session per task. For a playbook managing 50 resources, this
means 50 separate authentication round-trips — a significant performance drag and a
source of race conditions when credentials are rotated mid-play.

## The Vision

`ansible.platform` is built as a **platform SDK** that expresses entity-centric,
state-driven resource management over the AAP Gateway API. The SDK manages
**configuration entities** — users, organizations, authenticators, service clusters —
not raw API endpoints.

The architecture has two core properties:

1. **Persistent connection manager**: A long-lived Python process holds the HTTP session
   and credential state. Action plugins communicate with it via RPC. The same session is
   reused for every task in a play, eliminating per-task authentication overhead.

2. **Versioned data model**: Ansible-facing dataclasses (`AnsibleUser`, `AnsibleOrganization`,
   etc.) form a stable contract that never changes regardless of the underlying API version.
   Version-specific API models (`APIUser_v1`, `APIUser_v2`) and transform mixins handle
   the translation layer automatically.

The target is clear:

| Metric | Direct API calls | `ansible.platform` SDK |
|--------|-----------------|------------------------|
| HTTP sessions per playbook | One per task | One for the entire play |
| Name-to-ID resolution | Caller's problem | Built-in |
| Multi-step operations | Manual chaining | Transparent |
| API version compatibility | Caller must handle | Automatic version detection + fallback |
| Idempotency | Manual comparison | Built-in state comparison |
| check_mode support | Not possible | Supported on all resources |

## Personas

### Playbook Author

Writes playbooks to automate AAP infrastructure configuration. Expects stable,
simple interfaces with Ansible-standard naming conventions. Does not want to know
whether the underlying API has changed between AAP versions.

**What they care about:**
- Write once, works across AAP versions
- Clear parameter validation errors at task time
- Idempotent operations — safe to re-run in CI/CD pipelines
- `state: absent` for cleanup, `state: present` for convergence
- Output keys match input parameter names

**Example:**
```yaml
- name: Ensure engineering team exists in the platform
  ansible.platform.team:
    name: engineering
    organization: Red Hat
    state: present
```

### Collection Developer

Builds and maintains the `ansible.platform` collection. Wants to add new resource
modules without repeating boilerplate — the framework handles argument spec generation,
input validation, output validation, connection management, and version routing.

**What they care about:**
- Adding a new resource in < 2 hours
- Clear pattern: Ansible model → API model → transform mixin → action plugin
- Transform mixin is the only place to write custom logic
- `BaseResourceActionPlugin` handles everything else
- Registry auto-discovers new API versions without code changes

### Platform Team

Maintains the AAP Gateway API and its versioned OpenAPI specifications. Needs new
Gateway API versions to be supported in the collection with minimum friction.

**What they care about:**
- New API version = new `api/v<N>/` directory with updated dataclasses and mixins
- Registry auto-discovers the new version on startup
- Old playbooks continue to work via version fallback
- Stable Ansible-facing interface never broken by API changes

### AI Agent / Code Generator

Assists collection developers by generating boilerplate (Ansible models, API models,
transform mixin stubs, action plugin skeletons) from the `DOCUMENTATION` string in a
module stub file.

**What they care about:**
- `DOCUMENTATION` string is the single source of truth for module interface
- Clear, mechanical patterns to follow for each layer
- `09-agent-collaboration.md` defines quality gates and boundaries

## User Stories

### Playbook Author Stories

**Stable module interface**: Use the same module YAML across AAP 2.4, 2.5, and 3.x
without playbook changes. The collection detects the API version automatically.

**Idempotent operations**: Run the same playbook multiple times without side effects.
`changed: false` when the resource already matches desired state. `changed: true` only
when something was actually modified on the platform.

**Multi-resource operations**: Assign a user to an organization, role, and team in a
single play. Name resolution (org name → ID) is automatic.

**Safe dry-run**: Use `check_mode: true` on any task to preview what would change
without touching the platform.

### Collection Developer Stories

**Generate from docstring**: Write `DOCUMENTATION` in a stub module file. Run the
generator to produce the `AnsibleFoo` dataclass. The docstring IS the module interface.

**Implement only the business logic**: Write one transform mixin class that maps
Ansible fields to API fields. The base classes handle everything else.

**Version independently**: Add `api/v2/foo.py` to support a new API version. The
registry auto-discovers it. The v1 mixin continues to serve older platforms.

**Test with a mock server**: Run `molecule converge` with the mock Gateway server to
test idempotency without a live AAP instance. The mock reproduces the real API contract.

### System Administrator Stories

**Fast playbook execution**: Enable `persistent: true` on the connection to reuse the
HTTP session across all tasks. Playbook execution is 50–75% faster for plays with
many tasks.

**Clear error messages**: Validation errors report which field failed and why. API
errors include the HTTP status and the Gateway error response body. Version
compatibility issues log a clear warning and the fallback version used.

**Works across AAP versions**: The collection automatically detects the Gateway API
version and routes to the correct implementation. No `api_version:` override needed
in normal operation.

## Success Metrics

### For Playbook Authors
- Write once, works across AAP versions without modification
- Idempotent — safe to run in CI/CD pipelines daily
- `check_mode` supported on every resource
- Clear, actionable error messages

### For Collection Developers
- New resource module in < 2 hours
- Transform mixin is the only custom code required per resource
- New API version = new directory, no framework changes
- Single `DOCUMENTATION` string defines the stable interface

### For Platform Team
- Automatic version detection and fallback
- No collection changes needed for backward-compatible API updates
- Version compatibility matrix is implicit in the directory structure

## Technical Stack

### Core Technologies
- **Python 3.11+** — type hints, dataclasses, `multiprocessing.managers`
- **ansible-core 2.16+** — action plugins, `ArgumentSpecValidator`, connection plugins
- **requests** — HTTP session management inside the manager process
- **PyYAML** — DOCUMENTATION string parsing for argspec generation
- **multiprocessing** — persistent manager process (Unix domain socket RPC)

### Key Abstractions
- **`AnsibleModel` dataclasses** — stable user-facing interface, never changes
- **`APIModel` dataclasses** — version-specific API wire format
- **`TransformMixin`** — field mapping + business logic between the two tiers
- **`PlatformService`** — the HTTP client + transform engine running in the manager process
- **`BaseResourceActionPlugin`** — base class wiring all 22 action plugins to the framework
- **`APIVersionRegistry`** — auto-discovers api/v*/ directories at startup
- **`DynamicClassLoader`** — loads the right (AnsibleClass, APIClass, MixinClass) tuple

### Module Coverage (22 resources)

| Domain | Modules |
|--------|---------|
| Identity | `user`, `organization`, `team` |
| Authentication | `authenticator`, `authenticator_map`, `authenticator_user` |
| Access Control | `role_definition`, `role_user_assignment`, `role_team_assignment` |
| Services | `service`, `service_cluster`, `service_type`, `service_key`, `service_node` |
| Platform Config | `http_port`, `route`, `ui_plugin_route`, `settings`, `feature_flag` |
| Security | `ca_certificate`, `token` |
| Applications | `application` |

## Document Guide

This documentation suite mirrors the structure of `cisco/meraki_rm` — a related SDK
from the same team — so developers familiar with that collection find the same patterns
and document numbering.

### For Product Managers / Architects
Start here (`01-overview.md`), then:
- [02-resource-module-pattern.md](02-resource-module-pattern.md) — what resource modules are
- [03-sdk-architecture.md](03-sdk-architecture.md) — persistent manager and connection modes

### For Architects / Senior Developers
All of the above, plus:
- [04-data-model-transformation.md](04-data-model-transformation.md) — three-tier data flow
- [05-design-principles.md](05-design-principles.md) — guardrails and design rules

### For Developers Building the Framework
All of the above, plus:
- [06-foundation-components.md](06-foundation-components.md) — full spec for all core components

### For Developers Adding Resources
- [07-adding-resources.md](07-adding-resources.md) — step-by-step workflow with complete examples
- [05-design-principles.md](05-design-principles.md) — rules to follow

### For AI Agents
- [09-agent-collaboration.md](09-agent-collaboration.md) — personas, phases, coding standards

### For Testing
- [08-testing-strategy.md](08-testing-strategy.md) — mock server, Molecule, integration, unit tests

### Document Dependency Map

```
01-overview (you are here)
  |
  +-- 02-resource-module-pattern (what resource modules are)
  |     |
  |     +-- 03-sdk-architecture (persistent connection, manager lifecycle)
  |           |
  |           +-- 04-data-model-transformation (three-tier pattern)
  |           |
  |           +-- 05-design-principles (the rules)
  |
  +-- 06-foundation-components (build the framework)
  |     |
  |     +-- 07-adding-resources (use the framework)
  |
  +-- 08-testing-strategy (test everything)
  |
  +-- 09-agent-collaboration (AI agent guidance)
  |
  +-- 10-case-study-aap-platform (concrete module map)
```

### Time Estimates

| Task | Who | First Time | Subsequent |
|------|-----|-----------|------------|
| Add simple resource | Feature developer | 1–2 hours | 1 hour |
| Add complex resource | Feature developer | 2–4 hours | 1–2 hours |
| Add API version for existing resource | Framework developer | 30 min | 30 min |
| Add new API version globally | Framework developer | 1–2 hours | N/A |
| Write mock scenario for a resource | QE / developer | 1–2 hours | 30 min |
