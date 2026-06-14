#!/usr/bin/python
# coding: utf-8 -*-

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


DOCUMENTATION = """
---
module: role_team_assignment
author: Rohit Thakur (@rohitthakur2590)
short_description: Gives a team permission to a resource or an organization.
description:
    - Use this module to assign team or organization related roles to a team.
    - After creation, the assignment cannot be edited, but can be deleted to remove those permissions.
    - Not all role assignments are valid. See Limitations below.
notes:
  - This module is subject to limitations of the RBAC system in AAP 2.6.
  - Global roles (e.g. Platform Auditor) cannot be assigned to teams.
  - Team roles cannot be assigned to another team (Team Admin to Team is not supported).
  - Organization Member role cannot be assigned to teams.
  - The C(type) field in C(assignment_objects) must match the resource type expected by the
    role definition's C(content_type). For example, a role with C(content_type=awx.project)
    requires C(type=projects). Using C(type=organizations) for such a role will result in an
    error. Use the organization-scoped variant of the role (e.g. "Organization Project Admin")
    when you want to grant access to all resources of a type within an organization.
  - Attempting unsupported role assignments will result in errors.
options:
    assignment_objects:
        description:
            - List of dicts mapping resource names to their types.
            - When using name, each dict must include C(name) and C(type).
            - The C(type) value must match the endpoint corresponding to the role's
              C(content_type). For example, a role with C(content_type=awx.project) requires
              C(type=projects); a role with C(content_type=shared.organization) requires
              C(type=organizations).
        type: list
        elements: dict
        suboptions:
            name:
                description:
                  - The object name (e.g. organization, project, or activation name).
                  - Internally resolved to the object's primary key via a name lookup.
                type: str
                required: False
            type:
                description:
                  - The resource type endpoint for name-based lookup.
                  - Must match the content_type of the role definition.
                  - Examples - C(organizations), C(teams), C(projects), C(inventories),
                    C(credentials), C(job_templates), C(activations), C(event_streams).
                type: str
                required: False
            object_id:
                description:
                - The primary key of the object (team/organization) this assignment applies to.
                - A null value indicates system-wide assignment.
                required: False
                type: int
            object_ansible_id:
                description:
                  - Resource id of the object this role applies to. Alternative to the object_id field.
                required: False
                type: str
    role_definition:
        description:
          - The role definition which defines permissions conveyed by this assignment.
        required: True
        type: str
    team:
        description:
          - The name or id of the team to assign to the object.
        required: False
        type: str
    team_ansible_id:
        description:
          - Resource id of the team who will receive permissions from this assignment. Alternative to I(team) field.
        required: False
        type: str
    state:
      description:
        - Desired state of the resource.
      choices: ["present", "absent", "exists"]
      default: "present"
      type: str
extends_documentation_fragment:
- ansible.platform.auth
"""


EXAMPLES = """
- name: Assign org-level role against multiple organizations (content_type shared.organization)
  ansible.platform.role_team_assignment:
    role_definition: Organization Inventory Admin
    team: "{{ team2.name }}"
    assignment_objects:
      - name: "{{ org1.name }}"
        type: organizations
      - name: "{{ org2.name }}"
        type: organizations
    state: present
  register: result

- name: Assign resource-level role against a specific project (content_type awx.project)
  ansible.platform.role_team_assignment:
    role_definition: Project Admin
    team: "developers"
    assignment_objects:
      - name: "Demo Project"
        type: projects
    state: present

- name: Assign resource-level role against a specific EDA activation (content_type eda.activation)
  ansible.platform.role_team_assignment:
    role_definition: Activation Admin
    team: "eda-operators"
    assignment_objects:
      - name: "prod-alert-activation"
        type: activations
    state: present

- name: Assign role using object_ansible_id (works for any resource type)
  ansible.platform.role_team_assignment:
    role_definition: Organization Inventory Admin
    team: "APAC-BLR"
    assignment_objects:
      - object_ansible_id: "c891b9f7-cc08-4b62-9843-c9ebfda362a8"
    state: present
  register: result

- name: Check role team assignment exists
  ansible.platform.role_team_assignment:
    role_definition: Organization Inventory Admin
    team: "APAC-BLR"
    assignment_objects:
      - object_ansible_id: "c891b9f7-cc08-4b62-9843-c9ebfda362a8"
    state: exists
  register: result

- name: Remove role team assignment
  ansible.platform.role_team_assignment:
    role_definition: Organization Inventory Admin
    team: "APAC-BLR"
    assignment_objects:
      - object_ansible_id: "c891b9f7-cc08-4b62-9843-c9ebfda362a8"
    state: absent
  register: result
...
"""

