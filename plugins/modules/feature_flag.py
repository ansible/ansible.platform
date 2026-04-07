# coding: utf-8 -*-

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: feature_flag
author: Fabricio Aguiar (@fao89)
short_description: Configure feature flags in Automation Platform Gateway
description:
    - Manage feature flags in the Automation Platform Gateway.
    - Allows viewing and updating runtime feature flags.
    - Install-time feature flags cannot be modified at runtime.
options:
    name:
      description:
        - The name of the feature flag to manage.
        - Must follow the format FEATURE_<flag-name>_ENABLED.
      required: True
      type: str
    value:
      description:
        - The value to set for the feature flag.
        - For boolean conditions, use 'True' or 'False'.
        - Only applicable when state is 'present' or 'enforced'.
        - Required when modifying feature flags.
      type: str
    state:
      description:
        - The desired state of the feature flag.
        - Use 'present' to ensure the feature flag exists with the specified value.
        - Use 'exists' to check if the feature flag exists without modifying it.
        - Use 'absent' to remove the feature flag (not typically supported for system flags).
        - Use 'enforced' to ensure the feature flag value matches exactly.
      choices: ["present", "absent", "exists", "enforced"]
      default: "exists"
      type: str

extends_documentation_fragment:
- ansible.platform.auth
"""

EXAMPLES = """
- name: Check if a feature flag exists
  ansible.platform.feature_flag:
    name: FEATURE_EXAMPLE_ENABLED
    state: exists

- name: Enable a runtime feature flag
  ansible.platform.feature_flag:
    name: FEATURE_EXAMPLE_ENABLED
    value: "True"
    state: present

- name: Disable a runtime feature flag
  ansible.platform.feature_flag:
    name: FEATURE_EXAMPLE_ENABLED
    value: "False"
    state: present

- name: Ensure a feature flag has a specific value
  ansible.platform.feature_flag:
    name: FEATURE_CUSTOM_SETTING_ENABLED
    value: "custom_value"
    state: enforced
...
"""

RETURN = """
id:
  description: The unique ID of the feature flag.
  returned: always
  type: int
  sample: 1

name:
  description: The name of the feature flag.
  returned: always
  type: str
  sample: FEATURE_EXAMPLE_ENABLED

ui_name:
  description: The display name for the feature flag.
  returned: always
  type: str
  sample: Example Feature

condition:
  description: The condition type for evaluating the flag.
  returned: always
  type: str
  sample: boolean

value:
  description: The current value of the feature flag.
  returned: always
  type: str
  sample: True

required:
  description: Whether this flag is required.
  returned: always
  type: bool
  sample: false

support_level:
  description: The support level of the feature flag.
  returned: always
  type: str
  sample: DEVELOPER_PREVIEW

visibility:
  description: Whether the flag is visible in the UI.
  returned: always
  type: bool
  sample: true

toggle_type:
  description: Whether the flag can be toggled at runtime or only install-time.
  returned: always
  type: str
  sample: run-time

description:
  description: Detailed description of the feature flag.
  returned: always
  type: str
  sample: Enables example functionality

support_url:
  description: URL for documentation about this feature.
  returned: always
  type: str
  sample: https://docs.example.com/feature

labels:
  description: List of labels associated with the feature flag.
  returned: always
  type: list
  sample: ["experimental", "ui"]

state:
  description: The current state of the feature flag (computed).
  returned: always
  type: bool
  sample: true
"""
