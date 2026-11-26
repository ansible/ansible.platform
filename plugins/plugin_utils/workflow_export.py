"""Read and convert Controller workflow graphs to portable module inputs."""

from .platform.exceptions import APIError

_CONTROLLER_PATH = "api/controller/v2/"
_NODE_TARGET_COLLECTIONS = {
    "inventory_source": "inventory_sources",
    "job_template": "job_templates",
    "project": "projects",
    "system_job_template": "system_job_templates",
    "workflow_approval": "workflow_approval_templates",
}
_EDGE_FIELDS = ("success_nodes", "failure_nodes", "always_nodes")
_PROMPT_REFERENCES = {"inventory": "inventories", "execution_environment": "execution_environments"}
_EXECUTION_ASSOCIATION_FLAGS = {"credentials": "ask_credential_on_launch", "instance_groups": "ask_instance_groups_on_launch"}
_PROMPT_FIELDS = (
    "extra_data",
    "scm_branch",
    "job_type",
    "job_tags",
    "skip_tags",
    "limit",
    "diff_mode",
    "verbosity",
    "forks",
    "job_slice_count",
    "timeout",
    "all_parents_must_converge",
)


def read_workflow_dependency(manager, endpoint, **kwargs):
    """Return a visible dependency or None when Controller denies or hides it."""
    try:
        return manager.search_api(endpoint=endpoint, **kwargs)
    except APIError as exc:
        if exc.status_code not in (403, 404):
            raise
        return None


def workflow_organization_name(resource):
    """Return the exposed organization name only when its ID matches."""
    scope = resource.get("summary_fields", {}).get("organization") or {}
    if resource.get("organization") is not None and scope.get("id") == resource["organization"]:
        return scope.get("name")
    return None


def _read_named_resource(manager, collection, resource_id):
    """Read a Controller resource by ID and verify the returned identity."""
    if type(resource_id) is not int:
        raise ValueError(f"Invalid ID for workflow {collection} reference")
    resource = read_workflow_dependency(manager, f"{_CONTROLLER_PATH}{collection}/{resource_id}/")
    if resource is None:
        return None
    if resource.get("id") != resource_id or not resource.get("name"):
        raise ValueError(f"Invalid {collection} response while exporting workflow nodes")
    return resource


def _scoped_reference(resource):
    """Make a portable reference from a resource and its saved organization."""
    if "organization" not in resource:
        raise ValueError("Missing organization field in workflow dependency response")
    organization_name = workflow_organization_name(resource)
    if resource["organization"] is not None and not organization_name:
        return None
    return {"name": resource["name"], "organization": {"name": organization_name} if organization_name else None}


def _read_node_target(manager, node):
    """Read a supported node target through the caller's existing access."""
    template_id = node.get("unified_job_template")
    target_path = node.get("related", {}).get("unified_job_template", "")
    if type(template_id) is int:
        for target_type, collection in _NODE_TARGET_COLLECTIONS.items():
            if target_path.endswith(f"/{collection}/{template_id}/"):
                return target_type, _read_named_resource(manager, collection, template_id)
    return None, None


def _node_target_reference(manager, target_type, target):
    """Convert a readable node target to the workflow module's input format."""
    if target is None:
        return None
    if target_type == "system_job_template":
        return {"type": target_type, "name": target["name"]}
    if target_type == "inventory_source":
        inventory_id = target.get("inventory")
        if inventory_id is None:
            return None
        inventory = _read_named_resource(manager, "inventories", inventory_id)
        reference = _scoped_reference(inventory) if inventory is not None else None
        if reference is None:
            return None
        return {"type": target_type, "name": target["name"], "inventory": reference}
    if target_type == "workflow_approval":
        timeout = target.get("timeout")
        description = target.get("description")
        if type(timeout) is not int or timeout < 0 or not isinstance(description, str):
            raise ValueError("Invalid approval template response while exporting workflow nodes")
        return {"type": target_type, "name": target["name"], "description": description, "timeout": timeout}
    reference = _scoped_reference(target)
    if reference is None:
        return None
    if reference["organization"] is None:
        reference.pop("organization")
    return {**reference, "type": target_type}


