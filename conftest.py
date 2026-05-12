# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Root conftest — ensure ansible_collections parent directory is on sys.path.

This allows ``import ansible_collections.ansible.platform.*`` to work when
running pytest directly from the collection root:

    pytest tests/unit/ -v
"""

import sys
from pathlib import Path

# conftest.py lives at ansible_collections/ansible/platform/conftest.py
# Go up 4 levels to reach the parent of ansible_collections/
_workspace_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _workspace_root not in sys.path:
    sys.path.insert(0, _workspace_root)
