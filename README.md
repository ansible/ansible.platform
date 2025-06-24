# Ansible Platform Collection

## Changelog for v2.5.20250702

* Ensures that modules in the ansible.platform collection accepts `AAP_*` variable for authentication.
* Adds missing option in the ansible.platform.user module to allow setting the `is_platform_auditor` flag on a user.
* Allows running `ansible.platform` collection modules in check mode.
* Fixes `ansible.platform.user` not adding users to organizations.
* Specify correct `aap_*` parameters in `ansible.platform.token` module examples.
* Fixes an example task in `ansible.platform.token` module.
* Adds a new section in the collection README describing how to authenticate to AAP from the playbook.
* Allows `object_id` field in `role_user_assignment` module to accept a list of items.
* Updated documentation examples for the `ansible.platform.settings` module with tested tasks examples.
* Improve documentation and examples for `ansible.platform.authenticator` and `ansible.platform.authenticator_map` modules.
* Allows role assignments using `object_ansible_id` in the `role_user_assignment` module.
* Improve documentation and examples related to `object_id` and `object_ansible_id` parameters in `role_user_assignment` module.

## Description

This collection contains modules that can be used to automate the creation of resources on an install of Ansible Automation Platform.


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
  - name: ansible.platform.
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

This collection can be used to automate to the creation of resources inside of the Ansible Automation Platform. Things such as users, organizations and teams can be created using this collection. 

Adding services (Controller, Event Driven Automation, Automation) can also be done with this collection. Nodes for those services can also be added. 

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

This collection is supported by RedHat Engineering. Support cases can be opened at: https://access.redhat.com/support/

## Release Notes and Roadmap

Changelogs can be found in the changelogs directory. 


## Related Information

Please refer to Ansible Automation Platform Documentation for further documentation needs: https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.5


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
