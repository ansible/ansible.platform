# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
name: controller_export
short_description: Filters for converting between Controller export formats.
description:
  - Provides filters to convert legacy awxkit/awx CLI export data into the
    native ansible.platform import format used by the C(controller_import) role.
  - The C(from_awxkit_export) filter transforms awxkit natural-key references
    into plain name strings and flattens related objects so each resource entry
    maps directly to its corresponding C(ansible.platform) module parameters.
version_added: "2.7.0"
"""

RESOURCE_TYPE_MAP = {
    "users": "user",
    "organizations": "organization",
    "teams": "team",
    "credential_types": "controller_credential_type",
    "credentials": "controller_credential",
    "notification_templates": "notification_template",
    "projects": "controller_project",
    "inventory": "inventory",
    "inventory_sources": "inventory_source",
    "job_templates": "job_template",
    "workflow_job_templates": "workflow_job_template",
    "execution_environments": "execution_environment",
    "schedules": "schedule",
}

# Fields in the awxkit export where the value is a natural-key dict
# that should be resolved to just the name string.
FK_NATURAL_KEY_FIELDS = {
    "organization",
    "inventory",
    "project",
    "credential_type",
    "execution_environment",
    "source_project",
    "default_environment",
    "webhook_credential",
    "insights_credential",
    "vault_credential",
    "target_credential",
    "input_source",
    "notification_template",
    "unified_job_template",
    "workflow_job_template",
}

# Related keys that are association lists (lists of natural-key refs → lists of names).
ASSOCIATION_RELATED_KEYS = {
    "credentials",
    "labels",
    "instance_groups",
    "notification_templates_started",
    "notification_templates_success",
    "notification_templates_error",
    "execution_environments",
    "hosts",
    "groups",
}

# Related keys that are full sub-resource dicts (kept as-is, not flattened to names).
SUB_RESOURCE_RELATED_KEYS = {
    "survey_spec",
    "schedules",
    "workflow_nodes",
    "create_approval_template",
}

# Keys to strip from each exported object (internal awxkit metadata).
STRIP_KEYS = {"natural_key", "type"}


def _resolve_natural_key(nk):
    """Extract the display name from an awxkit natural-key dict.

    Natural keys look like:
        {"type": "organization", "name": "Default"}
    or for org-scoped resources:
        {"type": "credential", "name": "My Cred",
         "organization": {"type": "organization", "name": "Default"}}
    """
    if isinstance(nk, dict):
        return nk.get("name") or nk.get("username") or nk.get("hostname")
    return nk


def _convert_resource(resource):
    """Convert a single awxkit-exported resource dict to native format."""
    result = {}

    for key, value in resource.items():
        if key in STRIP_KEYS:
            continue
        if key == "related":
            continue
        if key in FK_NATURAL_KEY_FIELDS and isinstance(value, dict):
            result[key] = _resolve_natural_key(value)
        else:
            result[key] = value

    related = resource.get("related", {})
    for rel_key, rel_value in related.items():
        if rel_key in ASSOCIATION_RELATED_KEYS and isinstance(rel_value, list):
            result[rel_key] = [_resolve_natural_key(item) for item in rel_value]
        elif rel_key in SUB_RESOURCE_RELATED_KEYS:
            result[rel_key] = rel_value
        elif isinstance(rel_value, list):
            result[rel_key] = [_convert_resource(item) if isinstance(item, dict) else item for item in rel_value]
        elif isinstance(rel_value, dict):
            result[rel_key] = rel_value

    return result


def from_awxkit_export(data):
    """Convert a full awxkit export dict to the native ansible.platform import format.

    Args:
        data: Dict from awxkit's export_assets() or ``awx export`` CLI output.

    Returns:
        Dict with same top-level resource type keys, but each resource entry
        uses plain name strings for FK references and has related objects
        flattened into the resource dict.
    """
    if not isinstance(data, dict):
        raise TypeError("from_awxkit_export expects a dict, got %s" % type(data).__name__)

    result = {}
    for resource_type in RESOURCE_TYPE_MAP:
        resources = data.get(resource_type)
        if resources is None:
            continue
        if not isinstance(resources, list):
            continue
        result[resource_type] = [_convert_resource(r) for r in resources]

    return result


def resource_module_map(dummy=None):
    """Return the mapping of export resource type keys to ansible.platform module names."""
    return dict(RESOURCE_TYPE_MAP)


class FilterModule:
    """Controller export format conversion filters."""

    def filters(self):
        return {
            "from_awxkit_export": from_awxkit_export,
            "controller_resource_module_map": resource_module_map,
        }
