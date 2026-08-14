#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/role_team_assignment.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: role_team_assignment
author: Rohit Thakur (@rohitthakur2590)
short_description: Assign a team permission to a resource or organization.
description:
    - Creates or removes a role assignment that grants a team access to a
      specific resource (project, inventory, EDA activation, Hub namespace, etc.)
      or to all resources of a type within an organization.
    - Assignments are immutable after creation — delete and re-create to change them.
notes:
  - Global roles (e.g. Platform Auditor) cannot be assigned to teams.
  - Organization Member role cannot be assigned to teams.
  - The C(type) value in C(assignment_objects) must match the resource type
    implied by the role definition's C(content_type). A mismatch produces
    a descriptive error before any API call is made.
  - EDA projects must use C(type=eda_projects). Using C(type=projects) routes
    to Controller and will fail or resolve the wrong resource.
  - For Controller/EDA resources whose names are not globally unique, set
    C(organization) on each C(assignment_objects) item to scope the name lookup.
options:
    role_definition:
        description:
          - Name or ID of the role definition that defines the permissions granted.
        required: true
        type: str
    team:
        description:
          - Name or numeric ID of the team receiving the role.
          - Mutually exclusive with I(team_ansible_id).
        required: false
        type: str
    team_ansible_id:
        description:
          - Ansible resource ID (UUID) of the team. Alternative to I(team).
        required: false
        type: str
    assignment_objects:
        description:
            - List of objects to assign the role against.
            - Each item must specify exactly one of C(name)+C(type),
              C(object_id), or C(object_ansible_id).
        type: list
        elements: dict
        suboptions:
            name:
                description:
                  - Resource name for name-based lookup. Requires C(type).
                type: str
                required: false
            type:
                description:
                  - Resource type endpoint used for name-based lookup.
                  - Must match the role definition's C(content_type).
                  - "Gateway: C(organizations), C(teams)."
                  - "Controller: C(projects), C(inventories), C(credentials),
                    C(job_templates), C(workflow_job_templates),
                    C(execution_environments), C(instance_groups),
                    C(notification_templates)."
                  - "EDA: C(eda_projects), C(activations), C(event_streams),
                    C(decision_environments), C(eda_credentials)."
                  - "Hub: C(namespaces), C(collection_remotes),
                    C(ansible_repositories), C(container_namespaces)"
                  - Use C(eda_projects) for EDA projects — C(projects) routes
                    to Controller.
                type: str
                required: false
            organization:
                description:
                  - Organization name used to disambiguate name-based lookup.
                  - Supported for Controller types that are org-scoped, EDA
                    resource types, and Gateway C(teams).
                type: str
                required: false
            object_id:
                description:
                  - Numeric primary key of the target object.
                type: int
                required: false
            object_ansible_id:
                description:
                  - Ansible resource UUID of the target object.
                type: str
                required: false
    object_id:
        description:
          - Numeric primary key of a single target object.
          - Use I(assignment_objects) to assign against multiple objects.
        type: int
        required: false
    object_ansible_id:
        description:
          - Ansible resource UUID of a single target object.
        type: str
        required: false
    state:
      description:
        - C(present) creates the assignment if it does not exist (idempotent).
        - C(absent) removes the assignment if it exists (idempotent).
        - C(exists) asserts the assignment is present; fails if not found.
      choices: ["present", "absent", "exists"]
      default: "present"
      type: str
extends_documentation_fragment:
- ansible.platform.auth
"""

EXAMPLES = """
# Assign an org-scoped role to a team across multiple organizations
- name: Assign Organization Inventory Admin to team
  ansible.platform.role_team_assignment:
    role_definition: Organization Inventory Admin
    team: "network-team"
    assignment_objects:
      - name: "org-emea"
        type: organizations
      - name: "org-apac"
        type: organizations
    state: present

# Assign a Controller project role to a team
- name: Assign project admin role to team
  ansible.platform.role_team_assignment:
    role_definition: "project-admin"
    team: "devops-team"
    assignment_objects:
      - name: "Demo Project"
        type: projects
    state: present

