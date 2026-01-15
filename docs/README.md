# Ansible Platform Collection - Documentation

## Overview

This directory contains architecture documentation for the Ansible Platform Collection POC implementation, which demonstrates the architecture proposed in [ANSTRAT-1640 SDP](../handbook/The%20Ansible%20Engineering%20Handbook/System%20Design%20Plans/ANSTRAT-1640-persistent-connection-manager-for-ansible-platform-collection.md) and [P1 Proposal](../handbook/The%20Ansible%20Engineering%20Handbook/proposals/ANSTRAT-1640-ANSTRAT-1640-Platform-API-Evolution.md).

## Documentation Files

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete system architecture
   - High-level architecture overview
   - Component responsibilities
   - Data flow and transformations
   - Dual-mode connection support (standard vs experimental)
   - Key design decisions

2. **[ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md)** - Visual architecture diagrams
   - High-level architecture diagrams
   - Component architecture
   - Data flow diagrams
   - Sequence diagrams

## Key Architecture Principles

1. **Dual-Mode Connections**: Support for both standard (direct HTTP) and experimental (persistent manager) modes
2. **API Version Management**: Filesystem-based API version discovery and dynamic class loading
3. **Shared Layers**: Both connection modes use the same layers (version detection, error handling, credentials, CRUD)
4. **Action Plugin Architecture**: Migration from modules to action plugins (new architecture)
5. **Quality Tooling**: Modern Python tooling (ruff, mypy, pydoclint) with automated checks

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
