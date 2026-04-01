# Ansible Platform Collection (`ansible.platform`)

## Description

The `ansible.platform` collection provides idempotent resource modules for managing
[Red Hat Ansible Automation Platform](https://www.redhat.com/en/technologies/management/ansible)
(AAP) Gateway resources. It targets the AAP Gateway API and enables teams to define
infrastructure-as-code for users, organizations, teams, authentication, services,
routing, and access control — all through standard Ansible playbooks.

The collection follows the **resource module** pattern: each module accepts a desired
`config` list and a `state` (`merged`, `replaced`, `overridden`, `deleted`, or
`gathered`), making it easy to enforce declarative configuration at scale.

## Requirements

| Requirement | Version |
|---|---|
| Python | >= 3.11 |
| ansible-core | >= 2.16.0 |
| Red Hat Ansible Automation Platform | Current release |

No additional Python package dependencies are required beyond what is bundled with
`ansible-core`.

## Installation

Install the collection from Ansible Galaxy:

```bash
ansible-galaxy collection install ansible.platform
```

To pin a specific version:

```bash
ansible-galaxy collection install ansible.platform:==2.7.20260313
```

To upgrade an already-installed collection:

```bash
ansible-galaxy collection install ansible.platform --upgrade
```

You can also declare it in a `requirements.yml` file:

```yaml
collections:
  - name: ansible.platform
```

Then install with:

```bash
ansible-galaxy collection install -r requirements.yml
```

See [Using Ansible collections](https://docs.ansible.com/ansible/devel/user_guide/collections_using.html)
for further details.

## Use Cases

The collection is intended for platform engineers and automation architects who need to
manage AAP Gateway configuration programmatically. Common use cases include:

- **Day-0 provisioning** — bootstrap a fresh AAP installation with organizations,
  teams, users, and authenticators defined in source control.
- **Day-2 operations** — enforce desired state across environments; detect and
  remediate configuration drift with `state: overridden`.
- **Audit and reporting** — use `state: gathered` to read current platform state
  into Ansible variables for downstream processing.
- **CI/CD pipelines** — gate deployments on AAP configuration being exactly as
  expected before running automation.

## Included Content

### Modules

| Module | Description |
|---|---|
| `ansible.platform.applications` | Manage Gateway application (OAuth2 app) resources |
| `ansible.platform.authenticators` | Manage Gateway authenticator resources |
| `ansible.platform.authenticator_maps` | Manage Gateway authenticator map resources |
| `ansible.platform.authenticator_users` | Manage Gateway authenticator user resources |
| `ansible.platform.ca_certificates` | Manage Gateway CA certificate resources |
| `ansible.platform.feature_flags` | Manage Gateway feature flag resources |
| `ansible.platform.http_ports` | Manage Gateway HTTP port resources |
| `ansible.platform.organizations` | Manage Gateway organization resources |
| `ansible.platform.role_definitions` | Manage Gateway role definition resources |
| `ansible.platform.role_team_assignments` | Manage Gateway role-to-team assignment resources |
| `ansible.platform.role_user_assignments` | Manage Gateway role-to-user assignment resources |
| `ansible.platform.routes` | Manage Gateway route resources |
| `ansible.platform.services` | Manage Gateway service resources |
| `ansible.platform.service_clusters` | Manage Gateway service cluster resources |
| `ansible.platform.service_keys` | Manage Gateway service key resources |
| `ansible.platform.service_nodes` | Manage Gateway service node resources |
| `ansible.platform.service_types` | Manage Gateway service type resources |
| `ansible.platform.settings` | Manage Gateway settings resources |
| `ansible.platform.teams` | Manage Gateway team resources |
| `ansible.platform.tokens` | Manage Gateway OAuth2 token resources |
| `ansible.platform.ui_plugin_routes` | Manage Gateway UI plugin route resources |
| `ansible.platform.users` | Manage Gateway user resources |

### Connection Plugins

| Plugin | Description |
|---|---|
| `ansible.platform.http` | Persistent HTTP connection plugin for the AAP Gateway API |

## Authenticating to AAP Gateway

Each module accepts connection parameters directly in the task. You can also export
them as environment variables (prefixed `AAP_`).

```yaml
- name: Manage AAP Gateway resources
  hosts: localhost
  tasks:
    - name: Ensure an organization exists
      ansible.platform.organizations:
        config:
          - name: "my-org"
            description: "Managed by Ansible"
        state: merged
        gateway_hostname: "https://your-aap-hostname"
        gateway_username: "admin"
        gateway_password: "{{ vault_aap_password }}"
        gateway_validate_certs: true
```

### Supported connection parameters

| Parameter | Environment variable | Description |
|---|---|---|
| `gateway_hostname` | `GATEWAY_HOSTNAME` | URL of the AAP Gateway |
| `gateway_username` | `GATEWAY_USERNAME` | Username for authentication |
| `gateway_password` | `GATEWAY_PASSWORD` | Password for authentication |
| `gateway_validate_certs` | `GATEWAY_VALIDATE_CERTS` | Validate TLS certificates (default: `true`) |

## Testing

The collection is tested with:

- **Sanity tests** — PEP8, pylint, validate-modules, yamllint, and shebang checks via
  `ansible-test sanity`.
- **Molecule integration tests** — per-state scenarios (`merged`, `replaced`,
  `overridden`, `gathered`, `deleted`, and `check` mode) for every module, run against
  a mock Gateway server.

To run sanity tests locally, the collection must reside under the correct namespace
path:

```bash
mkdir -p ~/ansible_collections/ansible/platform
ln -s /path/to/this/repo ~/ansible_collections/ansible/platform

cd ~/ansible_collections/ansible/platform
ansible-test sanity --python 3.12
```

To run the full lint suite (matches CI):

```bash
make collection-lint
```

To run Molecule integration tests:

```bash
make collection-test
```

A running Ansible Automation Platform instance is required for integration tests.

## Support

This collection is supported by Red Hat Engineering. Support cases can be opened at
<https://access.redhat.com/support/>.

For bugs and feature requests, open an issue in the
[project repository](https://github.com/ansible/ansible.platform).

## Release Notes and Roadmap

Full release notes are available in [CHANGELOG.rst](https://github.com/ansible/ansible.platform/blob/main/CHANGELOG.rst).

The `changelogs/` directory contains individual release fragments and the compiled
`changelog.yaml`.

## Related Information

- [Red Hat Ansible Automation Platform Documentation](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform)
- [Using Ansible Collections](https://docs.ansible.com/ansible/devel/user_guide/collections_using.html)
- [Ansible Resource Modules](https://docs.ansible.com/ansible/latest/network/user_guide/network_resource_modules.html)
- [AAP Gateway API Reference](https://access.redhat.com/documentation/en-us/red_hat_ansible_automation_platform)

## License Information

[GPL-3.0-or-later](https://github.com/ansible/ansible.platform/blob/main/COPYING)

## Authors

- [Sean Sullivan](https://github.com/sean-m-sullivan)
- [Martin Slemr](https://github.com/slemrmartin)
- [Jake Jackson](https://github.com/thedboubl3j)
- [Brennan Paciorek](https://github.com/brennanpaciorek)
- [John Westcott](https://github.com/john-westcott-iv)
- [Jessica Steurer](https://github.com/jay-steurer)
- [Bryan Havenstein](https://github.com/bhavenst)
