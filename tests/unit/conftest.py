# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Pytest conftest for ansible.platform unit tests.

Ensures ansible_collections is importable when running pytest from the collection root:
  pytest tests/unit/plugins/connection/test_http.py -v

Requires ansible-core (or ansible) to be installed in the same environment (connection plugin
imports from ansible.plugins.connection). For full matrix testing use tox-ansible instead.
"""

import sys
from pathlib import Path

# Add parent of ansible_collections to sys.path so "import ansible_collections.ansible.platform" works
# Path: .../ansible_collections/ansible/platform/tests/unit/conftest.py -> 4x parent = ansible_collections dir
_here = Path(__file__).resolve().parent
_collections_dir = _here.parent.parent.parent.parent
_collections_parent = _collections_dir.parent
if _collections_parent not in sys.path:
    sys.path.insert(0, str(_collections_parent))
