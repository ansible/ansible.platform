# `ansible.platform` Documentation

This directory contains the canonical technical documentation for the `ansible.platform` collection for Ansible Automation Platform (AAP) Gateway. The structure mirrors `cisco/meraki_rm` — a related SDK from the same team — so developers familiar with that collection find the same patterns and numbering.

---

## Quick Start

### For Playbook Authors

```yaml
- name: Ensure engineering team exists
  ansible.platform.team:
    name: engineering
    organization: Red Hat
    state: present
```

See [01-overview.md](01-overview.md) for the problem statement and vision.

### For Collection Developers

Start with [07-adding-resources.md](07-adding-resources.md) to add a new platform action plugin. Foundation developers should begin with [06-foundation-components.md](06-foundation-components.md).

### For AI Agents

Load [09-agent-collaboration.md](09-agent-collaboration.md) first to understand personas, phases, and quality gates.

---

## Document Index

| # | File | Audience | Description |
|---|------|----------|-------------|
| 01 | [01-overview.md](01-overview.md) | All | Problem, vision, personas, user stories, module coverage, doc map |
| 02 | [02-action-plugin-pattern.md](02-action-plugin-pattern.md) | All | States (present/absent/exists/enforced), entities vs endpoints, convergence contract |
| 03 | [03-sdk-architecture.md](03-sdk-architecture.md) | Architects / Senior devs | Persistent connection manager, two connection modes, RPC interface, directory structure |
| 04 | [04-data-model-transformation.md](04-data-model-transformation.md) | Framework devs | Three-tier data flow, Ansible model, API model, transform mixin, ref fields, case studies |
| 05 | [05-design-principles.md](05-design-principles.md) | All devs | 10 rules governing every decision, quality checklist, human-in-the-loop triggers |
| 06 | [06-foundation-components.md](06-foundation-components.md) | Framework devs | Full spec: Registry, Loader, BaseTransformMixin, GatewayConfig, PlatformService, PlatformManager, ManagerRPCClient, BaseResourceActionPlugin |
| 07 | [07-adding-resources.md](07-adding-resources.md) | Feature devs | Step-by-step 7-file workflow, complete example, common patterns catalog, PR checklist |
| 08 | [08-testing-strategy.md](08-testing-strategy.md) | All devs / QE | Three-layer strategy: unit (pytest), Molecule mock, integration; CI workflows; linting |
| 09 | [09-agent-collaboration.md](09-agent-collaboration.md) | AI agents | Personas (Foundation Builder, Feature Developer), phase-by-phase guidance, coding standards, anti-patterns, troubleshooting |
| 10 | [10-case-study-aap-platform.md](10-case-study-aap-platform.md) | Feature devs | Module map (all 22 modules), identity categories, API quirks, platform-specific challenges, version strategy |
| 11 | [11-persistent-manager-idle-timeout.md](11-persistent-manager-idle-timeout.md) | Framework devs / operators | Persistent manager idle timeout: config, semantics, edge cases, tests |

---

## Reading Paths by Role

### "I want to understand what this collection does"

→ Start here: [01-overview.md](01-overview.md)  
→ Then read: [02-action-plugin-pattern.md](02-action-plugin-pattern.md)

**Time**: 20–30 minutes

---

### "I want to understand the architecture"

→ [03-sdk-architecture.md](03-sdk-architecture.md) — Persistent manager, RPC, connection modes  
→ [04-data-model-transformation.md](04-data-model-transformation.md) — Three-tier data flow

**Prerequisites**: [01-overview.md](01-overview.md)  
**Time**: 45–60 minutes

---

### "I need to add a new platform action plugin"

→ **Primary**: [07-adding-resources.md](07-adding-resources.md) — Step-by-step 7-file workflow  
→ **Reference**: [05-design-principles.md](05-design-principles.md) — Rules to follow  
→ **Reference**: [10-case-study-aap-platform.md](10-case-study-aap-platform.md) — Find your module's identity category and API quirks

