# (c) 2020 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
name: gateway_api
author: John Westcott IV (@john-westcott-iv)
short_description: Search the API for objects
requirements:
  - None
description:
  - Returns GET requests from the Automation Platform Gateway API. See
    U(https://docs.ansible.com/TODO) for API usage.
  - This plugin is designed to support Gateway API endpoints used to manage resources with ansible.platform modules,
    such as users, teams, organizations, settings, role_definitions, and related endpoints.
  - Querying APIs outside of the Gateway API (such as Automation Hub, Galaxy etc.) is not supported and may lead to unexpected errors.
options:
  _terms:
    description:
      - The endpoint to query, i.e. teams, users, tokens, settings, services, etc.
    required: True
  query_params:
    description:
      - The query parameters to search for in the form of key/value pairs.
    type: dict
    required: False
    aliases: [query, data, filter, params]
  expect_objects:
    description:
      - Error if the response does not contain either a detail view or a list view.
    type: boolean
    default: False
    aliases: [expect_object]
  expect_one:
    description:
      - Error if the response contains more than one object.
    type: boolean
    default: False
  return_objects:
    description:
      - If a list view is returned, promote the list of results to the top-level of list returned.
      - Allows using this lookup plugin to loop over objects without additional work.
    type: boolean
    default: True
  return_all:
    description:
      - If the response is paginated, return all pages.
    type: boolean
    default: False
  return_ids:
    description:
      - If response contains objects, promote the id key to the top-level entries in the list.
      - Allows looking up a related object and passing it as a parameter to another module.
      - This will convert the return to a string or list of strings depending on the number of selected items.
    type: boolean
    aliases: [return_id]
    default: False
  max_objects:
    description:
      - if C(return_all) is true, this is the maximum of number of objects to return from the list.
      - If a list view returns more an max_objects an exception will be raised
    type: integer
    default: 1000
extends_documentation_fragment: ansible.platform.auth_lookup
notes:
  - If the query is not filtered properly this can cause a performance impact.
"""

RETURN = """
_raw:
  description:
    - Response from the API
  type: dict
  returned: on successful request
"""

EXAMPLES = """
- name: Load the UI settings
  set_fact:
    ui_settings: "{{ lookup('ansible.platform.gateway_api', 'settings/ui') }}"

- name: Load the UI settings specifying the connection info
  set_fact:
    ui_settings: "{{ lookup('ansible.platform.gateway_api', 'settings/ui', host='gateway.example.com',
                             username='admin', password=my_pass_var, verify_ssl=False) }}"

- name: Report the usernames of all users with admin privs
  debug:
    msg: "Admin users: {{ admins }}"
  vars:
    admins: "{{ query('ansible.platform.gateway_api', 'users', query_params={ 'is_superuser': true }) | map(attribute='username') | join(', ') }}"

- name: debug all organizations in a loop  # use query to return a list
  debug:
    msg: "Organization description={{ item['description'] }} id={{ item['id'] }}"
  loop: "{{ query('ansible.platform.gateway_api', 'organizations') }}"
  loop_control:
    label: "{{ item['name'] }}"

- name: Make sure user 'john' is an org admin of the default org if the user exists
  role:
    organization: Default
    role: admin
    user: john
  when: "lookup('ansible.platform.gateway_api', 'users', query_params={ 'username': 'john' }) | length == 1"

- name: Create an inventory group with all 'foo' hosts
  group:
    name: "Foo Group"
    inventory: "Demo Inventory"
    hosts: >-
      {{ query(
           'ansible.platform.gateway_api',
            'hosts',
            query_params={ 'name__startswith' : 'foo', },
        ) | map(attribute='name') | list }}
  register: group_creation
