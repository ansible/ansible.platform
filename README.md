# Ansible Platform Collection

## Changelog for v2.6.20251106

New module Added ca_certificate got added and a new attribute enable_mtls to the route objects and this enable the collection to work with mtls.

Additional changes:
* Fixes default handling for gateway_request_timeout (avoids passing an int to a boolean filter path).


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

The ansible.platform collection now provides unified, platform-wide Role-Based Access Control (RBAC) management across Ansible Automation Platform components. New or enhanced modules include Organization, Team, User, Role definition, and Role assignment (team/user).

Additional changes:

* You can declare the RBAC state as code and apply it idempotently across services.
* Ansible collections now use a standard global environment variable prefix across components. Automation Controller, Automation Hub, and Event-Driven Ansible all use the new standard ``AAP_`` instead of ``COMPONENT_``. For example, ``aap_hostname``. See the [Automation Hub](https://console.redhat.com/ansible/automation-hub/repo/published/ansible/platform/docs/) documentation for more information.


## Support

This collection is supported by RedHat Engineering. Support cases can be opened at: https://access.redhat.com/support/

## Release Notes and Roadmap

Changelogs can be found in the changelogs directory. 


## Related Information

Please refer to Ansible Automation Platform Documentation for further documentation needs: https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.5


## License Information

GNU General Public License v3.0 or later.

See [LICENSE](https://www.gnu.org/licenses/gpl-3.0.txt) to see the full text.

## Authors

[Sean Sullivan](https://github.com/sean-m-sullivan)
[Martin Slemr](https://github.com/slemrmartin)
[Jake Jackson](https://github.com/thedboubl3j)
[Brennan Paciorek](https://github.com/brennanpaciorek)
[John Westcott](https://github.com/john-westcott-iv)
[Jessica Steurer](https://github.com/jay-steurer)
[Bryan Havenstein](https://github.com/bhavenst)