# Scope name lookup when the same resource name exists in multiple orgs
- name: Assign job template admin in Preprod only
  ansible.platform.role_team_assignment:
    role_definition: "Job Template Admin"
    team: "Ops Team"
    assignment_objects:
      - name: "mco - preprod"
        type: job_templates
        organization: "Preprod"
    state: present

# Assign an EDA project role to a team (use eda_projects, not projects)
- name: Assign EDA project role to team
  ansible.platform.role_team_assignment:
    role_definition: "eda_admin_project_access"
    team: "eda-team"
    assignment_objects:
      - name: "EDA Project 1"
        type: eda_projects
    state: present

# Assign an EDA activation role to a team
- name: Assign activation admin role to team
  ansible.platform.role_team_assignment:
    role_definition: "Activation Admin"
    team: "eda-operators"
    assignment_objects:
      - name: "prod-alert-activation"
        type: activations
    state: present

# Assign a Controller inventory role to a team
- name: Assign inventory admin role to team
  ansible.platform.role_team_assignment:
    role_definition: "Inventory Admin"
    team: "devops-team"
    assignment_objects:
      - name: "Target Inventory"
        type: inventories
    state: present


# Assign a Controller execution environment role to a team
- name: Assign execution environment admin role to team
  ansible.platform.role_team_assignment:
    role_definition: "ExecutionEnvironment Admin"
    team: "devops-team"
    assignment_objects:
      - name: "Cool New EE"
        type: execution_environments
    state: present

# Assign an EDA event stream role to a team
- name: Assign event stream admin role to team
  ansible.platform.role_team_assignment:
    role_definition: "Event Stream Admin"
    team: "eda-team"
    assignment_objects:
      - name: "Demo Event Stream"
        type: event_streams
    state: present

# Assign a Hub namespace role to a team
- name: Assign namespace owner role to team
  ansible.platform.role_team_assignment:
    role_definition: "galaxy.collection_namespace_owner"
    team: "hub-publishers"
    assignment_objects:
      - name: "my_namespace"
        type: namespaces
    state: present

# Assign using numeric object_id directly (works for any resource type)
- name: Assign role by object_id
  ansible.platform.role_team_assignment:
    role_definition: "eda_admin_project_access"
    team: "eda-team"
    object_id: 13
    state: present

# Assign using Ansible resource UUID
- name: Assign role by object_ansible_id
  ansible.platform.role_team_assignment:
    role_definition: "Activation Admin"
    team: "eda-operators"
    assignment_objects:
      - object_ansible_id: "c891b9f7-cc08-4b62-9843-c9ebfda362a8"
    state: present

# Check assignment exists without modifying it
- name: Assert assignment is present
  ansible.platform.role_team_assignment:
    role_definition: "Organization Inventory Admin"
    team: "network-team"
    assignment_objects:
      - name: "org-emea"
        type: organizations
    state: exists

# Remove an assignment
- name: Remove role team assignment
  ansible.platform.role_team_assignment:
    role_definition: "Organization Inventory Admin"
    team: "network-team"
    assignment_objects:
      - name: "org-emea"
        type: organizations
      - name: "org-apac"
        type: organizations
    state: absent
...
"""

RETURN = """
changed:
  description: Whether any assignment was created or deleted.
  returned: always
  type: bool

role_team_assignment:
  description: >
    The role assignment after the operation. For multi-object assignments
    (C(assignment_objects)) this reflects the first assignment; see C(assignments)
    for the full list. Internal fields (C(created), C(url), C(state)) are excluded.
  returned: when state is present or exists
  type: dict
  contains:
    id:
      description: Numeric database ID of the assignment.
      type: int
    role_definition:
      description: Name of the role definition assigned.
      type: str
    team:
      description: Name of the team receiving the role.
      type: str
    object_id:
      description: Primary key of the target object (if scoped to a specific resource).
      type: int
    object_name:
      description: Name of the target object as supplied in assignment_objects.
      type: str
    object_type:
      description: Type value of the target object as supplied in assignment_objects.
      type: str

assignments:
  description: >
    Full list of assignment results when C(assignment_objects) contains more
    than one entry. Each element has the same structure as C(role_team_assignment).
  returned: when assignment_objects has more than one entry
  type: list
...
"""
