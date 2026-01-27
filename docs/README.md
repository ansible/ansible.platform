# Ansible Platform Collection - Documentation

## Overview

This directory contains architecture documentation for the Ansible Platform Collection POC implementation, which demonstrates the architecture proposed in [ANSTRAT-1640 SDP](../handbook/The%20Ansible%20Engineering%20Handbook/System%20Design%20Plans/ANSTRAT-1640-persistent-connection-manager-for-ansible-platform-collection.md) and [P1 Proposal](../handbook/The%20Ansible%20Engineering%20Handbook/proposals/ANSTRAT-1640-ANSTRAT-1640-Platform-API-Evolution.md).

## Documentation Files

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete system architecture
   - High-level architecture overview
   - Component responsibilities
   - Data flow and transformations
   - Dual-mode connection support (direct vs persistent)
   - Key design decisions

2. **[CONNECTION_MODES.md](CONNECTION_MODES.md)** - Connection modes guide
   - Direct mode (ephemeral managers) - default
   - Persistent mode (long-lived managers) - opt-in
   - Performance comparison
   - When to use each mode
   - Troubleshooting

3. **[CONNECTION_INITIALIZATION.md](CONNECTION_INITIALIZATION.md)** - Connection plugin initialization
   - How Ansible selects connection plugins
   - Connection plugin initialization flow
   - When and how get_client() is called
   - Configuration option reading
   - Debugging tips

4. **[ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md)** - Visual architecture diagrams
   - High-level architecture diagrams
   - Component architecture
   - Data flow diagrams
   - Sequence diagrams

## Key Architecture Principles

1. **Dual-Mode Connections**: Support for both direct (ephemeral managers) and persistent (long-lived managers) modes
2. **Unified Architecture**: Both modes use the same manager process architecture with TransitMixin, API version detection, and Ansible dataclasses
3. **No Worker Crashes**: HTTP requests made in separate manager processes, not in action plugin workers
4. **API Version Management**: Filesystem-based API version discovery and dynamic class loading
5. **Shared Layers**: Both connection modes use the same layers (version detection, error handling, credentials, CRUD)
6. **Action Plugin Architecture**: Migration from modules to action plugins (new architecture)
7. **Quality Tooling**: Modern Python tooling (ruff, mypy, pydoclint) with automated checks

## Component Locations

- **Platform Components**: `plugins/plugin_utils/platform/`
- **Manager Components**: `plugins/plugin_utils/manager/`
- **Action Plugins**: `plugins/action/`
- **Data Models**: `plugins/plugin_utils/ansible_models/` and `plugins/plugin_utils/api/`
- **Documentation**: `plugins/plugin_utils/docs/`

## Related Resources

- **SDP**: [ANSTRAT-1640 SDP](../handbook/The%20Ansible%20Engineering%20Handbook/System%20Design%20Plans/ANSTRAT-1640-persistent-connection-manager-for-ansible-platform-collection.md)
- **P1 Proposal**: [Platform API Evolution Proposal](../handbook/The%20Ansible%20Engineering%20Handbook/proposals/ANSTRAT-1640-ANSTRAT-1640-Platform-API-Evolution.md)
- **Collection README**: `../README.md`
- **Changelog**: `../CHANGELOG.rst`
- **Requirements**: `../requirements/requirements_dev.txt`
- **Tests**: `../tests/`