...
"""

from ansible.errors import AnsibleError  # noqa
from ansible.module_utils._text import to_native  # noqa
from ansible.plugins.lookup import LookupBase  # noqa
from ansible.utils.display import Display  # noqa


class LookupModule(LookupBase):
    """
    Lookup plugin that queries the Automation Platform Gateway API.

    All HTTP/SSL work is delegated to the manager subprocess via
    spawn_ephemeral_client() + client.search_api(), keeping the forked Ansible
    worker process completely free of SSL initialisation.  This avoids the
    macOS + Python 3.12 SIGABRT ("A worker was found in a dead state") that
    occurs when urllib or requests initialises an SSL context inside a fork.

    The stable-2.6 call signature is fully preserved: the same plugin options
    (host, username, password, verify_ssl, oauth_token, request_timeout,
    query_params, return_objects, return_ids, expect_one, expect_objects,
    return_all, max_objects) are accepted unchanged.  aap_module.py and
    aap_object.py are retained in plugins/module_utils/ for import backward
    compatibility with any custom code that imports them directly.
    """

    display = Display()

    @staticmethod
    def _to_plain(value):
        """
        Strip Ansible tagged types (e.g. _AnsibleTaggedStr, AnsibleUnsafeText)
        and return plain Python objects.

        multiprocessing.managers RPC serialises arguments with pickle. Ansible
        forbids pickling its lazy/tagged objects, so we must convert everything
        to plain Python types before any cross-process call.

        A JSON round-trip is the simplest universal approach: it handles nested
        dicts/lists/strings and always produces plain builtins.
        """
        import json

        if value is None:
            return None
        try:
            return json.loads(json.dumps(value))
        except (TypeError, ValueError):
            # Fallback for non-JSON-serialisable edge cases
            return str(value)

    def _build_gateway_config(self):
        """Build a GatewayConfig from the lookup options (plain Python types only)."""
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig

        host = self._to_plain(self.get_option("host")) or "https://localhost/"
        return GatewayConfig(
            base_url=str(host),
            username=str(self._to_plain(self.get_option("username")) or ""),
            password=str(self._to_plain(self.get_option("password")) or ""),
            oauth_token=str(self._to_plain(self.get_option("oauth_token")) or ""),
            verify_ssl=bool(self.get_option("verify_ssl")),
            request_timeout=float(self.get_option("request_timeout") or 60),
            connection_mode="direct",
        )

    def run(self, terms, variables=None, **kwargs):
        if len(terms) != 1:
            raise AnsibleError("You must pass exactly one endpoint to query")

        self.set_options(direct=kwargs)

        # Strip Ansible tagged types before any RPC/pickle boundary.
        # multiprocessing.managers serialises call arguments with pickle, and
        # Ansible explicitly forbids pickling its lazy objects.
        endpoint = str(self._to_plain(terms[0]))
        query_params = self._to_plain(self.get_option("query_params")) or {}
        return_all = bool(self.get_option("return_all"))
        max_objects = int(self.get_option("max_objects") or 1000)

        # Delegate all HTTP/SSL work to a fresh manager subprocess so the
        # forked Ansible worker never touches SSL (macOS + Python 3.12 safety).
        try:
            from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import spawn_ephemeral_client

            gateway_config = self._build_gateway_config()
            # spawn_ephemeral_client expects task_vars for facts; pass empty dict
            # since lookups don't set host facts.
            client, _facts = spawn_ephemeral_client({}, gateway_config)
        except Exception as e:
            raise AnsibleError("gateway_api lookup: failed to connect to platform manager: {0}".format(to_native(e)))

        try:
            return_data = client.search_api(
                endpoint=endpoint,
                query_params=query_params,
                return_all=return_all,
                max_objects=max_objects,
            )
        except ValueError as e:
            raise AnsibleError("gateway_api lookup: {0}".format(to_native(e)))
        except Exception as e:
            raise AnsibleError("gateway_api lookup: API request failed for '{0}': {1}".format(endpoint, to_native(e)))
        finally:
            try:
                client.shutdown_manager()
            except Exception:
                pass

        # --- response validation ---
        if self.get_option("expect_objects") or self.get_option("expect_one"):
            if ("id" not in return_data) and ("results" not in return_data):
                raise AnsibleError("Did not obtain a list or detail view at '{0}', and expect_objects or expect_one is set to True".format(endpoint))

        if self.get_option("expect_one"):
            if "results" in return_data and len(return_data["results"]) != 1:
                raise AnsibleError("Expected one object from endpoint {0}, but obtained {1} from API".format(endpoint, len(return_data["results"])))

        # --- result shaping ---
        if self.get_option("return_ids"):
            if "results" in return_data:
                return_data["results"] = [str(item["id"]) for item in return_data["results"]]
            elif "id" in return_data:
                return_data = str(return_data["id"])

        if self.get_option("return_objects") and "results" in return_data:
            return return_data["results"]
        return [return_data]
