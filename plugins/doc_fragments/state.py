# -*- coding: utf-8 -*-

# Copyright: (c) 2024, Martin Slemr <@slemrmartin>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    # Ansible Galaxy documentation fragment
    DOCUMENTATION = r"""
options:
    state:
      description:
        - Desired state of the resource.
        - C(merged) creates or updates resources additively (items not in config are left untouched).
        - C(replaced) replaces matched items entirely (unmatched items are left untouched).
        - C(overridden) enforces exact set equality — items not in config are deleted.
        - C(deleted) removes the specified resources.
        - C(gathered) reads the current state without making changes.
      choices: ["merged", "replaced", "overridden", "deleted", "gathered"]
      default: "merged"
      type: str
"""
