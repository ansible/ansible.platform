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
  - The C(type) field in C(assignment_objects) must match the role definition's C(content_type).
    Use C(type=awx.project) for a role with C(content_type=awx.project). Gateway resources are
    the exception, use C(type=organizations) or C(type=teams). Mismatches are rejected before
    any API call is made. Use the organization-scoped variant of the role (e.g. "Organization
    Project Admin") to grant access to all resources of a type within an organization.
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
                  - Resource type used for name-based lookup. Use the same value
                    as the role definition's C(content_type) field.
                  - "Gateway: C(organizations), C(teams) (plural endpoint names)."
                  - "Controller: C(awx.project), C(awx.inventory), C(awx.credential),
                    C(awx.jobtemplate), C(awx.workflowjobtemplate),
                    C(awx.executionenvironment), C(awx.instancegroup),
                    C(awx.notificationtemplate)."
                  - "EDA: C(eda.project), C(eda.activation), C(eda.eventstream),
                    C(eda.decisionenvironment), C(eda.edacredential)."
                  - "Hub: C(galaxy.namespace), C(galaxy.collectionremote),
                    C(galaxy.ansiblerepository), C(galaxy.containernamespace)."
                type: str
                required: False
            organization:
                description:
                  - Organization name used to disambiguate named Controller, EDA, and Gateway team resources.
                  - Not supported for Hub resources or Controller execution environments and instance groups.
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
        type: awx.project
    state: present

- name: Assign resource-level role against a specific EDA activation (content_type eda.activation)
  ansible.platform.role_team_assignment:
    role_definition: Activation Admin
    team: "eda-operators"
    assignment_objects:
      - name: "prod-alert-activation"
        type: eda.activation
    state: present

- name: Assign resource-level role against an EDA project (content_type eda.project)
  ansible.platform.role_team_assignment:
    role_definition: EDA Project Admin
    team: "eda-team"
    assignment_objects:
      - name: "EDA Project 1"
        type: eda.project
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
from ..module_utils.resource_type_map import (
    ASSIGNMENT_TYPE_PATH_MAP,
    CONTROLLER_NON_ORG_TYPES,
    GATEWAY_ORG_TYPES,
    get_expected_assignment_type,
    lookup_path_for,
    service_kind,
)


def _get_expected_endpoint(role_definition):
    """Return the user-facing assignment type for a role definition's content_type."""
    raw = (role_definition.get("content_type") or "").strip()
    if not raw:
        return None
    return get_expected_assignment_type(raw)


def _matches_org(item, org_id):
    for key in ("organization_id", "organization"):
        value = item.get(key)
        if isinstance(value, dict):
            value = value.get("id")
        if value is not None and str(value) == str(org_id):
            return True
    return False


def _lookup_exact_named_resource(module, endpoint, name, organization_id=None, query=None):
    """Return exactly one resource whose response name equals *name*."""
    query_params = dict(query or {})
    query_params["name"] = name
    response = module.get_endpoint(endpoint, data=query_params)
    if response["status_code"] != 200:
        module.fail_json(msg="Failed to look up resource '{0}' at {1}: HTTP {2}".format(name, endpoint, response["status_code"]))

    payload = response.get("json", {})
    items = payload.get("results") or payload.get("data") or []
    next_page = payload.get("next")
    while next_page:
        page = module.make_request("GET", next_page)
        page_payload = page.get("json", {})
        items.extend(page_payload.get("results") or page_payload.get("data") or [])
        next_page = page_payload.get("next")

    matches = [item for item in items if item.get("name") == name]
    if organization_id is not None:
        matches = [item for item in matches if _matches_org(item, organization_id)]
    if len(matches) != 1:
        module.fail_json(
            msg="Expected exactly one resource named '{0}'{1} at {2}, got {3}.".format(
                name,
                " in organization '{0}'".format(organization_id) if organization_id is not None else "",
                endpoint,
                len(matches),
            )
        )
    return matches[0]


def _resolve_organization_id(module, organization, service):
    endpoint = {
        "controller": "/api/controller/v2/organizations/",
        "eda": "/api/eda/v1/organizations/",
        "gateway": "organizations",
    }[service]
    return _lookup_exact_named_resource(module, endpoint, organization)["id"]


def _resolve_named_object(module, entry):
    obj_type = entry["type"]
    name = entry["name"]
    organization = entry.get("organization")
    service = service_kind(obj_type)
    path = lookup_path_for(obj_type)

    if organization and service == "hub":
        module.fail_json(msg="organization is not supported for Hub type '{0}'".format(obj_type))
    if organization and service == "controller" and obj_type in CONTROLLER_NON_ORG_TYPES:
        module.fail_json(msg="organization is not supported for Controller type '{0}'".format(obj_type))
    if organization and service == "gateway" and obj_type not in GATEWAY_ORG_TYPES:
        module.fail_json(msg="organization is only supported for Gateway type 'teams' (got '{0}')".format(obj_type))

    if service == "hub":
        return _lookup_hub_object_id(module, obj_type, name)

    org_id = _resolve_organization_id(module, organization, service) if organization else None
    query = {"organization": org_id} if org_id is not None and service in ("controller", "gateway") else None
    return _lookup_exact_named_resource(module, path, name, organization_id=org_id, query=query)


def _lookup_hub_object_id(module, obj_type, name):
    """Look up a Hub (Pulp) resource by name and return a dict with an 'id' key.

    Pulp list endpoints return 'results' (or occasionally 'data') and objects
    carry 'pulp_href' instead of a numeric 'id'. The UUID at the end of
    pulp_href is what the Gateway RBAC API expects as object_id.
    """
    path = lookup_path_for(obj_type)
    item = _lookup_exact_named_resource(module, path, name)
    pulp_href = item.get("pulp_href", "")
    if pulp_href:
        uuid = pulp_href.rstrip("/").rsplit("/", 1)[-1]
        if uuid:
            return {"id": uuid, "pulp_href": pulp_href}

    module.fail_json(
        msg=(
            "Hub resource '{0}' at {1} returned no 'pulp_href' field. "
            "Cannot derive an object_id for role assignment.".format(name, path)
        )
    )


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

    if has_name and (not has_type):
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
        allowed = sorted(
            set(["organizations", "teams"]) | set(ASSIGNMENT_TYPE_PATH_MAP.keys())
        )
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
            resource = expected_endpoint.split(".")[-1] if "." in expected_endpoint else expected_endpoint.rstrip("s")
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
                    resource=resource,
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
                organization=dict(type="str", required=False),
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

    role_definition = (
        module.get_one("role_definitions", allow_none=False, name_or_id=role_definition_str)
        if role_definition_str.isdigit()
        else _lookup_exact_named_resource(module, "role_definitions", role_definition_str)
    )
    team = (
        module.get_one("teams", allow_none=True, name_or_id=team_param)
        if team_param and team_param.isdigit()
        else (_lookup_exact_named_resource(module, "teams", team_param) if team_param else None)
    )

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
            if entity["name"] and entity["type"]:
                expected_endpoint = _get_expected_endpoint(role_definition)
                _validate_selector(
                    entity,
                    module,
                    expected_endpoint=expected_endpoint,
                    role_name=role_definition_str,
                )
                obj = _resolve_named_object(module, entity)
            elif entity["object_id"]:
                _validate_selector(
                    entity,
                    module,
                    expected_endpoint=None,
                    role_name=role_definition_str,
                )
                obj = {"id": entity["object_id"]}
            else:
                # object_ansible_id path — pass through directly
                _validate_selector(
                    entity,
                    module,
                    expected_endpoint=None,
                    role_name=role_definition_str,
                )
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
