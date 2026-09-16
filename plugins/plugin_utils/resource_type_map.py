"""
Resource type mapping for RBAC assignment modules.

Shared by role_team_assignment (and future role_user_assignment) to avoid
duplicating the content_type → API path routing logic.

Gateway resources (organization, team) use plural endpoint names as the
assignment type because they have no service-prefix in their content_type.
All other services (EDA, Controller, Hub) use the content_type value directly
as the assignment type, so users only need to learn one name per resource.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

# Maps role_definition.content_type → assignment_objects[].type value.
# Only Gateway resources need an explicit entry; EDA/AWX/Galaxy map to
# themselves (content_type IS the type value).
_CONTENT_TYPE_TO_ASSIGNMENT_TYPE = {
    "shared.organization": "organizations",
    "shared.team": "teams",
}

# Maps assignment_objects[].type → REST lookup path.
# Gateway entries use bare endpoint names (no leading /api/); all others
# use an absolute path routed through the appropriate service.
ASSIGNMENT_TYPE_PATH_MAP = {
    # Gateway
    "organizations": "organizations",
    "teams": "teams",
    # EDA
    "eda.project": "/api/eda/v1/projects/",
    "eda.activation": "/api/eda/v1/activations/",
    "eda.edacredential": "/api/eda/v1/eda-credentials/",
    "eda.eventstream": "/api/eda/v1/event-streams/",
    "eda.decisionenvironment": "/api/eda/v1/decision-environments/",
    # Controller
    "awx.project": "/api/controller/v2/projects/",
    "awx.inventory": "/api/controller/v2/inventories/",
    "awx.credential": "/api/controller/v2/credentials/",
    "awx.jobtemplate": "/api/controller/v2/job_templates/",
    "awx.workflowjobtemplate": "/api/controller/v2/workflow_job_templates/",
    "awx.executionenvironment": "/api/controller/v2/execution_environments/",
    "awx.instancegroup": "/api/controller/v2/instance_groups/",
    "awx.notificationtemplate": "/api/controller/v2/notification_templates/",
    # Hub
    "galaxy.namespace": "/api/galaxy/v3/namespaces/",
    "galaxy.collectionremote": "/api/galaxy/pulp/api/v3/remotes/",
    "galaxy.ansiblerepository": "/api/galaxy/pulp/api/v3/repositories/",
    "galaxy.containernamespace": "/api/galaxy/pulp/api/v3/pulp_container/namespaces/",
}

# Controller resources that are not scoped to an organization.
CONTROLLER_NON_ORG_TYPES = frozenset(
    {
        "awx.executionenvironment",
        "awx.instancegroup",
    }
)

# Gateway resources that accept an organization scope.
GATEWAY_ORG_TYPES = frozenset({"teams"})


def get_expected_assignment_type(content_type):
    """Return the assignment_objects type value for a role_definition content_type.

    Raises ValueError for unknown content_type values.
    """
    raw = (content_type or "").strip()
    if not raw:
        return None
    if raw in _CONTENT_TYPE_TO_ASSIGNMENT_TYPE:
        return _CONTENT_TYPE_TO_ASSIGNMENT_TYPE[raw]
    if raw in ASSIGNMENT_TYPE_PATH_MAP:
        return raw
    known = sorted(set(list(_CONTENT_TYPE_TO_ASSIGNMENT_TYPE.keys()) + list(ASSIGNMENT_TYPE_PATH_MAP.keys())))
    raise ValueError(
        "Unknown content_type '%s' in role definition. Known types: %s. "
        "If this is a new resource type, add it to resource_type_map.py." % (content_type, ", ".join(known))
    )


def service_kind(obj_type):
    """Return the service name ('eda', 'controller', 'hub', 'gateway') for an assignment type."""
    path = ASSIGNMENT_TYPE_PATH_MAP.get(obj_type, obj_type)
    if isinstance(path, str) and path.startswith("/api/controller/"):
        return "controller"
    if isinstance(path, str) and path.startswith("/api/eda/"):
        return "eda"
    if isinstance(path, str) and path.startswith("/api/galaxy/"):
        return "hub"
    return "gateway"
