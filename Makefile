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
	collection-install collection-test collection-docs \
	collection-lint collection-sanity  collection-test-completeness \
	collection-test-integration-check

## Set the local git configuration(specific to this repo) to look for hooks in .githooks folder
git_hooks_config:
	git config --local core.hooksPath .githooks

## Zero out all of the temp and build files
clean:
	@-find . -type f -regex ".*\.py[co]$$" -print0 | xargs -0 $(RM) -f
	@-find . -type d -name "__pycache__" -print0 \
			 -o -type d -name ".pytest_cache" -print0 | xargs -0 $(RM) -rf

## Run black syntax check
check_black:
	tox -e black -- --check $(CHECK_SYNTAX_FILES)

## Run flake8 syntax check
check_flake8:
	tox -e flake8 -- $(CHECK_SYNTAX_FILES)

## Run isort syntax check
check_isort:
	tox -e isort -- --check $(CHECK_SYNTAX_FILES)

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
collection-test: collection-install
	echo 'gateway_password: $(GATEWAY_PASSWORD)' > /tmp/collections/ansible_collections/ansible/platform/tests/integration/integration_config.yml && \
	cat /tmp/collections/ansible_collections/ansible/platform/tests/integration/integration_config.yml && \
	cd /tmp/collections/ansible_collections/ansible/platform && \
	  ansible-test integration --venv --requirements --coverage

## Run the collections test-integration check to see if all modules have integration tests
collection-test-integration-check:
	./tests/test_integration_check.py

## Run the collections test-completness check
collection-test-completeness: collection-install
	ansible-playbook /tmp/collections/ansible_collections/ansible/platform/tools/check_gateway_up.yaml && \
	./tests/test_completeness.py
