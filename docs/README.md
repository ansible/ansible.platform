# `ansible.platform` Documentation

This directory contains the canonical technical documentation for the `ansible.platform`
collection. The structure mirrors `cisco/meraki_rm` — a related SDK from the same team —
so developers familiar with that collection find the same patterns and numbering.

> **New to this collection?** Start with
> [13-user-module-worked-example.md](13-user-module-worked-example.md) for a
> concrete, step-by-step walkthrough of the `user` module — playbook YAML,
> expected output, HTTP calls, and data flow explained at every layer.

---

## Document Index

| # | File | Audience | Description |
|---|------|----------|-------------|
| 01 | [01-overview.md](01-overview.md) | All | Problem, vision, personas, user stories, module coverage, doc map |
| 02 | [02-resource-module-pattern.md](02-resource-module-pattern.md) | All | States (merged/deleted/gathered/replaced/overridden), entities vs endpoints, convergence contract, return value format |
| 03 | [03-sdk-architecture.md](03-sdk-architecture.md) | Architects / Senior devs | Persistent connection manager, two connection modes, RPC interface, directory structure |
| 04 | [04-data-model-transformation.md](04-data-model-transformation.md) | Framework devs | Three-tier data flow, Ansible model, API model, transform mixin, ref fields, case studies |
| 05 | [05-design-principles.md](05-design-principles.md) | All devs | 10 rules governing every decision, quality checklist, human-in-the-loop triggers |
| 06 | [06-foundation-components.md](06-foundation-components.md) | Framework devs | Full spec: Registry, Loader, BaseTransformMixin, GatewayConfig, PlatformService, PlatformManager, ManagerRPCClient, BaseResourceActionPlugin |
| 07 | [07-adding-resources.md](07-adding-resources.md) | Feature devs | Step-by-step workflow with `user` module as reference, common patterns catalog, PR checklist |
| 08 | [08-testing-strategy.md](08-testing-strategy.md) | All devs / QE | Three-layer strategy: unit (pytest), Molecule mock (with `users_mock` worked example + expected output), integration |
| 09 | [09-agent-collaboration.md](09-agent-collaboration.md) | AI agents | Personas, phase-by-phase guidance, coding standards, human-in-the-loop triggers, troubleshooting |
| 10 | [10-case-study-aap-platform.md](10-case-study-aap-platform.md) | Feature devs | Module map, identity categories, known API quirks, implementation roadmap |
| 12 | [12-generate-resource-tool.md](12-generate-resource-tool.md) | Feature devs / AI agents | Complete reference for `tools/generate_resource.py`: CLI, code flow, all generators, post-gen checklist |
| **13** | **[13-user-module-worked-example.md](13-user-module-worked-example.md)** | **All** | **Concrete examples with output.** Every state (`merged`, `deleted`, `gathered`, `replaced`, `overridden`) traced through playbook → HTTP → return value using the real `user` module |

---

## Reading Paths

### ★ "I want to see concrete examples — show me what the code actually does"
→ **[13-user-module-worked-example.md](13-user-module-worked-example.md)** ← start here

### "I want to understand what this collection does"
→ [01-overview.md](01-overview.md) → [02-resource-module-pattern.md](02-resource-module-pattern.md)

### "I want to understand the architecture"
→ [03-sdk-architecture.md](03-sdk-architecture.md) → [04-data-model-transformation.md](04-data-model-transformation.md)

### "I need to add a new resource module"
→ [13-user-module-worked-example.md](13-user-module-worked-example.md) (see how an existing module works)
→ [07-adding-resources.md](07-adding-resources.md) (step-by-step guide)
→ [05-design-principles.md](05-design-principles.md) (rules)
→ [10-case-study-aap-platform.md](10-case-study-aap-platform.md) (find your resource's identity category)
→ [12-generate-resource-tool.md](12-generate-resource-tool.md) (run the generator, then follow the post-gen checklist)

### "I'm working with an AI agent on this codebase"
→ [09-agent-collaboration.md](09-agent-collaboration.md) first, then task-specific docs

### "I need to modify the framework (manager, registry, base classes)"
→ [06-foundation-components.md](06-foundation-components.md) → [03-sdk-architecture.md](03-sdk-architecture.md)

### "I need to write or fix tests"
→ [08-testing-strategy.md](08-testing-strategy.md) (includes `users_mock` Molecule example with expected output)

---

## Document Dependency Map

```
13-user-module-worked-example  ← NEW: concrete examples, start here
  │ (makes these abstract docs tangible)
  ▼
01-overview (start here for architecture)
  │
  ├── 02-resource-module-pattern (states + return values with user examples)
  │     │
  │     └── 03-sdk-architecture (persistent connection, manager lifecycle)
  │           │
  │           ├── 04-data-model-transformation (three-tier pattern + user data flow)
  │           │
  │           └── 05-design-principles (the rules)
  │
  ├── 06-foundation-components (build the framework)
  │     │
  │     └── 07-adding-resources (use the framework, user as reference)
  │
  ├── 08-testing-strategy (test everything, users_mock as example)
  │
  ├── 09-agent-collaboration (AI agent guidance)
  │
  └── 10-case-study-aap-platform (module map, API quirks)
```

---

## Old Documentation

The previous documentation (a collection of unstructured `CAPS_NAMES.md` files) has
been preserved in `docs_old/` for reference. It is not maintained going forward.