from ..module_utils.aap_module import AAPModule


# Maps the suffix of a role definition's content_type to the Gateway API endpoint
# used for name-based object lookup.
# Format: "service.ResourceName" → suffix → endpoint
# e.g. "awx.project" → "project" → "projects"
CONTENT_TYPE_ENDPOINT_MAP = {
    # Gateway / shared
    "organization": "organizations",
    "team": "teams",
    # Controller (awx)
    "project": "projects",
    "inventory": "inventories",
    "credential": "credentials",
    "jobtemplate": "job_templates",
    "workflowjobtemplate": "workflow_job_templates",
    "executionenvironment": "execution_environments",
    "instancegroup": "instance_groups",
    "notificationtemplate": "notification_templates",
    # EDA (eda)
    "activation": "activations",
    "edacredential": "eda_credentials",
    "eventstream": "event_streams",
    "decisionenvironment": "decision_environments",
    "credentialinputsource": "credential_input_sources",
    # Hub (galaxy)
    "namespace": "namespaces",
    "collectionremote": "collection_remotes",
    "ansiblerepository": "ansible_repositories",
    "containernamespace": "container_namespaces",
    "containerrepository": "container_repositories",
    "task": "tasks",
}


def _get_expected_endpoint(role_definition):
    """
    Derive the Gateway API lookup endpoint from a role definition's content_type.

    Returns the endpoint string (e.g. 'projects') or None for global roles
    (content_type is null).
    """
    raw = (role_definition.get("content_type") or "").strip()
    if not raw:
        return None
    suffix = raw.split(".")[-1] if "." in raw else raw
    # Fall back to naive pluralisation for unknown types
    return CONTENT_TYPE_ENDPOINT_MAP.get(suffix, "{0}s".format(suffix))


def assign_team_role(
    module,
    state,
    role_team_assignment,
    kwargs,
    role_definition_str,
    team_param,
    team_ansible_id,
    auto_exit=False,
):
    """
    Create/delete/assert a single team role assignment.
    """
    if state == "exists":
        if not role_team_assignment:
            module.fail_json(
                msg=(
                    "Team role assignment does not exist: %s, team: %s"
                    % (role_definition_str, team_param or team_ansible_id)
                )
            )
    elif state == "absent":
        module.delete_if_needed(role_team_assignment, auto_exit=auto_exit)
    elif state == "present":
        module.create_if_needed(
            role_team_assignment,
            kwargs,
            endpoint="role_team_assignments",
            item_type="role_team_assignment",
            auto_exit=auto_exit,
        )
    return


def _validate_selector(entry, module, expected_endpoint=None, role_name=""):
    """
    Enforce exactly one selector per assignment_objects item:
      EITHER (name AND type) OR object_id OR object_ansible_id.

    When name+type is used, validate that the provided type matches the
    endpoint derived from the role definition's content_type so that the
    object lookup targets the correct resource and the Gateway API receives
    a compatible object_id.
    """
    has_name = bool(entry.get("name"))
    has_type = bool(entry.get("type"))
    has_pk = entry.get("object_id") is not None
    has_uuid = bool(entry.get("object_ansible_id"))

    if has_name ^ has_type:
        module.fail_json(
            msg="When using 'name', you must also provide 'type' in each assignment_objects item."
        )

    count = (
        (1 if (has_name and has_type) else 0)
        + (1 if has_pk else 0)
        + (1 if has_uuid else 0)
    )
    if count == 0:
        module.fail_json(
            msg="Each assignment_objects item must include exactly one of: "
            "(name & type) OR object_id OR object_ansible_id."
        )
    if count > 1:
        module.fail_json(
            msg="Each assignment_objects item must not include more than one of: "
            "(name & type), object_id, object_ansible_id."
        )

    if has_name and has_type:
        allowed = sorted(set(CONTENT_TYPE_ENDPOINT_MAP.values()))
        if entry["type"] not in allowed:
            module.fail_json(
                msg=("Unsupported type '{0}'. Valid types: {1}.").format(
                    entry["type"], ", ".join(allowed)
                )
            )

        # Validate that the provided type matches what this role's content_type expects.
        # Mismatches (e.g. type=organizations for a role with content_type=awx.project)
        # cause the Gateway API to reject the assignment with a 400/500 error.
        if expected_endpoint and entry["type"] != expected_endpoint:
            module.fail_json(
                msg=(
                    "Role '{role}' has content_type that requires type '{expected}' for "
                    "name-based lookup, but assignment_objects specifies type '{provided}'. "
                    "To grant access to all {expected} within an organization, use the "
                    "organization-scoped variant of this role (e.g. search for a role "
                    "whose name starts with 'Organization'). "
                    "To target a specific {resource}, use type '{expected}' with the "
                    "resource name."
                ).format(
                    role=role_name,
                    expected=expected_endpoint,
                    provided=entry["type"],
                    resource=expected_endpoint.rstrip("s"),
                )
            )