def _caller_is_superuser(manager):
    """Check whether Controller's relationship lists can be treated as unfiltered."""
    response = read_workflow_dependency(manager, f"{_CONTROLLER_PATH}me/")
    if response is None:
        return False
    users = response.get("results")
    if not isinstance(users, list) or len(users) != 1 or not isinstance(users[0], dict) or not isinstance(users[0].get("is_superuser"), bool):
        raise ValueError("Invalid Controller identity response while exporting workflow nodes")
    return users[0]["is_superuser"]


def export_workflow_nodes(manager, workflow_id, max_objects):
    """Return visible node declarations and reasons that prevent a full restore."""
    endpoint = f"{_CONTROLLER_PATH}workflow_job_templates/{workflow_id}/workflow_nodes/"
    response = read_workflow_dependency(manager, endpoint, return_all=True, max_objects=max_objects)
    if response is None:
        return [], ["workflow nodes could not be read"]

    nodes = response.get("results")
    if not isinstance(nodes, list):
        raise ValueError("Invalid workflow node list response")
    identifiers = {}
    for node in nodes:
        if not isinstance(node, dict) or type(node.get("id")) is not int or not isinstance(node.get("identifier"), str) or not node["identifier"]:
            raise ValueError("Invalid workflow node ID or identifier")
        identifiers[node["id"]] = node["identifier"]
    if len(identifiers) != len(nodes) or len(set(identifiers.values())) != len(nodes):
        raise ValueError("Duplicate workflow node ID or identifier")

    exported = []
    reasons = []
    caller_is_superuser = None
    for node in nodes:
        identifier = node["identifier"]
        item = {field: node[field] for field in _PROMPT_FIELDS if node.get(field) is not None}
        item["identifier"] = identifier
        target_type, template = _read_node_target(manager, node)
        reference = _node_target_reference(manager, target_type, template)
        if reference is None:
            reasons.append(f"node {identifier!r} has an unresolved or unsupported template target")
        else:
            item["unified_job_template"] = reference

        related = {}
        for field in _EDGE_FIELDS:
            edges = node.get(field)
            if not isinstance(edges, list) or any(type(target) is not int for target in edges):
                raise ValueError(f"Invalid {field} list for workflow node {identifier!r}")
            if any(target not in identifiers for target in edges):
                reasons.append(f"node {identifier!r} has unresolved {field}")
            related[field] = [{"identifier": identifiers[target]} for target in edges if target in identifiers]

        for field, collection in _PROMPT_REFERENCES.items():
            resource_id = node.get(field)
            if resource_id is None:
                continue
            resource = _read_named_resource(manager, collection, resource_id)
            prompt_reference = _scoped_reference(resource) if resource is not None else None
            if prompt_reference is None:
                reasons.append(f"node {identifier!r} has an unresolved {field} prompt")
            else:
                item[field] = prompt_reference
        for field in ("credentials", "labels", "instance_groups"):
            prompt_flag = _EXECUTION_ASSOCIATION_FLAGS.get(field)
            execution_prompt_enabled = (
                prompt_flag is not None and target_type == "job_template" and template is not None and template.get(prompt_flag) is not False
            )
            if execution_prompt_enabled:
                if caller_is_superuser is None:
                    caller_is_superuser = _caller_is_superuser(manager)
                if not caller_is_superuser:
                    reasons.append(f"node {identifier!r} has a {field} prompt whose associations cannot be verified")
                    continue
            endpoint = f"{_CONTROLLER_PATH}workflow_job_template_nodes/{node['id']}/{field}/"
            association = read_workflow_dependency(manager, endpoint, return_all=True, max_objects=max_objects)
            if association is None:
                reasons.append(f"node {identifier!r} has inaccessible {field}")
            elif not isinstance(association.get("results"), list):
                raise ValueError(f"Invalid {field} list for workflow node {identifier!r}")
            elif association["results"]:
                reasons.append(f"node {identifier!r} has unresolved {field}")
            elif prompt_flag is None or execution_prompt_enabled:
                related[field] = []
        item["related"] = related
        exported.append(item)

    return exported, reasons
