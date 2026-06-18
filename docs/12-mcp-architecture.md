# MCP Server: Design & Architecture

This document describes the design, architecture, and implementation details
of the `ansible-platform-mcp` server — a Model Context Protocol (MCP) server
that exposes every `ansible.platform` resource as an AI-agent tool.

For the business rationale and value proposition, see
[11-mcp-vision.md](11-mcp-vision.md).

---

## Design Principles

1. **Zero per-resource code.** No hand-written tool definitions. Every tool is
   generated at startup from the collection's own `DOCUMENTATION` metadata.
   Adding a module to the collection automatically adds a tool to the MCP server.

2. **SDK reuse, not reimplementation.** The MCP server imports and calls the
   same `PlatformService` that powers the Ansible action plugins. There is no
   second HTTP client, no duplicated transform logic, no separate auth flow.

3. **Dual-mode by default.** Every tool supports `execute` (call the Gateway
   API now) and `emit` (return the equivalent Ansible task YAML). The mode is
   explicit in every invocation — there is no ambiguity about whether the agent
   is making changes or producing artifacts.

4. **Lazy Gateway connection.** The server starts and serves tool listings and
   `emit` requests without any Gateway connection. `PlatformService` is
   initialized on the first `execute` call, so misconfigured credentials never
   prevent tool discovery.

---

## Package Structure

The MCP server ships as two pip packages in the `packages/` directory:

```
packages/
├── sdk/                              # ansible-platform-sdk
│   ├── pyproject.toml
│   └── src/ansible_collections/      # Namespace package
│       └── ansible/platform/
│           └── plugins -> (symlink)  # Points to ../../../../../../plugins
│
└── mcp-server/                       # ansible-platform-mcp
    ├── pyproject.toml
    └── src/ansible_platform_mcp/
        ├── __init__.py               # Package version
        ├── config.py                 # Environment → GatewayConfig
        ├── discovery.py              # AST-based module metadata extraction
        ├── schema.py                 # Ansible argspec → JSON Schema
        ├── executor.py               # PlatformService wrapper (execute mode)
        ├── emitter.py                # Ansible task YAML generator (emit mode)
        └── server.py                 # MCP protocol, tool registry, dispatch
```

**`ansible-platform-sdk`** makes the collection pip-installable by packaging
`plugins/` under the `ansible_collections.ansible.platform` namespace via a
build-time symlink. The namespace `__init__.py` files use `pkgutil.extend_path`
so the SDK coexists with galaxy-installed collections.

**`ansible-platform-mcp`** declares `ansible-platform-sdk` as a dependency.
`pip install ansible-platform-mcp` installs everything needed — SDK, MCP
framework, and the server itself.

---

## Module Lifecycle

### Startup: Discovery → Schema → Registry

```
┌─────────────────┐    ┌──────────────┐    ┌──────────────────┐
│   discovery.py  │───▶│  schema.py   │───▶│    server.py     │
│                 │    │              │    │                  │
│ For each .py in │    │ Convert      │    │ Build MCP Tool   │
│ plugins/modules │    │ Ansible opts │    │ objects, store in │
│                 │    │ to JSON      │    │ tool_registry    │
│ • ast.parse()   │    │ Schema       │    │                  │
│ • Extract DOCS  │    │              │    │ Register         │
│ • Merge frags   │    │ Add synthetic│    │ list_tools and   │
│ • Strip auth    │    │ operation +  │    │ call_tool        │
│                 │    │ mode params  │    │ handlers         │
└─────────────────┘    └──────────────┘    └──────────────────┘
```

**1. Discovery (`discovery.py`)**

Scans `plugins/modules/*.py` and extracts the `DOCUMENTATION` YAML string
from each file using `ast.parse()` — no imports, no side effects.

For each module:
- Parses `DOCUMENTATION` via `yaml.safe_load()`
- Resolves `extends_documentation_fragment` references by loading fragment
  files from `plugins/doc_fragments/` (also via AST)
- Merges fragment options with module options (module wins on conflict)
- Strips server-level auth options (`aap_hostname`, `aap_username`, etc.)
  since those are configured via environment variables, not per-tool
