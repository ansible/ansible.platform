# `ansible.platform` Documentation

This directory contains the canonical technical documentation for the `ansible.platform`
collection. The structure mirrors `cisco/meraki_rm` — a related SDK from the same team —
so developers familiar with that collection find the same patterns and numbering.

---

## Document Index

| # | File | Audience | Description |
|---|------|----------|-------------|
| 01 | [01-overview.md](01-overview.md) | All | Problem, vision, personas, user stories, module coverage, doc map |
| 02 | [02-resource-module-pattern.md](02-resource-module-pattern.md) | All | States (present/absent/exists/enforced), entities vs endpoints, convergence contract |
| 03 | [03-sdk-architecture.md](03-sdk-architecture.md) | Architects / Senior devs | Persistent connection manager, two connection modes, RPC interface, directory structure |
| 04 | [04-data-model-transformation.md](04-data-model-transformation.md) | Framework devs | Three-tier data flow, Ansible model, API model, transform mixin, ref fields, case studies |
| 05 | [05-design-principles.md](05-design-principles.md) | All devs | 10 rules governing every decision, quality checklist, human-in-the-loop triggers |
| 06 | [06-foundation-components.md](06-foundation-components.md) | Framework devs | Full spec: Registry, Loader, BaseTransformMixin, GatewayConfig, PlatformService, PlatformManager, ManagerRPCClient, BaseResourceActionPlugin |
| 07 | [07-adding-resources.md](07-adding-resources.md) | Feature devs | Step-by-step 7-file workflow, complete example, common patterns catalog, PR checklist |
| 08 | [08-testing-strategy.md](08-testing-strategy.md) | All devs / QE | Three-layer strategy: unit (pytest), Molecule mock, integration; CI workflows; linting |
| 09 | [09-agent-collaboration.md](09-agent-collaboration.md) | AI agents | Personas, phase-by-phase guidance, coding standards, human-in-the-loop triggers, troubleshooting |
| 10 | [10-case-study-aap-platform.md](10-case-study-aap-platform.md) | Feature devs | Module map, identity categories, known API quirks, implementation roadmap |
| 11 | [11-persistent-manager-idle-timeout.md](11-persistent-manager-idle-timeout.md) | Framework devs / operators | Persistent manager idle timeout: config, semantics, edge cases, tests |

---

## Reading Paths

### "I want to understand what this collection does"
→ [01-overview.md](01-overview.md) → [02-resource-module-pattern.md](02-resource-module-pattern.md)

### "I want to understand the architecture"
→ [03-sdk-architecture.md](03-sdk-architecture.md) → [04-data-model-transformation.md](04-data-model-transformation.md)

### "I need to add a new resource module"
→ [07-adding-resources.md](07-adding-resources.md) (primary)
→ [05-design-principles.md](05-design-principles.md) (rules)
→ [10-case-study-aap-platform.md](10-case-study-aap-platform.md) (find your resource's identity category)

### "I'm working with an AI agent on this codebase"
→ [09-agent-collaboration.md](09-agent-collaboration.md) first, then task-specific docs

### "I need to modify the framework (manager, registry, base classes)"
→ [06-foundation-components.md](06-foundation-components.md) → [03-sdk-architecture.md](03-sdk-architecture.md)

### "I need to write or fix tests"
→ [08-testing-strategy.md](08-testing-strategy.md)

### "I need to understand persistent manager idle timeout behavior"
→ [11-persistent-manager-idle-timeout.md](11-persistent-manager-idle-timeout.md)

---

## Document Dependency Map

```
01-overview (start here)
  │
  ├── 02-resource-module-pattern (what resource modules are)
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
  │
  └── 10-case-study-aap-platform (module map, API quirks)
```

---

## Old Documentation

The previous documentation (a collection of unstructured `CAPS_NAMES.md` files) has
been preserved in `docs_old/` for reference. It is not maintained going forward.