def main():
    argument_spec = dict(
        role_definition=dict(required=True, type="str"),
        team=dict(required=False, type="str"),
        assignment_objects=dict(
            required=False,
            type="list",
            elements="dict",
            options=dict(
                name=dict(type="str", required=False),
                type=dict(type="str", required=False),
                object_id=dict(required=False, type="int"),
                object_ansible_id=dict(required=False, type="str"),
            ),
        ),
        team_ansible_id=dict(required=False, type="str"),
        state=dict(default="present", choices=["present", "absent", "exists"]),
    )
    module = AAPModule(
        argument_spec=argument_spec,
        mutually_exclusive=[
            ("team", "team_ansible_id"),
        ],
        required_one_of=[
            ("team", "team_ansible_id"),
        ],
    )
    team_param = module.params.get("team")
    role_definition_str = module.params.get("role_definition")
    assignment_objects = module.params.get("assignment_objects")
    team_ansible_id = module.params.get("team_ansible_id")
    state = module.params.get("state")

    role_definition = module.get_one(
        "role_definitions", allow_none=False, name_or_id=role_definition_str
    )
    team = module.get_one("teams", allow_none=True, name_or_id=team_param)

    kwargs = {
        "role_definition": role_definition["id"],
    }
    if team:
        kwargs["team"] = team["id"]
    if team_ansible_id is not None:
        kwargs["team_ansible_id"] = team_ansible_id

    # Derive the expected lookup endpoint from the role's content_type.
    # This is used to validate that assignment_objects[*].type is compatible
    # and to avoid sending a mismatched object_id to the Gateway API.
    expected_endpoint = _get_expected_endpoint(role_definition)
    object_param = assignment_objects
    results = []

    if (
        role_definition_str.lower().startswith("platform")
        and role_definition["id"] == 1
    ):
        # Global platform-auditor path — no object scoping needed
        role_team_assignment = module.get_one(
            "role_team_assignments", **{"data": kwargs}
        )
        assign_team_role(
            module,
            state,
            role_team_assignment,
            kwargs,
            role_definition_str,
            team_param,
            team_ansible_id,
        )

    elif object_param:
        # Process each assignment_objects entry.
        # Gate on object_param alone — not on expected_endpoint — so that
        # entries using object_id / object_ansible_id (which bypass name
        # lookup and need no type validation) are always handled.
        for entity in object_param:
            _validate_selector(
                entity,
                module,
                expected_endpoint=expected_endpoint,
                role_name=role_definition_str,
            )

            if entity["name"] and entity["type"]:
                obj = module.get_one(
                    entity["type"], allow_none=False, name_or_id=entity["name"]
                )
            elif entity["object_id"]:
                obj = {"id": entity["object_id"]}
            else:
                # object_ansible_id path — pass through directly
                kwargs["object_ansible_id"] = entity["object_ansible_id"]
                role_team_assignment = module.get_one(
                    "role_team_assignments", **{"data": kwargs}
                )
                assign_team_role(
                    module,
                    state,
                    role_team_assignment,
                    kwargs,
                    role_definition_str,
                    team_param,
                    team_ansible_id,
                )
                results.append(module.json_output.copy())
                continue

            if obj is None:
                module.fail_json(
                    msg="Unable to find {0} with name '{1}'".format(
                        entity.get("type", "object"), entity.get("name", "")
                    )
                )

            kwargs["object_id"] = obj["id"]
            role_team_assignment = module.get_one(
                "role_team_assignments", **{"data": kwargs}
            )
            assign_team_role(
                module,
                state,
                role_team_assignment,
                kwargs,
                role_definition_str,
                team_param,
                team_ansible_id,
            )
            results.append(module.json_output.copy())

    # Return all results
    module.exit_json(
        changed=any(r.get("changed", False) for r in results), assignments=results
    )


if __name__ == "__main__":
    main()