- Returns a `ModuleInfo` dataclass: name, description, options dict, `has_state`

**2. Schema conversion (`schema.py`)**

Converts each module's Ansible options dict into a JSON Schema `inputSchema`
suitable for MCP tool definitions:

| Ansible type | JSON Schema type |
|-------------|-----------------|
| `str`       | `string`        |
| `int`       | `integer`       |
| `float`     | `number`        |
| `bool`      | `boolean`       |
| `list`      | `array`         |
| `dict`      | `object`        |
| `raw`       | `oneOf[string, object]` |

Additional mappings:
- `choices` → `enum`
- `default` → `default`
- `required: true` → added to `required` array
- `elements` → `items` type for arrays
- `suboptions` → nested `properties` for objects and array items
- `aliases` → appended to the `description` string

Two synthetic parameters are injected into every tool schema:

- **`operation`** (required, enum): `create | update | delete | find` for
  stateful resources, `update` only for singletons like `settings`.
  Replaces the Ansible `state` parameter with operation semantics natural
  to agent tooling.

- **`mode`** (optional, enum, default `execute`): `execute | emit`.
  Controls whether the tool calls the Gateway API or returns Ansible YAML.

**3. Tool registry (`server.py`)**

`_build_tool_registry()` calls discovery and schema, then constructs an
`mcp.types.Tool` for each module. The registry is a dict mapping
`ansible_platform_{resource}` → `(Tool, ModuleInfo)`.

The low-level MCP server registers two handlers:

- `list_tools()` → returns all `Tool` objects from the registry
- `call_tool(name, arguments)` → dispatches to executor or emitter

### Runtime: Tool Invocation

```
                        ┌─────────────────────────────┐
                        │        call_tool()           │
                        │                              │
                        │  1. Pop operation & mode     │
                        │  2. Dispatch by mode:        │
                        │                              │
                  ┌─────┴──────┐            ┌──────────┴────┐
                  │   execute  │            │     emit      │
                  │            │            │               │
                  ▼            │            ▼               │
          ┌──────────────┐    │    ┌───────────────┐       │
          │ executor.py  │    │    │  emitter.py   │       │
          │              │    │    │               │       │
          │ Map op →     │    │    │ Map op →      │       │
          │   state      │    │    │   state       │       │
          │              │    │    │               │       │
          │ Auto-lookup  │    │    │ Build task    │       │
          │ for delete/  │    │    │ dict with     │       │
          │ update if no │    │    │ module FQCN   │       │
          │ ID provided  │    │    │               │       │
          │              │    │    │ yaml.dump()   │       │
          │ PlatformSvc  │    │    │               │       │
          │ .execute()   │    │    └───────┬───────┘       │
          └──────┬───────┘    │            │               │
                 │            │            │               │
                 ▼            │            ▼               │
          ┌──────────────┐   │     YAML text content      │
          │ AAP Gateway  │   │                             │
          │ REST API     │   │                             │
          └──────┬───────┘   │                             │
                 │           │                             │
                 ▼           │                             │
          JSON result dict   │                             │
                 │           │                             │
                 └───────────┴─────────────────────────────┘
                                       │
                                       ▼
                              TextContent response
                              back to MCP client
```

---

## Module Details

### `config.py` — Environment to GatewayConfig

`ServerConfig` is a frozen dataclass that reads six environment variables:

| Variable | Purpose | Default |
|----------|---------|---------|
| `AAP_GATEWAY_URL` | Gateway base URL | (required for execute) |
| `AAP_USERNAME` | Basic auth username | `None` |
| `AAP_PASSWORD` | Basic auth password | `None` |
| `AAP_TOKEN` | OAuth / PAT token | `None` |
| `AAP_VALIDATE_CERTS` | TLS verification | `true` |
| `AAP_REQUEST_TIMEOUT` | HTTP timeout (seconds) | `10` |

`to_gateway_config()` converts to the SDK's `GatewayConfig` dataclass —
the same configuration object used by the Ansible connection plugin.

### `discovery.py` — Module Metadata Extraction

Key design decisions:

