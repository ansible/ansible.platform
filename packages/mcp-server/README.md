# ansible-platform-mcp

MCP server that exposes every [ansible.platform](https://github.com/ansible/ansible.platform)
collection resource as an AI-agent tool — with the same schema, validation, and
idempotent behavior as the Ansible modules.

## Installation

From PyPI (when published):

```bash
pip install ansible-platform-mcp
```

This pulls in `ansible-platform-sdk` automatically — the same SDK that powers
the Ansible modules, packaged for direct use by Python applications.

From source (development):

```bash
git clone https://github.com/ansible/ansible.platform.git
cd ansible.platform
pip install -e packages/sdk -e packages/mcp-server
```

## Configuration

Set environment variables for Gateway connectivity:

```bash
export AAP_GATEWAY_URL=https://gateway.example.com
export AAP_USERNAME=admin
export AAP_PASSWORD=secret
# or
export AAP_TOKEN=your-token-here

# Optional
export AAP_VALIDATE_CERTS=true    # default: true
export AAP_REQUEST_TIMEOUT=10     # default: 10 seconds
```

Gateway credentials are only required for `execute` mode.  The `emit` mode
(Ansible task YAML generation) works without a Gateway connection.

## Usage

### stdio (default transport)

```bash
ansible-platform-mcp
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "ansible-platform": {
      "command": "ansible-platform-mcp",
      "env": {
        "AAP_GATEWAY_URL": "https://gateway.example.com",
        "AAP_USERNAME": "admin",
        "AAP_PASSWORD": "secret"
      }
    }
  }
}
```

### Claude Desktop

Add to Claude Desktop MCP settings:

```json
{
  "mcpServers": {
    "ansible-platform": {
      "command": "ansible-platform-mcp",
      "env": {
        "AAP_GATEWAY_URL": "https://gateway.example.com",
        "AAP_USERNAME": "admin",
        "AAP_PASSWORD": "secret"
      }
    }
  }
}
```

## Tools

Each `ansible.platform` module becomes an MCP tool named
`ansible_platform_{resource}` (e.g. `ansible_platform_user`,
`ansible_platform_organization`).

Every tool accepts:

- **`operation`** (required): `create`, `update`, `delete`, or `find`
- **`mode`** (optional, default `execute`): `execute` or `emit`
- Resource-specific parameters matching the module's argument spec

### Execute mode

Calls the AAP Gateway API directly and returns the structured result:

```json
{
  "tool": "ansible_platform_user",
  "arguments": {
    "operation": "create",
    "mode": "execute",
    "username": "jdoe",
    "email": "jdoe@example.com"
  }
}
```

### Emit mode

Returns the equivalent Ansible task YAML for use in a playbook:

```json
{
  "tool": "ansible_platform_user",
  "arguments": {
    "operation": "create",
    "mode": "emit",
    "username": "jdoe",
    "email": "jdoe@example.com"
  }
}
```

Output:

```yaml
- name: Create user jdoe
  ansible.platform.user:
    username: jdoe
    email: jdoe@example.com
    state: present
```

## Architecture

The MCP server reuses the `ansible.platform` SDK directly — no code
duplication, no REST client reimplementation. As the collection gains modules,
the MCP server gains tools automatically.

```
┌──────────────┐     ┌──────────────────────┐     ┌─────────────┐
│  AI Agent    │────▶│  ansible-platform-mcp│────▶│ AAP Gateway │
│  (Cursor,    │ MCP │                      │ SDK │             │
│   Claude,    │◀────│  discover / schema / │◀────│             │
│   etc.)      │     │  execute / emit      │     │             │
└──────────────┘     └──────────────────────┘     └─────────────┘
```

See [docs/12-mcp-architecture.md](../../docs/12-mcp-architecture.md) for the
detailed design and architecture documentation.

## License

GPL-3.0-or-later — same as the `ansible.platform` collection.
