# One SDK, Two Surfaces: The Case for MCP-Native `ansible.platform`

## The Thesis

A good MCP tool and a good Ansible module are the same thing: typed inputs, deterministic
behavior, idempotent state management, structured output. The `ansible.platform` SDK
already implements all of these properties for 22 AAP Gateway resources. A thin MCP
transport layer exposes every resource to AI agents — with the same schema, the same
validation, and the same deterministic behavior — without duplicating a single line of
business logic.

The investment is not "build an MCP server." The investment is "add a second front door
to an SDK that already exists."

---

## The Problem

Playbooks are the right tool for planned, repeatable automation. They are version-controlled,
peer-reviewed, and executed in CI/CD pipelines. Nothing in this document proposes replacing
them.

But the way engineers interact with infrastructure is changing. The pattern is shifting from
"write a playbook, run it, read the output" to "tell an agent what you need, review what it
did." This is not a future prediction — it is happening now across every major cloud provider,
CI platform, and developer tool.

Today, an engineer who wants to create a user, assign it to an organization, and grant a role
has two options:

1. **Write a playbook** — 15-40 lines of YAML, test it, commit it, run it. Correct, but slow
   for ad-hoc work.
2. **Hit the API directly** — curl or a script. Fast, but no idempotency, no validation, no
   name-to-ID resolution. Error-prone.

There is no third option. There is no way to say "create user jdoe in the engineering org
with the Team Admin role" and have a system that understands AAP's resource model do it
correctly, idempotently, and with full audit trail.

The MCP ecosystem is filling this gap for databases, cloud providers, and SaaS platforms.
Enterprise automation has no serious entry. AAP can own this space.

---

## Why This Codebase Is Already There

The `ansible.platform` SDK was not designed for MCP — but its architecture satisfies every
requirement for dynamic tool generation:

**1. Universal execution interface.** `PlatformService.execute()` takes three arguments —
an operation string (`create`, `update`, `delete`, `find`), a module name (`user`,
`organization`, `team`), and a plain Python dict of parameters. It returns a plain dict.
No Ansible runtime, no playbook context, no YAML parsing required.

```python
service = PlatformService(GatewayConfig(base_url=url, username=user, password=pw))
result = service.execute("create", "user", {"username": "jdoe", "email": "jdoe@example.com"})
```

**2. Self-describing modules.** Every module carries a `DOCUMENTATION` YAML string that
declares field names, types, required flags, choices, defaults, and descriptions. The
`_build_argspec_from_docs()` method already parses this into a structured dict at runtime.
This is the same metadata an MCP tool needs for its `inputSchema`.

**3. Typed dataclasses.** The `ansible_models/` layer uses standard Python dataclasses with
type hints (`str`, `Optional[bool]`, `List[str]`). These map directly to JSON Schema
types — the format MCP uses for tool definitions. `dataclasses.fields()` and
`typing.get_type_hints()` extract everything needed for schema generation.

**4. Auto-discovery.** `APIVersionRegistry` scans the filesystem to discover all available
resources. No hardcoded module list. Add a new resource to the collection and the MCP
server picks it up on next startup.

The SDK's layered architecture means the MCP server is a **consumer** of the existing code,
not a fork. It imports `PlatformService`, `APIVersionRegistry`, and `GatewayConfig` — the
same classes the connection plugin uses today.

```
                    ┌─────────────────────┐
                    │   ansible.platform   │
                    │        SDK          │
                    │                     │
                    │  PlatformService    │
                    │  APIVersionRegistry │
                    │  DynamicClassLoader │
                    │  TransformMixins    │
                    │  GatewayConfig      │
                    └────────┬────────────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
                ▼            ▼            ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Ansible  │  │   MCP    │  │  Future   │
        │ Action   │  │  Server  │  │ Consumers │
        │ Plugins  │  │          │  │           │
        └──────────┘  └──────────┘  └──────────┘
             │              │
             ▼              ▼
         Playbooks      AI Agents
```

---

## Dual-Mode Tools: Execute or Emit

Every MCP tool supports two modes, selectable per invocation:

| Mode | What Happens | When to Use |
|------|-------------|-------------|
| **Execute** | SDK calls the Gateway API directly, returns structured result | Ad-hoc operations, interactive troubleshooting, agent-driven workflows |
| **Emit** | Returns the equivalent `ansible.platform` task YAML | Playbook authoring, code review workflows, auditable change management |

This is the central differentiator. The MCP server does not compete with playbooks — it
makes them easier to write and provides a direct-execution path when a playbook is
unnecessary.

**Execute mode** — the agent creates the user now:

```json
{
  "tool": "ansible_platform_user",
  "arguments": {
    "mode": "execute",
    "operation": "create",
    "username": "jdoe",
    "email": "jdoe@example.com",
    "first_name": "Jane",
    "state": "present"
  }
}
```

Returns:
```json
{
  "changed": true,
  "user": {"id": 591, "username": "jdoe", "email": "jdoe@example.com", "first_name": "Jane"}
}
```

