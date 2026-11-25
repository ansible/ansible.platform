# Ansible Platform Collection

The `ansible.platform` collection centralizes resource management for Ansible Automation
Platform Gateway, Automation Controller, and Event-Driven Ansible (EDA).

See the [development module inventory](docs/README.md#collection-scope-and-module-inventory)
and [unreleased changes](CHANGELOG.rst#unreleased) for work since the documented releases.

## Changelog for v2.7.20260313

* Added OIDC User Identity support for Ansible Automation Platform Gateway
* New modules: feature_flag, ca_certificates, role_team_assignment, role_definition
* Add request_timeout_seconds and idle_timeout_seconds to route modules
* Add enable_mtls attribute to route module for mutual TLS support
* Add associated_authenticators parameter to users module
* Add Gateway UI plugin Route Collection Module
* Enhanced organization association logic and auditor user support
* Multiple bug fixes for role assignment, object deletion, and URL handling
* Deprecated authenticator_uid and authenticators fields

## Upgrading to AAP 2.7?

Ensure you are on `ansible.platform >= 2.7.x` before upgrading. Connection variables have changed — replace `controller_host` with `aap_hostname` pointing to your gateway URL.

See the [AAP 2.7 documentation](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.7) for the full upgrade guide.

### HTTP retries when migrating from AWX

`ansible.platform` accepts AWX's `max_retries` and `retry_backoff_factor` as
aliases for `aap_max_retries` and `aap_retry_backoff_factor`. Set them in module
arguments, lookup keyword arguments, inventory, or the `AAP_MAX_RETRIES` and
`AAP_RETRY_BACKOFF_FACTOR` environment variables. Explicit arguments take
precedence over inventory, followed by the environment.

`aap_max_retries: 2` allows up to three attempts on an eligible transient
failure, including the initial request. Use `0` for one attempt. Job launches
and resource-creating POSTs are protected against transient retries. When
either setting is supplied, the configured policy applies to eligible requests
in both manager modes and the in-process HTTP fallback.

If the count is unset, the manager allows up to three attempts. The in-process
HTTP fallback makes one attempt when both settings are unset. The backoff
factor defaults to `2` and must be at least `1`. Platform starts the delay at
one second before jitter, raises the factor to the retry index starting at
zero, caps the result at 60 seconds, and applies up to 10% jitter. AWX uses a
wider jitter range and has no explicit delay cap.

## Description

This collection provides Gateway, Controller, and EDA modules under the
`ansible.platform` namespace. It includes platform identity and service configuration,
Controller automation resources and job operations, and EDA resources and rulebook
activations. Each module targets the service that owns its resource.

## Requirements

This collection supports python versions >=3.11 and requires an ansible-core version of >=2.16.0.

It also requires an existing install of Ansible Automation Platform as a target.

## Installation

Before using this collection, you need to install it with the Ansible Galaxy command-line tool:

```
ansible-galaxy collection install ansible.platform
```

You can also include it in a requirements.yml file and install it with ansible-galaxy collection install -r requirements.yml, using the format:

```yaml
collections:
  - name: ansible.platform
```

Note that if you install any collections from Ansible Galaxy, they will not be upgraded automatically when you upgrade the Ansible package.
To upgrade the collection to the latest available version, run the following command:

```
ansible-galaxy collection install ansible.platform --upgrade
```

You can also install a specific version of the collection, for example, if you need to downgrade when something is broken in the latest version (please report an issue in this repository). Use the following syntax to install version 2.5.0:

```
ansible-galaxy collection install ansible.platform:==2.5.0
```

See [using Ansible collections](https://docs.ansible.com/ansible/devel/user_guide/collections_using.html) for more details.

## Use Cases

- **Gateway:** Manage users, organizations, teams, authentication, access control,
  services, service nodes, and Gateway settings. Registering a service or node is
  Gateway configuration.
- **Controller:** Manage inventories, hosts, groups, projects, credentials, execution
  environments, job templates, workflows, schedules, notifications, and Controller
  settings. Launch, cancel, and wait for automation jobs.
- **EDA:** Manage projects, credentials, credential types and input sources, Controller
  tokens, decision environments, event streams, and rulebook activations.

Service ownership remains distinct within the collection. For example,
`ansible.platform.settings` manages Gateway settings, while
`ansible.platform.controller_settings` manages Controller settings. Similarly,
`ansible.platform.controller_project` and `ansible.platform.eda_project` manage
projects in their respective services. See each module's documentation for its
supported inputs and operations.

## Authenticating to AAP in a playbook

Connecting to AAP requires specifying authentication variables (the ones prefixed by `aap_` here) in the task. Alternatively, `AAP_` environment variables can also be set. For a complete list of authentication variables that can be used, please refer to the module specific documentations.

```yaml
- name: Manage AAP
  hosts: localhost
  tasks:
    - name: Example for auth
      ansible.platform.<module-name>:
        your-module-parameters: parameter-values
        aap_hostname: your-hostname
        aap_username: your-username
        aap_password: your-password
```

## Testing

This collection is tested using integration tests which can be called via `ansible-test integration`. If you wish to run the tests manually, we recommend using the parent Makefile via `make collection-test`. It will require a running version of Ansible Automation Platform.

The collection is tested against current version of Ansible Automation Platform.

## Support

This collection is supported by Red Hat Engineering.

- Open a support case at [Red Hat Customer Portal](https://access.redhat.com/support/)
- Report collection bugs or request features using the **Create issue** button on the [Automation Hub collection page](https://console.redhat.com/ansible/automation-hub/repo/published/ansible/platform)
- For community discussion, see the [Ansible Forum](https://forum.ansible.com)

## Release Notes and Roadmap

Changelogs can be found in the [changelogs directory](https://github.com/ansible/ansible.platform/tree/devel/changelogs).

## Related Information

- [Ansible Automation Platform Documentation](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform)
- [Using Ansible Collections](https://docs.ansible.com/ansible/devel/user_guide/collections_using.html)
- [Ansible Certified Collections README Template](https://access.redhat.com/articles/7068606)

## License Information

[GPLv3](https://github.com/ansible/ansible.platform/blob/devel/COPYING)

## Authors

[Sean Sullivan](https://github.com/sean-m-sullivan)
[Martin Slemr](https://github.com/slemrmartin)
[Jake Jackson](https://github.com/thedboubl3j)
[Brennan Paciorek](https://github.com/brennanpaciorek)
[John Westcott](https://github.com/john-westcott-iv)
[Jessica Steurer](https://github.com/jay-steurer)
[Bryan Havenstein](https://github.com/bhavenst)
