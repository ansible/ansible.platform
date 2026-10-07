# Repository Guidelines

## Project Structure & Module Organization

This repository is the `ansible.platform` collection. User-facing modules live in `plugins/modules/`; corresponding action plugins live in `plugins/action/`. Shared API models, transforms, and service logic are under `plugins/plugin_utils/`, with connection, lookup, and documentation plugins in their respective `plugins/` subdirectories. Unit tests are in `tests/unit/`, live AAP integration tests in `tests/integration/`, and mock Gateway scenarios in `extensions/molecule/`. Use `docs/07-adding-resources.md` when adding a resource. Keep release notes in `changelogs/fragments/`.

## Build, Test, and Development Commands

- `make collection-install` installs the local collection for Ansible commands.
- `python -m pytest tests/unit/ -v` runs unit tests without a live AAP instance.
- `make molecule-test SCENARIO=service_cluster_mock` runs one mock scenario; `make molecule-test-all` runs the suite.
- `make collection-test` runs live integration tests with coverage; set `GATEWAY_PASSWORD` and provide a reachable AAP Gateway first.
- `make check_ruff check_mypy check_pydoclint` runs Python style and type checks. `make check_action_plugin_invariants` checks SDK boundaries.
- `make collection-docs collection-lint` checks Ansible documentation and playbook/YAML linting.

## Coding Style & Naming Conventions

Use Python 3.11-compatible syntax, four-space indentation, and `snake_case` files and functions. Ruff enforces imports and formatting with a 160-character line limit; pydoclint checks Google-style docstrings in action plugins. YAML uses two-space indentation, `---` and `...` document markers, and lowercase `true`/`false`. Name resource files `plugins/modules/<resource>.py`, action plugins `<resource>.py`, unit tests `test_*.py`, and mock scenarios `<resource>_mock`. Put shared auth options in `plugins/doc_fragments/` so `ansible-doc` exposes them.

## Testing Guidelines

Add focused pytest coverage for changed Python behavior and a Molecule scenario for new resource flows. Cover create, update, delete, idempotency, and errors where applicable. Run a live integration target when behavior depends on AAP. No numeric coverage threshold is specified; CI runs unit, lint, sanity, Molecule, and integration checks.

## Commit & Pull Request Guidelines

Recent commits use short, imperative summaries; some include `[AAP-XXXXX]` or a `fix:`/`docs:` prefix. Follow the nearby history and do not create commits unless explicitly requested. PR titles must reference a Jira issue as `[AAP-XXXXX] Short description`. Complete the PR template with purpose, reproducible test steps, and relevant logs or screenshots; add a changelog fragment for user-visible changes. Apply `safe to test` for integration CI. Two approvals are required before merge. Tag the CasC collections team for new modules, auth or return-value changes, and deprecations.
