#!/usr/bin/env python

import os
import re
import base64

import requests

GH_WORKSPACE = os.environ.get("GH_WORKSPACE", "")
TOKEN = os.environ.get("GH_TOKEN")

GH_API_HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def _git_auth_header():
    """Create the authorization header.

    helpful: https://github.com/actions/checkout/blob/main/src/git-auth-helper.ts#L56

    :param token: The token
    :return: The base64 encoded token and the authorization header cli parameter
    """
    basic = f"x-access-token:{TOKEN}"
    basic_encoded = base64.b64encode(basic.encode("utf-8")).decode("utf-8")
    return basic_encoded


def _git_clone(repo_url, branch, local_destination):
    """Clone the a repo with a specified branch in local directory.
    :param repo_url: The repository to clone.
    :param branch: The branch in the repository to clone.
    :param local_destination: The local directory where the repo will be cloned.
    """
    print(
        f"Checking out {branch} branch of {repo_url} into {GH_WORKSPACE}/{local_destination}"
    )
    os.system(
        f"git clone {repo_url} -b {branch} --depth=1 -c http.extraheader='AUTHORIZATION: basic {_git_auth_header()}' {GH_WORKSPACE}/{local_destination}"
    )


def _get_requires(pr_body, target):
    """Return the Pull Request number specified as required.

    :param pr_body: The Pull Request body to parse.
    :param target: The repository name containing the Pull Request.
    """
    requires_re = re.compile(
        f"requires.*ansible-automation-platform/{target}(?:#|/pull/)([0-9]+)",
        re.IGNORECASE,
    )
    matches = requires_re.search(pr_body)
    if matches:
        return matches.group(1)


def _checkout_aap_gateway(pr_body):
    """Checkout aap-gateway, either from devel OR from a specified Pull Request.
       Return the body of the specified Pull Request, if any.
    :param pr_body: The ansible.platform PR body.
    """
    repo_url = "https://github.com/ansible-automation-platform/aap-gateway"
    branch = "devel"
    aap_gateway_pr_body = ""

    required_pr = _get_requires(pr_body, target="aap-gateway")
    if required_pr:
        print(f"This ansible.platform PR requires aap-gateway PR {required_pr}")
        url = f"https://api.github.com/repos/ansible-automation-platform/aap-gateway/pulls/{required_pr}"
        response = requests.get(url, headers=GH_API_HEADERS)
        pr_data = response.json()
        merged = pr_data["merged"]

        if not merged:
            # if PR is not merged, checkout the repo and branch specified by "Requires"
            repo_url = pr_data["head"]["repo"]["html_url"]
            branch = pr_data["head"]["ref"]
            aap_gateway_pr_body = pr_data.get("body", "")
        else:
            print(
                f"The referenced PR {required_pr} of aap-gateway has been merged already, no need to check out the branch!"
            )

    _git_clone(repo_url=repo_url, branch=branch, local_destination="aap-gateway")

    return aap_gateway_pr_body


def _checkout_django_ansible_base(pr_body):
    """Checkout a django-ansible-base branch if specified in an aap-gateway Pull Request.
    :param pr_body: The aap-gateway PR body.
    """
    required_pr = _get_requires(pr_body, target="django-ansible-base")

    if required_pr:
        print(f"This aap-gateway PR requires django-ansible-base PR {required_pr}")
        url = f"https://api.github.com/repos/ansible/django-ansible-base/pulls/{required_pr}"
        response = requests.get(url)
        pr_data = response.json()
        merged = pr_data["merged"]

        if not merged:
            # if PR is not merged, checkout the repo and branch specified by "Requires"
            repo_url = pr_data["head"]["repo"]["html_url"]
            branch = pr_data["head"]["ref"]
            _git_clone(
                repo_url=repo_url,
                branch=branch,
                local_destination="aap-gateway/django-ansible-base",
            )
        else:
            print(
                f"The referenced PR {required_pr} of django-ansible-base has been merged already, no need to check out the branch!"
            )
    else:
        print("No django-ansible-base PR was specified!")


def main():
    # get ansible.platform Pull Request body
    platform_pr_body = os.environ.get("PR_BODY", "")

    # checkout aap-gateway
    aap_gateway_pr_body = _checkout_aap_gateway(pr_body=platform_pr_body)

    # checkout a specific DAB branch (only if specified in aap-gateway PR)
    _checkout_django_ansible_base(pr_body=aap_gateway_pr_body)


if __name__ == "__main__":
    main()
