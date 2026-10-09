#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2020, John Westcott IV <john.westcott.iv@redhat.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/instance_group.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: instance_group
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller instance groups
description:
  - Create, update, or delete instance groups on Ansible Automation Platform Controller.
  - Instance groups can be regular or container groups (with Kubernetes/OpenShift).
  - The C(instances) association endpoint is planned for a follow-up PR.
version_added: "2.8.0"

options:
  name:
    description:
      - Name of the instance group.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  credential:
    description:
      - Credential name or ID to authenticate with Kubernetes or OpenShift.
      - Must be of type "OpenShift or Kubernetes API Bearer Token".
    type: str

  is_container_group:
    description:
      - Signifies that this instance group should act as a container group.
      - If no credential is specified, the underlying Pod's ServiceAccount will be used.
    type: bool

  policy_instance_percentage:
    description:
      - Minimum percentage of all instances that will be automatically assigned to this group.
    type: int

  policy_instance_minimum:
    description:
      - Static minimum number of instances that will be automatically assigned to this group.
    type: int

  max_concurrent_jobs:
    description:
      - Maximum number of concurrent jobs to run on this group.
      - Zero means no limit.
    type: int

  max_forks:
    description:
      - Maximum number of forks to execute on this group.
      - Zero means no limit.
    type: int

  policy_instance_list:
    description:
      - List of exact-match instance hostnames that will be assigned to this group.
    type: list
    elements: str

  pod_spec_override:
    description:
      - A custom Kubernetes or OpenShift Pod specification.
    type: str

seealso:
  - module: ansible.controller.instance_group
  - module: awx.awx.instance_group

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Create a regular instance group
  ansible.platform.instance_group:
    name: "My Instance Group"
    policy_instance_percentage: 50
    state: present

- name: Create a container group
  ansible.platform.instance_group:
    name: "K8s Container Group"
    is_container_group: true
    credential: "My K8s Credential"
    pod_spec_override: |
      apiVersion: v1
      kind: Pod
      spec:
        containers:
          - name: worker
            image: quay.io/ansible/awx-ee:latest
    state: present

- name: Rename an instance group
  ansible.platform.instance_group:
    name: "My Instance Group"
    new_name: "Production Group"

- name: Delete an instance group
  ansible.platform.instance_group:
    name: "Production Group"
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the instance group was created, updated, or deleted.
  returned: always
  type: bool

instance_group:
  description: >
    The instance group resource as it exists after the operation.
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the instance group.
      type: int
    name:
      description: Name of the instance group.
      type: str
    credential:
      description: Credential ID for Kubernetes/OpenShift authentication.
      type: int
    is_container_group:
      description: Whether this is a container group.
      type: bool
    policy_instance_percentage:
      description: Auto-assignment percentage for new instances.
      type: int
    policy_instance_minimum:
      description: Minimum auto-assigned instances.
      type: int
    max_concurrent_jobs:
      description: Maximum concurrent jobs (0 = no limit).
      type: int
    max_forks:
      description: Maximum forks (0 = no limit).
      type: int
    policy_instance_list:
      description: List of exact-match instance hostnames.
      type: list
    pod_spec_override:
      description: Custom Pod specification.
      type: str
...
"""