**Prerequisites**: [01-overview.md](01-overview.md), [02-action-plugin-pattern.md](02-action-plugin-pattern.md)  
**Time**: 1–2 hours + implementation time (1–4 hours per module)

---

### "I'm working with an AI agent on this codebase"

→ **Start**: [09-agent-collaboration.md](09-agent-collaboration.md)  
→ **Foundation Builder path**: Section 3 (Phases 1–4)  
→ **Feature Developer path**: Section 4 (Phases 1–7)  
→ **Reference**: [08-code-generators.md](08-code-generators.md) (optional, if implementing generators)

**Time**: 15 minutes to load; 2–8 hours for actual implementation

---

### "I need to modify the framework (manager, registry, base classes)"

→ [06-foundation-components.md](06-foundation-components.md) — Full component specification  
→ [03-sdk-architecture.md](03-sdk-architecture.md) — Architecture and manager lifecycle

**Prerequisites**: [01-overview.md](01-overview.md), [04-data-model-transformation.md](04-data-model-transformation.md)  
**Time**: 1–2 hours to understand; 4–8 hours for implementation

---

### "I need to write or fix tests"

→ [08-testing-strategy.md](08-testing-strategy.md) — Unit tests, Molecule, integration tests, CI workflows  
→ [07-adding-resources.md](07-adding-resources.md) — Test examples from the workflow

**Time**: 30–45 minutes + implementation time

### "I need to understand persistent manager idle timeout behavior"
→ [11-persistent-manager-idle-timeout.md](11-persistent-manager-idle-timeout.md)

---

## Document Dependency Map

```
01-overview (start here)
  │
  ├── 02-action-plugin-pattern (entity-centric action plugin pattern)
  │     │
  │     └── 03-sdk-architecture (persistent connection, manager lifecycle)
  │           │
  │           ├── 04-data-model-transformation (three-tier pattern)
  │           │
  │           ├── 05-design-principles (the rules)
  │           │
  │           └── 11-persistent-manager-idle-timeout (local manager idle shutdown)
  │
  ├── 06-foundation-components (build the framework)
  │     │
  │     └── 07-adding-resources (use the framework)
  │
  ├── 08-testing-strategy (test everything)
  │
  ├── 09-agent-collaboration (AI agent guidance)
  │     ├── Section 3: Foundation Builder (build framework)
  │     └── Section 4: Feature Developer (add resources)
  │
  └── 10-case-study-aap-platform (module map, API quirks, version strategy)
```

---

## Key Concepts at a Glance

### The Problem
Naïve 1:1 API endpoint → module mapping produces 100+ modules where a single logical operation (create a user and assign to org) requires multiple tasks with manual ID resolution.

### The Solution
**Platform SDK** with:
- **Persistent connection manager** — One HTTP session for the entire play
- **Versioned data model** — Stable Ansible interface regardless of API version
- **22 action plugins** — One per logical entity, not endpoint

### The Three Tiers
```
Playbook task
      │
      ▼
Ansible Model (e.g., AnsibleUser with username: "alice")
      │
      ▼
Transform Mixin (maps Ansible ↔ API, resolves name↔ID)
      │
      ▼
API Model (e.g., APIUser_v1 with integer organization IDs)
      │
      ▼
HTTP to AAP Gateway API
```

### Persistent Manager
- Action plugins spawn a manager subprocess (Python multiprocessing)
- Manager owns the HTTP session (one per play)
- Action plugins talk to manager via Unix domain socket RPC
- Solves fork-safety on macOS + Python 3.12
- Auto-terminates after idle timeout (prevents orphaned processes)

### Version Compatibility
- `api/v1/` directory for AAP 2.6 (current release)
- `api/v2/` directory for AAP 2.7+ (upcoming — add when API changes ship)
- Ansible interface (`AnsibleUser`, etc.) never changes across versions
- Registry auto-detects API version and routes to correct mixin
- Fallback to latest available version if exact match not found

