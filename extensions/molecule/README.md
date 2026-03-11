# Molecule integration tests (ANSTRAT-1640)

**Requirement (P1R14):** *Molecule integration testing MUST replace classic tests.*

This directory holds Molecule scenarios for the ansible.platform collection.

**Important:** `extensions/molecule/` must be **tracked in git** for tox integration to run these tests. Tox copies only `git ls-files` into the collection build; if this directory is untracked, no scenarios are found and you get "got empty parameter set for (molecule_scenario)". Run `git add extensions/molecule/` (and commit) so the **users** scenario runs in `tox -e integration-*`. Tests run against an AAP Gateway; connection is configured via environment variables or inventory.

## Layout

- **config.yml** – Base config (optional; scenarios can inherit).
- **inventory.yml** – Shared inventory: `localhost` with `gateway_*` vars from env.
- **users/** – Scenario for `ansible.platform.user`: create, update, idempotency, verify, cleanup.

## Gateway configuration

Defaults are set **statically** in the playbooks (no `lookup('env')`) so the connection plugin never receives unevaluated Jinja. Current defaults: `gateway_hostname: https://34.238.38.25/`, `gateway_username: admin`, `gateway_password: Admin!Password!Gw`, `gateway_validate_certs: false`.

To override for a run, pass extra vars:

```bash
molecule test -s users --all -- -e gateway_hostname=https://other.example/ -e gateway_password=OtherPass
```

The inventory sets `ansible_connection: ansible.platform.http` so the platform user module can call `get_client()` on the connection. Do not use `connection: local` for plays that run `ansible.platform.user`.

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
export GATEWAY_PASSWORD='your-gateway-password'
# Optional: export GATEWAY_HOSTNAME GATEWAY_USERNAME

# Use only this repo's collections (avoids loading cisco.ios, iosxr, etc. from venv/site-packages)
# From collection root .../ansible_collections/ansible/platform, parent of ansible_collections is ../..
export ANSIBLE_COLLECTIONS_PATH="$(cd ../.. && pwd)"

# Run the users scenario
molecule test -s users --all
# Or: molecule converge -s users && molecule verify -s users
```

Ensure the Gateway is running and reachable at `GATEWAY_HOSTNAME` before running tests.

### Why you see “Another version of …” (networking / ansible.platform) warnings

Ansible discovers collections from **several roots**:

1. **ANSIBLE_COLLECTIONS_PATH** (your `../..` = workspace parent)
2. **~/.ansible/collections** (user installs)
3. **Python env’s `ansible_collections`** (e.g. venv `site-packages` if you pip-installed collections)

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
