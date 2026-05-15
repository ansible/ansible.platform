SHELL=/bin/bash

# Prefer python 3.11 but take python3 if 3.11 is not installed
PYTHON := $(notdir $(shell for i in python3.11 python3; do command -v $$i; done|sed 1q))
RM ?= /bin/rm
UID := $(shell id -u)
ANSIBLE_CONFIG ?= tools/ansible/ansible.cfg
export ANSIBLE_CONFIG

## Get the version of python we are working with
PYTHON_VERSION:
	@echo "$(subst python,,$(PYTHON))"

.PHONY: PYTHON_VERSION clean git_hooks_config \
	check_ruff check_mypy check_pydoclint \
	collection-install collection-test collection-docs \
	collection-lint collection-sanity  collection-test-completeness \
	collection-test-integration-check \
	collection-test-local collection-test-http-direct collection-test-http-persistent \
	collection-test-all-connections \
	molecule-test molecule-test-all

## Set the local git configuration(specific to this repo) to look for hooks in .githooks folder
git_hooks_config:
	git config --local core.hooksPath .githooks

## Zero out all of the temp and build files
clean:
	@-find . -type f -regex ".*\.py[co]$$" -print0 | xargs -0 $(RM) -f
	@-find . -type d -name "__pycache__" -print0 \
			 -o -type d -name ".pytest_cache" -print0 | xargs -0 $(RM) -rf

## Run ruff lint and format check (replaces flake8, black, isort)
check_ruff:
	tox -e ruff

## Run mypy static type check
check_mypy:
	tox -e mypy

## Run pydoclint docstring style check
check_pydoclint:
	tox -e pydoclint

## Install the collection locally on your machine
collection-install:
	ansible-galaxy collection install . --force

## Run the collection sanity tests
collection-sanity: collection-install
	cd /tmp/collections/ansible_collections/ansible/platform && \
	ansible-test sanity

## Run the collections docs check
collection-docs: collection-install
	@RC=0 ; \
	for file_name in $$(ls plugins/modules/*.py) ; do \
            module=$$(echo $${file_name} | sed 's:^.*/::' | sed 's:\..*::') ; \
            ansible-doc -M plugins/modules $${module} 1> /dev/null ; \
            RC=$$(( RC + $$? )) ; \
	done ; \
	for file_name in $$(ls plugins/lookup/*.py) ; do \
            module=$$(echo $${file_name} | sed 's:^.*/::' | sed 's:\..*::') ; \
            ansible-doc -M plugins/lookup -t lookup $${module} 1> /dev/null ; \
            RC=$$(( RC + $$? )) ; \
	done ; \
	if [[ $$RC -eq 0 ]] ; then echo "Doc Passed" ; else echo "Docs Failed" ; fi ; \
	exit $$RC

## Run the collection lint check
collection-lint: collection-install
	# ansible-lint gets its settings from .ansible-lint
	ansible-lint --profile=production

## Run the collection tests
## Requires the GATEWAY_PASSWORD env variable to be set
## Set ANSIBLE_TEST_INTEGRATION_NO_VENV=1 to run without --venv (e.g. in CI after installing controller deps)
## Set CONNECTION_MODE to control which connection mode is tested:
##   local            (default) – ephemeral DirectHTTPClient, one per task
##   http-direct      – ansible.platform.http plugin, DirectHTTPClient, one per task
##   http-persistent  – ansible.platform.http plugin, shared ManagerRPCClient process
ANSIBLE_TEST_INTEGRATION_VENV := --venv
ifneq ($(ANSIBLE_TEST_INTEGRATION_NO_VENV),)
ANSIBLE_TEST_INTEGRATION_VENV :=
endif
CONNECTION_MODE ?= local

## Set GATEWAY_SSL_PRIVATE_CA=true to enable SSL env forwarding assertions (Tests 1 & 2)
## in ssl_env_forwarding_test.  Only effective when the gateway cert is signed by a
## private CA not present in the system trust store.  Leave unset in standard CI.
GATEWAY_SSL_PRIVATE_CA ?=

_write_integration_config:
	@mkdir -p /tmp/collections/ansible_collections/ansible/platform/tests/integration
	@printf 'gateway_password: %s\nconnection_mode: %s\ngateway_tls_ca_bundle_path: %s\ngateway_ssl_private_ca: %s\n' \
		'$(GATEWAY_PASSWORD)' '$(CONNECTION_MODE)' '$(GATEWAY_TLS_CA_BUNDLE_PATH)' '$(GATEWAY_SSL_PRIVATE_CA)' \
		> /tmp/collections/ansible_collections/ansible/platform/tests/integration/integration_config.yml
	@cat /tmp/collections/ansible_collections/ansible/platform/tests/integration/integration_config.yml

collection-test: collection-install _write_integration_config
	cd /tmp/collections/ansible_collections/ansible/platform && \
	  ansible-test integration --color yes $(ANSIBLE_TEST_INTEGRATION_VENV) --requirements --coverage

## Run integration tests explicitly using connection: local (default ephemeral mode)
collection-test-local: collection-install
	$(MAKE) collection-test CONNECTION_MODE=local

## Run integration tests using connection: ansible.platform.http in direct (non-persistent) mode
collection-test-http-direct: collection-install
	$(MAKE) collection-test CONNECTION_MODE=http-direct

## Run integration tests using connection: ansible.platform.http in persistent manager mode
collection-test-http-persistent: collection-install
	$(MAKE) collection-test CONNECTION_MODE=http-persistent

## Run integration tests sequentially for all three connection modes
collection-test-all-connections: collection-install
	$(MAKE) collection-test CONNECTION_MODE=local
	$(MAKE) collection-test CONNECTION_MODE=http-direct
	$(MAKE) collection-test CONNECTION_MODE=http-persistent

## Run a single Molecule scenario (mock tests, no real Gateway needed).
## Usage: make molecule-test SCENARIO=role_user_assignment_mock
##        make molecule-test SCENARIO=users_mock
## Runs from inside the scenario directory so molecule finds molecule.yml regardless of version.
SCENARIO ?= default
molecule-test:
	cd extensions/molecule/$(SCENARIO) && molecule test

## Run all Molecule mock scenarios (starts mock server via default scenario, runs all, tears down).
molecule-test-all:
	cd extensions && molecule test --all

## Run the collections test-integration check to see if all modules have integration tests
collection-test-integration-check:
	./tests/test_integration_check.py

## Run the collections test-completness check
## Requires the GATEWAY_PASSWORD env variable to be set
collection-test-completeness: collection-install
	ansible-playbook /tmp/collections/ansible_collections/ansible/platform/tools/check_gateway_up.yaml -e "gateway_password=$(GATEWAY_PASSWORD)" && \
	./tests/test_completeness.py
