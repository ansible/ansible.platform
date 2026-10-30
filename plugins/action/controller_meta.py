#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020, Ansible by Red Hat, Inc
# Copyright: (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for controller_meta.

Returns metadata about the ansible.platform collection without making
any API calls. Reads version from galaxy.yml at the collection root.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
from pathlib import Path

import yaml
from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    _COLLECTION_NAMESPACE = "ansible"
    _COLLECTION_NAME = "platform"

    def run(self, tmp=None, task_vars=None):
        """Return collection metadata."""
        result = super().run(tmp, task_vars)
        result.update(
            {
                "changed": False,
                "namespace": self._COLLECTION_NAMESPACE,
                "name": self._COLLECTION_NAME,
                "prefix": f"{self._COLLECTION_NAMESPACE}.{self._COLLECTION_NAME}",
                "version": self._get_collection_version(),
            }
        )
        return result

    def _get_collection_version(self):
        """Read the collection version from galaxy.yml or MANIFEST.json."""
        collection_root = Path(__file__).resolve().parents[2]
        galaxy_path = collection_root / "galaxy.yml"
        try:
            with open(galaxy_path) as f:
                galaxy_data = yaml.safe_load(f)
            if isinstance(galaxy_data, dict):
                version = galaxy_data.get("version")
                if version is not None:
                    return str(version)
        except (OSError, yaml.YAMLError):
            pass
        manifest_path = collection_root / "MANIFEST.json"
        try:
            with open(manifest_path) as f:
                manifest_data = json.load(f)
            collection_info = manifest_data.get("collection_info") if isinstance(manifest_data, dict) else None
            if isinstance(collection_info, dict):
                version = collection_info.get("version")
                if version is not None:
                    return str(version)
        except (OSError, json.JSONDecodeError):
            pass
        return "unknown"