---

## File Organization

```
docs/
  01-overview.md                         ← Start here
  02-action-plugin-pattern.md
  03-sdk-architecture.md
  04-data-model-transformation.md
  05-design-principles.md
  06-foundation-components.md
  07-adding-resources.md
  08-testing-strategy.md
  09-agent-collaboration.md              ← For AI agents
  10-case-study-aap-platform.md
  README.md                              ← You are here
```

---

## Contributing

### Adding a New Resource Module

1. Read [07-adding-resources.md](07-adding-resources.md) — covers 7-file workflow
2. Use [10-case-study-aap-platform.md](10-case-study-aap-platform.md) to understand your module's identity category
3. Follow [05-design-principles.md](05-design-principles.md) rules
4. Write tests per [08-testing-strategy.md](08-testing-strategy.md)
5. Use AI agent assistance: follow [09-agent-collaboration.md](09-agent-collaboration.md) for roles and phases

### Working with AI Agents

1. Load [09-agent-collaboration.md](09-agent-collaboration.md) first
2. Agent identifies your role (Foundation Builder or Feature Developer)
3. Agent loads task-specific docs from Section 10
4. Agent follows persona walkthrough (Section 3 or 4)
5. Agent applies coding standards (Section 8)

**Quality gates**: Agent must pass checklist (Section 9) before human review.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Ansible Model** | Stable, user-facing dataclass (e.g., `AnsibleUser`). Never changes. |
| **API Model** | Version-specific Gateway API dataclass (e.g., `APIUser_v1`). Integer IDs, camelCase. |
| **Transform Mixin** | Bidirectional mapper between Ansible and API models. Contains business logic. |
| **PlatformManager** | Subprocess running PlatformService. Owns HTTP session. |
| **PlatformService** | HTTP client + transform engine inside the manager. |
| **ManagerRPCClient** | Client-side stub for communicating with PlatformManager. |
| **Persistent mode** | Action plugin keeps manager alive across multiple tasks. Recommended. |
| **Ephemeral mode** | Manager spawns and dies per task. Higher latency. Fallback only. |
| **Lookup field** | Unique identifier for a resource (e.g., `username` for user). |
| **Ref field** | Field containing a reference to another resource (e.g., `organization` in team). |
| **Write-only field** | Accepted on create/update but never returned by API (e.g., `password`). |
| **Idempotent** | `state: present` returns `changed: false` if resource already matches desired state. |

---

## FAQs

**Q: Do I need to understand all 10 documents?**  
A: No. Use the reading paths above to find the minimum set for your task.

**Q: Can I use this collection with AI code generation?**  
A: Yes. See [09-agent-collaboration.md](09-agent-collaboration.md) for personas and quality gates.

**Q: How do new AAP versions get supported?**  
A: Add a new `api/v<N>/` directory. Registry auto-discovers. No action plugin changes. See [10-case-study-aap-platform.md](10-case-study-aap-platform.md) Section 6.

**Q: What's the idle_timeout for?**  
A: Prevents orphaned manager processes after playbook failure or cancellation. Default 3600s. See [01-overview.md](01-overview.md) and [10-case-study-aap-platform.md](10-case-study-aap-platform.md).

**Q: Can I modify the framework?**  
A: Yes, but it requires careful review. See [06-foundation-components.md](06-foundation-components.md) and [09-agent-collaboration.md](09-agent-collaboration.md) Section 3 (Foundation Builder).

---

## Version History

| Version | Date | Notable Changes |
|---------|------|-----------------|
| 1.0 | 2025-Q1 | Initial 22-module release; AAP 2.6 support |
| 1.1 | 2025-Q2 | idle_timeout feature; integration test coverage; backward compat fixes |
| 1.2 | 2025-Q3 | AAP 2.7 support via v2 transform mixins (when API changes ship) |

---

## License

See [LICENSE](../LICENSE).
