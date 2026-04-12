# Contributing to ansible.platform

Thank you for contributing to `ansible.platform`. This guide covers everything you need to get started.

---

## Development Setup

```bash
# Clone the repository
git clone https://github.com/ansible/ansible.platform.git
cd ansible.platform

# Install development dependencies
pip install -r requirements.txt --break-system-packages

# Sync the installed copy from the source tree (required before running tests)
make sync-installed

# Run unit tests
PYTHONPATH=collections python -m pytest tests/unit/ -v

# Run molecule mock scenarios
cd extensions && molecule test -s organization_mock
```

---

## Adding a New Resource

The collection uses a code generator to scaffold new resources from the OpenAPI spec. See [docs/07-adding-resources.md](docs/07-adding-resources.md) for the complete walkthrough.

Quick start:

```bash
# Dry-run to preview generated files
python tools/generate_resource.py \
    --tag <openapi-tag> \
    --spec ../aap-openapi-specs/2.6/gateway.json \
    --dry-run

# Generate for real
python tools/generate_resource.py \
    --tag <openapi-tag> \
    --spec ../aap-openapi-specs/2.6/gateway.json
```

Every new resource requires:
- Generated files reviewed and transform mixin completed
- Molecule mock scenario added to `extensions/molecule/<resource>_mock/`
- Molecule scenario registered in `.github/workflows/molecule-mock.yml`
- `ansible-doc ansible.platform.<resource>` passes without errors

---

## Testing

### Unit tests

```bash
# Sync installed copy first (important — tests run against collections/)
make sync-installed

PYTHONPATH=collections python -m pytest tests/unit/ -v
```

### Molecule mock tests

```bash
cd extensions

# Single scenario
molecule test -s organization_mock

# All scenarios
molecule test --all
```

### Linting

```bash
# Python style
ruff check plugins/ tests/

# Type checking
mypy plugins/

# Docstring validation
pydoclint plugins/
```

---

## PR Guidelines

See [GOVERNANCE.md](GOVERNANCE.md) for full approval requirements. In brief:

- **Bug fixes and docs:** 1 steward team approver, CI must pass
- **New resources:** 1 approver + new molecule scenario required
- **Breaking changes or API-version-specific changes:** 2 approvers + PDT review

Add the `needs-pdt-review` label if your change touches argspec options, state machine behavior, or AAP API version dependencies.

---

## CaC Engagement

`ansible.platform` is a foundational dependency for CaC (Content as Code) validated content in the `infra.*` namespace.

**If you are a CaC content author** writing `infra.*` roles or playbooks, see [docs/11-cac-operator-guide.md](docs/11-cac-operator-guide.md) for how to consume this collection.

**If you find a compatibility issue** between `ansible.platform` and an `infra.*` collection, please open a GitHub issue with the label `infra-compat` and tag `@sean-m-sullivan` or `@djdanielsson`.

**Slack:** Join `#wg-ansible-platform-collection` on Red Hat Ansible Community Slack for real-time discussion, integration questions, and release coordination.

**Before each minor release** the CaC liaison reviews `docs/11-cac-operator-guide.md` for accuracy. If you are a CaC maintainer and notice a documentation gap, open a PR directly — doc-only PRs are welcome and require only 1 approver.

---

## Known API Limitations

See [docs/known-api-issues.md](docs/known-api-issues.md) for documented AAP API limitations that affect this collection and their current workarounds.

---

## Questions?

- GitHub Issues: `ansible/ansible.platform`
- Slack: `#wg-ansible-platform-collection`
- Governance and escalation: see [GOVERNANCE.md](GOVERNANCE.md)
