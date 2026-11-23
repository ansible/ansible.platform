# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Pytest conftest for ansible.platform unit tests.

Ensures ansible_collections is importable when running pytest from the collection root:
  pytest tests/unit/plugins/connection/test_http.py -v

Requires ansible-core (or ansible) to be installed in the same environment (connection plugin
imports from ansible.plugins.connection). For full matrix testing use tox-ansible instead.
"""

import os
import sys
from pathlib import Path

import pytest

# Add parent of ansible_collections to sys.path so "import ansible_collections.ansible.platform" works
# Path: .../ansible_collections/ansible/platform/tests/unit/conftest.py -> 4x parent = ansible_collections dir
_here = Path(__file__).resolve().parent
_collections_dir = _here.parent.parent.parent.parent
_collections_parent = _collections_dir.parent
if _collections_parent not in sys.path:
    sys.path.insert(0, str(_collections_parent))

# Gateway authentication environment variables honoured by extract_gateway_config.
# Developers commonly export these to run playbooks against a live AAP instance;
# left set, they would leak into unit tests and make results machine-dependent.
_GATEWAY_ENV_VARS = (
    "GATEWAY_HOSTNAME",
    "AAP_HOSTNAME",
    "GATEWAY_USERNAME",
    "AAP_USERNAME",
    "GATEWAY_PASSWORD",
    "AAP_PASSWORD",
    "GATEWAY_API_TOKEN",
    "AAP_TOKEN",
    "GATEWAY_VERIFY_SSL",
    "AAP_VALIDATE_CERTS",
    "GATEWAY_REQUEST_TIMEOUT",
    "AAP_REQUEST_TIMEOUT",
)


@pytest.fixture(autouse=True)
def _clear_gateway_env():
    """Remove gateway auth environment variables for the duration of each test.

    Autouse so that tests which assert defaults, or assert that a missing
    hostname raises, behave identically on a developer laptop with these
    variables exported and in CI where they are unset.  Tests that want to
    exercise environment resolution should pass an explicit ``env`` mapping to
    ``extract_gateway_config`` rather than mutating ``os.environ``.
    """
    saved = {name: os.environ.pop(name) for name in _GATEWAY_ENV_VARS if name in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)