**Emit mode** — the agent produces the playbook task for review:

```json
{
  "tool": "ansible_platform_user",
  "arguments": {
    "mode": "emit",
    "operation": "create",
    "username": "jdoe",
    "email": "jdoe@example.com",
    "first_name": "Jane",
    "state": "present"
  }
}
```

Returns:
```yaml
- name: Create user jdoe
  ansible.platform.user:
    username: jdoe
    email: jdoe@example.com
    first_name: Jane
    state: present
```

The engineer pastes this into a playbook, commits it, and runs it through the normal
CI/CD pipeline. The agent helped author the task — the human controls when and how it
executes.

The mode selection is explicit in every tool call. There is no ambiguity about whether
the agent is making changes or producing artifacts.

---

## Surface Area Compounds

The MCP server does not have its own module inventory. It reads the collection's
`APIVersionRegistry` at startup and generates tools for every discovered resource.

Today, `ansible.platform` covers 22 Gateway resources:

| Domain | Resources |
|--------|-----------|
| Identity | `user`, `organization`, `team` |
| Authentication | `authenticator`, `authenticator_map`, `authenticator_user` |
| Access Control | `role_definition`, `role_user_assignment`, `role_team_assignment` |
| Services | `service`, `service_cluster`, `service_type`, `service_key`, `service_node` |
| Platform Config | `http_port`, `route`, `ui_plugin_route`, `settings`, `feature_flag` |
| Security | `ca_certificate`, `token` |
| Applications | `application` |

Each resource generates tools for `create`, `update`, `delete`, and `find` — 88 MCP tools
from 22 resource definitions.

The roadmap extends this to the full AAP platform:

| Component | Resources | Status |
|-----------|-----------|--------|
| **Gateway** | Users, orgs, teams, auth, RBAC, services, routes | 22 resources today |
| **Controller** | Job templates, inventories, credentials, projects, workflows | Planned |
| **EDA** | Rulebook activations, decision environments, event streams | Planned |

As Controller and EDA resources are added to the `ansible.platform` collection using the
same SDK pattern (Ansible model, API model, transform mixin, action plugin), the MCP server
picks them up automatically. No MCP-specific development required per resource.

One schema definition. One test suite. One release. Both surfaces ship together.

---

## Meeting Engineers Where They Are

The same SDK serves different interaction patterns without forcing engineers to change
how they work:

**Playbook authors** keep writing YAML. Nothing changes. The collection works exactly as
it does today. The MCP server is a separate process that happens to share the same SDK.

**Platform engineers** get a conversational interface to AAP. "Set up a new team called
platform-ops in the Red Hat org with viewer permissions" becomes a tool call, not a
30-line playbook for a one-time operation.

**SREs** troubleshoot live Gateway state interactively. "List all authenticators" or "show
me the service clusters" without opening a terminal, writing a playbook, or hitting the
API with curl.

**CI/CD pipelines** call MCP tools directly for lightweight operations that don't justify
a full playbook — rotating a token, toggling a feature flag, checking whether a service
node exists before deploying to it.

**Internal developer platforms** integrate AAP Gateway as a tool-equipped backend for
self-service portals, chatbots, or developer copilots. The MCP server provides the
structured interface; the platform provides the UX.

---

## What It Takes

The MCP server is a consumer of the existing SDK. It requires no changes to the
`ansible.platform` collection.

| Component | Description | Effort |
|-----------|-------------|--------|
| MCP server skeleton | stdio/SSE transport using the Python `mcp` SDK | ~200 lines |
| Tool schema generator | Parse `DOCUMENTATION` YAML into JSON Schema `inputSchema` | ~150 lines |
| Dual-mode handler | Execute via `PlatformService` or emit Ansible task YAML | ~100 lines |
| Auth configuration | Reuse `GatewayConfig` — URL, credentials, SSL, timeouts | ~50 lines |

Total: approximately 300-500 lines of Python wrapping an SDK that already handles
authentication, session management, retries, idempotency, name-to-ID resolution,
API version detection, and error classification.

The `PlatformService` constructor authenticates and detects the API version at init time.
For an MCP server, initialization is deferred to first tool call (lazy) or tied to server
startup (eager, requires Gateway connectivity). Both approaches work; the choice is
operational.

---

## The Bigger Picture

This positions AAP as the first enterprise automation platform with native AI agent
integration — not through a chatbot wrapper or a prompt-engineering layer, but through
a structured tool interface backed by the same deterministic engine that runs production
playbooks.

The pattern is replicable. Any Ansible collection built with the SDK pattern
(typed dataclasses, self-describing documentation, `execute()` entry point) can generate
an MCP server. `ansible.platform` is the proof of concept; the architecture is the
template.

The MCP ecosystem is early. Infrastructure automation tools are conspicuously absent.
The collections that show up first with well-typed, idempotent, dual-mode tools will
define how agents interact with enterprise infrastructure for the next decade.

The SDK already exists. The tools are already defined. The only question is whether to
add the second front door.