- **AST, not import**: Module files are parsed with `ast.parse()` to extract
  the `DOCUMENTATION` string constant. This avoids importing modules (which
  would require `ansible-core` and all its dependencies) and has no side
  effects.

- **Fragment merging**: `extends_documentation_fragment` references are
  resolved by loading fragment files from `plugins/doc_fragments/`. Fragments
  use class-level `DOCUMENTATION` constants, so the AST walker handles both
  module-level and class-level assignments.

- **Auth stripping**: Server-level options (`aap_hostname`, `aap_username`,
  etc.) are removed from tool schemas. These are configured once via
  environment variables, not passed per-tool-call.

### `schema.py` — Argspec to JSON Schema

The converter handles the full range of Ansible option specifications:

- Scalar types with choices and defaults
- Lists with typed elements (including `elements: dict` with suboptions)
- Nested dicts with suboptions (recursive)
- `raw` type (accepts string or object)
- Aliases (surfaced in description text)

The `state` option is removed from every schema and replaced with the
`operation` parameter. This bridges Ansible's declarative model (`state:
present/absent/exists`) with the imperative model natural to tool invocation
(`create/update/delete/find`).

### `executor.py` — Gateway Operations

`GatewayExecutor` wraps `PlatformService` with two additions:

1. **Lazy initialization**: `PlatformService` is created on first `execute()`
   call, not at server startup. This means the MCP server starts instantly and
   serves `emit` and `list_tools` requests without Gateway connectivity.

2. **Auto-lookup for delete/update**: The SDK's `_delete_resource()` and
   `_update_resource()` methods require a numeric resource `id`. MCP tool
   callers typically provide a `name` or `username`. The executor automatically
   performs a `find` lookup before delete/update when no `id` is present,
   mirroring what the Ansible action plugin does internally.

Operation mapping:

| MCP operation | SDK operation | Ansible state |
|--------------|--------------|---------------|
| `create`     | `create`     | `present`     |
| `update`     | `update`     | `present`     |
| `delete`     | `delete`     | `absent`      |
| `find`       | `find`       | `exists`      |

All SDK calls are dispatched via `asyncio.to_thread()` since `PlatformService`
uses synchronous `requests.Session` internally. This keeps the async MCP
server responsive during HTTP round-trips.

### `emitter.py` — Ansible Task YAML

Generates valid Ansible task YAML that can be pasted directly into a playbook:

```yaml
- name: Create user jdoe
  ansible.platform.user:
    username: jdoe
    email: jdoe@example.com
    state: present
```

The task name is auto-generated from the operation verb and the first
recognizable lookup field (`name`, `username`, `slug`, or `id`).

### `server.py` — MCP Protocol Layer

Uses the low-level `mcp.server.lowlevel.Server` rather than the `FastMCP`
decorator API. This gives full control over:

- Dynamic tool registration (tools are built from discovery, not decorators)
- Custom schema injection (JSON Schema from the converter, not type hints)
- Error handling (SDK exceptions are caught and returned as structured
  JSON error objects, not MCP protocol errors)

Transport is stdio, compatible with Cursor, Claude Desktop, and any MCP
client that supports the stdio transport.

---

## Data Flow: End-to-End Example

**Agent request**: "Create user jdoe with email jdoe@example.com"

```
1. Client sends tools/call:
   {name: "ansible_platform_user",
    arguments: {operation: "create", mode: "execute",
                username: "jdoe", email: "jdoe@example.com"}}

2. server.py handle_call_tool():
   - Pops operation="create", mode="execute"
   - Delegates to executor.execute("create", "user", {username, email})

3. executor.py:
   - Maps "create" → state="present"
   - Builds ansible_data = {username: "jdoe", email: "jdoe@example.com",
                            state: "present"}
   - Calls PlatformService.execute("create", "user", ansible_data)

4. PlatformService (SDK):
   - Loads AnsibleUser, APIUser_v1, UserTransformMixin via DynamicClassLoader
   - Forward transform: AnsibleUser → APIUser_v1 (field mapping, validation)
   - HTTP POST to /api/gateway/v1/users/ with API-format payload
   - Reverse transform: API response → AnsibleUser dict
   - Returns {username: "jdoe", id: 1000, changed: true, ...}

