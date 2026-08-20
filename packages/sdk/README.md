# ansible-platform-sdk

The engine behind the [ansible.platform](https://github.com/ansible/ansible.platform)
Ansible collection, packaged for direct use by Python applications.

This package makes `ansible_collections.ansible.platform` importable via pip,
so non-Ansible consumers — MCP servers, CLIs, custom integrations — can use the
same SDK that powers the Ansible modules: entity discovery, typed data models,
API versioning, and idempotent CRUD operations against AAP Gateway.

## Installation

```bash
pip install ansible-platform-sdk
```

## What's included

Everything under the collection's `plugins/` directory:

- **`plugin_utils/platform/`** — `GatewayConfig`, `PlatformService`, HTTP clients
- **`plugin_utils/manager/`** — `PlatformManager` orchestrating CRUD operations
- **`plugin_utils/api/`** — Versioned API models and transform mixins
- **`plugin_utils/ansible_models/`** — Typed dataclasses for each resource
- **`modules/`** — Module stubs with embedded `DOCUMENTATION` metadata
- **`doc_fragments/`** — Shared option definitions

## Usage

```python
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService

config = GatewayConfig(
    base_url="https://gateway.example.com",
    username="admin",
    password="secret",
)
service = PlatformService(config)
result = service.execute("create", "user", {
    "username": "jdoe",
    "email": "jdoe@example.com",
    "state": "present",
})
```

## Relationship to the Ansible collection

This package and `ansible-galaxy collection install ansible.platform` install
the same code. Use whichever distribution mechanism fits your workflow:

| Method | Best for |
|--------|----------|
| `pip install ansible-platform-sdk` | Python apps, MCP servers, CI pipelines |
| `ansible-galaxy collection install ansible.platform` | Ansible playbooks, roles, EEs |

Both can coexist. Python resolves whichever appears first on `sys.path`.

## License

GPL-3.0-or-later — same as the `ansible.platform` collection.
