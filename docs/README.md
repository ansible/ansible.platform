# Ansible Platform Collection — Documentation

Overview and index for the ansible.platform collection (ANSTRAT-1640). Docs are grouped into subdirectories to make them easier to navigate.

---

## Quick links

| Topic | Directory | Key docs |
|-------|-----------|----------|
| **Architecture** | [architecture/](architecture/) | [ARCHITECTURE.md](architecture/ARCHITECTURE.md), [CONNECTION_MODES.md](architecture/CONNECTION_MODES.md) |
| **Connection plugin** | [connection/](connection/) | Implementation, migration, code flow |
| **Testing** | [testing/](testing/) | Unit/integration, Molecule, mock Gateway, CI |
| **Project / release** | [project/](project/) | ANSTRAT-1640 timeline, breaking changes, scrum updates |
| **API / Gateway** | [api/](api/) | Pagination, networking improvements |
| **Troubleshooting** | [troubleshooting/](troubleshooting/) | Worker crash analysis |
| **Migration** | [migration/](migration/) | Playbook migration |
| **Demo** | [demo/](demo/) | Demo script, Q&A |
| **Reusables** | [reusables/](reusables/) | Shared variables, snippets |

---

## Directory summary

### [architecture/](architecture/)

System design, connection modes, and high-level behavior.

- **[ARCHITECTURE.md](architecture/ARCHITECTURE.md)** — System architecture, components, data flow, direct vs persistent mode
- **[ARCHITECTURE_DIAGRAMS.md](architecture/ARCHITECTURE_DIAGRAMS.md)** — Diagrams (ASCII)
- **[CONNECTION_MODES.md](architecture/CONNECTION_MODES.md)** — Direct vs persistent mode, when to use each, troubleshooting
- **[DESIGN_ACTION_PLUGIN_OPERATIONS.md](architecture/DESIGN_ACTION_PLUGIN_OPERATIONS.md)** — Action plugin operations design
- **[DISPATCHER_PATTERN.md](architecture/DISPATCHER_PATTERN.md)** — Dispatcher pattern
- **[CODE_WALKTHROUGH.md](architecture/CODE_WALKTHROUGH.md)** — Code walkthrough
- **[CURRENT_IMPLEMENTATION_SUMMARY.md](architecture/CURRENT_IMPLEMENTATION_SUMMARY.md)** — Current implementation summary

### [connection/](connection/)

Connection plugin implementation, migration, and code flow.

- **CONNECTION_PLUGIN_*.md** — Migration, implementation, design decisions, final implementation
- **CONNECTION_DISPATCHER_PLACEMENT.md** — Where the dispatcher runs
- **CONNECTION_INITIALIZATION.md** — Initialization flow
- **PERSISTENT_CONNECTION_CODEFLOW.md**, **STANDARD_CONNECTION_CODEFLOW.md** — Code flow for each mode
- **VERIFYING_PERSISTENT_CONNECTION.md** — How to verify persistent mode

### [testing/](testing/)

How to run and extend tests; CI and references.

**Quick run commands (from collection root):**

| Test type | Command |
|-----------|--------|
| **Unit** | `tox -f unit --ansible -p auto --conf tox-ansible.ini` or `ansible-test units --venv -v` or `pytest tests/unit/ -v` (from collection root; see [RUN_UNIT_TESTS.md](testing/RUN_UNIT_TESTS.md) for pytest path). |
| **Integration (Molecule)** | `ANSIBLE_COLLECTIONS_PATH="$(cd ../.. && pwd)" molecule test --all` |

Unit tests live under **`tests/unit/`** (connection plugin, registry, loader). Integration tests use **Molecule** (see `extensions/molecule/` and [MOLECULE_TEST_ALL-HOW-IT-WORKS.md](testing/MOLECULE_TEST_ALL-HOW-IT-WORKS.md)).

- **[RUN_UNIT_TESTS.md](testing/RUN_UNIT_TESTS.md)** — Run unit tests locally (tox-ansible, ansible-test, pytest)
- **[RUN_INTEGRATION_TESTS_LOCALLY.md](testing/RUN_INTEGRATION_TESTS_LOCALLY.md)** — Run integration/Molecule tests locally
- **[TESTING_WITH_MOCK_GATEWAY.md](testing/TESTING_WITH_MOCK_GATEWAY.md)** — Using the mock Gateway server
- **INTEGRATION_TESTS_CI.md** — CI for integration tests
- **JIRA-AAP-57835-TEST-PLAN-TICKETS.md** — Test plan epic ticket content (unit + Molecule)
- **REFERENCE-MERAKI_RM-MOLECULE-AND-MOCK.md** — Reference: meraki_rm for Molecule and mock server
- **MOLECULE_TEST_ALL-HOW-IT-WORKS.md** — What runs when you `molecule test --all` and how to run it in CI
- **SPIKE-MANAGER-LIFECYCLE-IN-MANAGED-ENVIRONMENTS.md** — Spike guide for manager lifecycle in containers/EE

### [project/](project/)

ANSTRAT-1640 project and release notes.

- **[BREAKING_CHANGES_ANSTRAT_1640_PHASE1.md](project/BREAKING_CHANGES_ANSTRAT_1640_PHASE1.md)** — Breaking changes in Phase 1 (adopting new path)
- **ANSTRAT_1640_TIMELINE_TESTATHON.md** — Timeline and testathon
- **SCRUM_UPDATE_ANSTRAT_1640_POST_PROPOSAL.md** — Scrum update after P1 proposal

### [api/](api/)

Gateway API behavior and networking.

- **GATEWAY_API_PAGINATION_FULL_URL.md** — Pagination and full URLs
- **NETWORKING_IMPROVEMENTS.md** — Networking improvements and follow-ups

### [troubleshooting/](troubleshooting/)

Incident and root-cause notes.

- **WORKER_CRASH_FIX.md**, **WORKER_CRASH_ROOT_CAUSE.md** — Worker crash analysis and fix

### [migration/](migration/)

Playbook and usage migration.

- **PLAYBOOK_MIGRATION.md** — Migrating playbooks to the new path

### [demo/](demo/)

Demos and FAQ.

- **DEMO_SCRIPT.md** — Demo script
- **Q_AND_A.md** — Q&A

### [reusables/](reusables/)

Shared content (e.g. variables, snippets).

- **variables.md**

---

## Component locations (in repo)

- **Platform / config:** `plugins/plugin_utils/platform/`
- **Manager / RPC:** `plugins/plugin_utils/manager/`
- **Action plugins:** `plugins/action/`
- **Data models / API layers:** `plugins/plugin_utils/api/`, `plugins/plugin_utils/ansible_models/`
- **Plugin documentation (DOCUMENTATION):** `plugins/plugin_utils/docs/`

---

## Related

- **Collection README:** `../README.md`
- **Changelog:** `../CHANGELOG.rst`
- **Tests:** `../tests/`
- **Molecule scenarios:** `../extensions/molecule/`