5. server.py:
   - Serializes result as JSON TextContent
   - Returns to MCP client
```

**Same request in emit mode**:

```
1. Client sends tools/call:
   {name: "ansible_platform_user",
    arguments: {operation: "create", mode: "emit",
                username: "jdoe", email: "jdoe@example.com"}}

2. server.py handle_call_tool():
   - Pops operation="create", mode="emit"
   - Delegates to emitter.emit_task("user", "create", {username, email})

3. emitter.py:
   - Maps "create" → state="present"
   - Builds YAML task with FQCN ansible.platform.user
   - Returns formatted YAML string

4. server.py:
   - Returns YAML as TextContent (no Gateway call made)
```

---

## SDK Package (`ansible-platform-sdk`)

The SDK package makes the `ansible.platform` collection pip-installable under
its full namespace path (`ansible_collections.ansible.platform`).

### How it works

The collection's source lives at the repository root under `plugins/`. The SDK
package creates the Python namespace structure via a symlink at build time:

```
packages/sdk/src/
└── ansible_collections/           __init__.py (pkgutil.extend_path)
    └── ansible/                   __init__.py (pkgutil.extend_path)
        └── platform/              __init__.py
            └── plugins → ../../../../../../plugins  (symlink)
```

- **Editable installs** (`pip install -e`): Python follows the symlink at
  import time, reading directly from the working tree.
- **Wheel builds**: Hatchling resolves the symlink and copies the full
  `plugins/` tree into the wheel.
- **Coexistence**: The `pkgutil.extend_path` calls in the namespace
  `__init__.py` files allow the pip-installed SDK to coexist with a
  galaxy-installed collection. Python finds whichever appears first on
  `sys.path`.

### What's included

Everything under `plugins/`:

| Directory | Contents |
|-----------|----------|
| `plugin_utils/platform/` | `GatewayConfig`, `PlatformService`, HTTP clients, exceptions |
| `plugin_utils/manager/` | `PlatformManager` orchestrating CRUD operations |
| `plugin_utils/api/v*/` | Versioned API models and transform mixins |
| `plugin_utils/ansible_models/` | Typed dataclasses for each resource |
| `modules/` | Module stubs with embedded `DOCUMENTATION` metadata |
| `doc_fragments/` | Shared option definitions (auth, state) |
| `action/` | Action plugins (base execution logic) |
| `connection/` | Persistent connection plugin |

---

## Testing with the Mock Server

The repository includes a mock AAP Gateway server at
`tools/mock_gateway_server.py` that provides in-memory CRUD for all supported
resource types. No real AAP instance is required for development or testing.

```bash
# Start the mock server
python tools/mock_gateway_server.py --port 9080

# In another terminal, run the MCP server against it
AAP_GATEWAY_URL=http://127.0.0.1:9080 \
AAP_USERNAME=admin \
AAP_PASSWORD=password \
AAP_VALIDATE_CERTS=false \
ansible-platform-mcp
```

The mock server accepts any `Authorization` header, stores data in memory
(resets on restart), and supports all endpoints under `/api/gateway/v{1,2}/`.

---

## Scaling the Pattern

The architecture is intentionally generic. Any Ansible collection built with
the platform SDK pattern can generate an MCP server:

1. **Self-describing modules** — `DOCUMENTATION` YAML with typed options
2. **SDK execution interface** — `service.execute(operation, module, params)`
3. **Typed dataclasses** — Ansible models, API models, transform mixins

As Controller and EDA resources are added to the `ansible.platform` collection,
the MCP server picks them up automatically. No per-resource MCP code is needed.

| Component | Resources | MCP Tools |
|-----------|-----------|-----------|
| **Gateway** (today) | 22 resources | 22 tools |
| **Controller** (planned) | Job templates, inventories, credentials, projects, workflows | Auto-generated |
| **EDA** (planned) | Rulebook activations, decision environments, event streams | Auto-generated |

The total implementation: **~800 lines of Python** to expose 22 tools, with
zero lines of per-resource boilerplate.
