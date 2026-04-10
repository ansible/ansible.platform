# Molecule integration tests (ANSTRAT-1640)

**Requirement (P1R14):** *Molecule integration testing MUST replace classic tests.*

This directory holds Molecule scenarios for the ansible.platform collection.

**Important:** For tox integration to run these tests, (1) track in git: `extensions/molecule/` and `tests/integration/test_integration.py`. (2) Our tox integration runs pytest with `--rootdir={toxinidir}` so pytest-ansible's scenario discovery (which runs `git ls-files` from `config.rootpath`) uses the repo; otherwise rootpath can be wrong and no scenarios are found. Tox copies only `git ls-files` into the collection build; if this directory is untracked, no scenarios are found and you get "got empty parameter set for (molecule_scenario)". Run `git add extensions/molecule/` (and commit) so the **users** scenario runs in `tox -e integration-*`. Our `tox-ansible.ini` overrides integration envs to run pytest from the **collection_build** directory (which has `galaxy.yml` and `extensions/molecule`); the installed collection tarball does not include `galaxy.yml`, so discovery would otherwise find no scenarios. Tests run against an AAP Gateway; connection is configured via environment variables or inventory.

## Layout (meraki_rm–inspired)

- **config.yml** – Base config: `shared_state: true`, `prerun: false`, so the **default** scenario runs create first and destroy last when using `molecule test --all`. Other scenarios share the mock server.
- **inventory.yml** – Shared inventory: `localhost` with `gateway_*` vars.
- **default/** – Lifecycle scenario: **create** (start mock Gateway server) and **destroy** (stop it). No converge. With `molecule test --all`, default runs create first, then other scenarios, then default destroy. See [docs/testing/REFERENCE-MERAKI_RM-MOLECULE-AND-MOCK.md](../docs/testing/REFERENCE-MERAKI_RM-MOLECULE-AND-MOCK.md).
- **users/** – Scenario for `ansible.platform.user` against a **real AAP Gateway**: create, update, idempotency, verify, cleanup. Requires a running Gateway (or skip in CI when none).
- **users_mock/** – Scenario for `ansible.platform.user` against the **mock** server (`http://127.0.0.1:8000`). No real AAP required. Use with `molecule test --all` (mock started by default) or start `python3 tools/mock_gateway_server.py` manually.
- **organization_mock/** – Scenario for `ansible.platform.organization` against the **mock** server. Create, idempotency, update, verify, cleanup. No real AAP required.

## Gateway configuration

Defaults are set **statically** in the playbooks (no `lookup('env')`) so the connection plugin never receives unevaluated Jinja. Current defaults: `gateway_hostname: https://34.238.38.25/`, `gateway_username: admin`, `gateway_password: Admin!Password!Gw`, `gateway_validate_certs: false`.

To override for a run, pass extra vars:

```bash
molecule test -s users --all -- -e gateway_hostname=https://other.example/ -e gateway_password=OtherPass
```

The inventory sets `ansible_connection: ansible.platform.http` so the platform user module can call `get_client()` on the connection. Do not use `connection: local` for plays that run `ansible.platform.user`.

## ⚠️ Which directory to run from

**Always run `molecule` from the `extensions/` directory** (one level above this README), never from `extensions/molecule/` or from the collection root.

Molecule resolves scenario names by looking for a `molecule/` subdirectory inside your current working directory:

| Run from | Molecule looks for | Result |
|---|---|---|
| `extensions/` | `extensions/molecule/<scenario>/molecule.yml` | ✅ works |
| `extensions/molecule/` | `extensions/molecule/molecule/<scenario>/molecule.yml` | ❌ `glob failed` |
| `ansible/platform/` (collection root) | `ansible/platform/molecule/<scenario>/molecule.yml` | ❌ `glob failed` |

**Quick fix if you hit `CRITICAL '...molecule.yml' glob failed`:**

```bash
# Go UP one level from extensions/molecule/ to extensions/
cd ..   # now you are in extensions/

molecule test -s role_user_assignment_mock
```

Or use the Makefile target from the collection root (it handles the `cd` for you):

```bash
make molecule-test SCENARIO=role_user_assignment_mock
```

## Install (once)

From the **collection root**, in a venv or your active env (e.g. `ansible312`):

```bash
pip install molecule ansible-core
```

If you use **tox-ansible** for integration, the integration env runs pytest; pytest discovers scenarios via `tests/integration/test_integration.py` (which uses the `molecule_scenario` fixture from pytest-ansible). Each scenario under `extensions/molecule/*/` is run as a test (`molecule test -s <name>`). Ensure molecule is installed in the env (tox-ansible may include it via pytest-ansible):

```bash
tox -e integration-py3.11-2.16 --ansible --conf tox-ansible.ini
# or run all integration envs:
tox -f integration --ansible -p auto --conf tox-ansible.ini
```

## Run locally

From the **collection root** (where `galaxy.yml` and `extensions/` live):

```bash
# Use only this repo's collections
export ANSIBLE_COLLECTIONS_PATH="$(cd ../.. && pwd)"
```

**Option A — All scenarios with mock (no real AAP):**  
Default starts the mock, then runs `users_mock` (and optionally `users` if you have a Gateway). Default destroy stops the mock at the end.

```bash
molecule test --all
```

To see detailed Ansible output (task args, module I/O): `ANSIBLE_VERBOSITY=2 molecule test --all` (use 1–4 for -v through -vvvv). See [docs/testing/MOLECULE_TEST_ALL-HOW-IT-WORKS.md](../../docs/testing/MOLECULE_TEST_ALL-HOW-IT-WORKS.md).

**Option B — Only mock-based tests (user + organization):**  
Start the mock yourself, then run the scenarios:

```bash
python3 tools/mock_gateway_server.py --port 8000 &
molecule test -s users_mock --all
molecule test -s organization_mock --all
# Stop mock when done: pkill -f mock_gateway_server
```

Or let CI run them: the **molecule (mock)** workflow (`.github/workflows/molecule-mock.yml`) runs `users_mock` and `organization_mock` on every PR and push to `devel`; no real Gateway required.

**Option C — Real Gateway (users scenario):**

```bash
export GATEWAY_PASSWORD='your-gateway-password'
# Optional: export GATEWAY_HOSTNAME GATEWAY_USERNAME
molecule test -s users --all
```

Ensure the Gateway is running and reachable before running the **users** scenario.

### Why you see "Another version of …" (networking / ansible.platform) warnings

Ansible discovers collections from **several roots**:

1. **ANSIBLE_COLLECTIONS_PATH** (your `../..` = workspace parent)
2. **~/.ansible/collections** (user installs)
3. **Python env's `ansible_collections`** (e.g. venv `site-packages` if you pip-installed collections)

When the same FQCN (e.g. `cisco.ios`, `ansible.platform`) exists in more than one root, Ansible warns and uses the **first** one in its path order. The warnings do **not** mean Molecule is testing those collections; they only mean duplicate copies were seen. Your scenario only uses **ansible.platform** (user module).

To reduce or avoid the warnings:

- Use a venv that has **only** `ansible-core` and `molecule` (no `pip install cisco.ios` etc.), and/or
- Temporarily move or rename `~/.ansible/collections` so only your workspace tree is used, and/or
- Rely on the fact that the tests still pass: the run only exercises the platform user scenario.

## Run via tox-ansible (CI)

Integration tests are run via **tox-ansible** (same as unit tests):

```bash
tox -f integration --ansible -p auto --conf tox-ansible.ini
tox -e integration-py3.11-2.16 --ansible --conf tox-ansible.ini
```

CI should set `GATEWAY_PASSWORD` (and optionally `GATEWAY_HOSTNAME` / `GATEWAY_USERNAME`) when running the integration job (e.g. from a secret or from a Gateway started in a prior step).

## Adding a scenario

1. Create `extensions/molecule/<scenario_name>/molecule.yml` (driver: delegated, inventory, playbooks).
2. Add `converge.yml`, `verify.yml`, and optionally `cleanup.yml`.
3. Use `module_defaults` for `group/ansible.platform.gateway` so tasks receive `gateway_hostname`, `gateway_username`, `gateway_password`, `gateway_validate_certs`.

Requirements (ANSTRAT-1640): cover create, update, delete, find, idempotency, and error handling where applicable.
