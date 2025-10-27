SHELL=/bin/bash

# Prefer python 3.11 but take python3 if 3.11 is not installed
PYTHON := $(notdir $(shell for i in python3.11 python3; do command -v $$i; done|sed 1q))
RM ?= /bin/rm
UID := $(shell id -u)
ANSIBLE_CONFIG ?= tools/ansible/ansible.cfg
export ANSIBLE_CONFIG

.PHONY: PYTHON_VERSION clean git_hooks_config \
	collection-install collection-test collection-docs \
	collection-lint collection-sanity collection-test-completeness \
	collection-test-integration-check gateway-build gateway-install \
	collection collection-build setup-for-gateway

## Get the version of python we are working with
PYTHON_VERSION:
	@echo "$(subst python,,$(PYTHON))"

## Set the local git configuration(specific to this repo) to look for hooks in .githooks folder
git_hooks_config:
	git config --local core.hooksPath .githooks

## Zero out all of the temp and build files
clean:
	@-find . -type f -regex ".*\.py[co]$$" -print0 | xargs -0 $(RM) -f
	@-find . -type d -name "__pycache__" -print0 \
			 -o -type d -name ".pytest_cache" -print0 | xargs -0 $(RM) -rf

## Syntax checks
check_black:
	tox -e black -- --check $(CHECK_SYNTAX_FILES)
check_flake8:
	tox -e flake8 -- $(CHECK_SYNTAX_FILES)
check_isort:
	tox -e isort -- --check $(CHECK_SYNTAX_FILES)

## Install the collection locally (developer use)
collection-install:
	ansible-galaxy collection install . --force

## Build tarball for distribution
collection-build:
	ansible-galaxy collection build . --force -o dist
	@echo "Collection built under dist/"

## Alias for old 'collection' targets used by other repos/CI
collection: collection-build
	@tarball=$$(ls -1t dist/ansible-platform-*.tar.gz | head -1); \
	 echo "Installing $$tarball"; \
	 ansible-galaxy collection install "$$tarball" --force

## End-to-end helper for Gateway or any AAP component CI
setup-for-gateway: collection
	@echo "ansible.platform is now built and installed for external CI"

## Run the collection sanity tests
collection-sanity: collection-install
	cd /tmp/collections/ansible_collections/ansible/platform && ansible-test sanity

## Run docs check
collection-docs: collection-install
	@RC=0 ; \
	for file_name in $$(ls plugins/modules/*.py); do \
	  module=$$(basename $$file_name .py); \
	  ansible-doc -M plugins/modules $$module >/dev/null; RC=$$((RC + $$?)); \
	done; \
	for file_name in $$(ls plugins/lookup/*.py); do \
	  module=$$(basename $$file_name .py); \
	  ansible-doc -M plugins/lookup -t lookup $$module >/dev/null; RC=$$((RC + $$?)); \
	done; \
	if [[ $$RC -eq 0 ]]; then echo "Doc Passed"; else echo "Docs Failed"; fi; \
	exit $$RC

## Run lint
collection-lint: collection-install
	ansible-lint --profile=production

## Integration tests
collection-test: collection-install
	echo 'gateway_password: $(GATEWAY_PASSWORD)' > /tmp/collections/ansible_collections/ansible/platform/tests/integration/integration_config.yml && \
	cd /tmp/collections/ansible_collections/ansible/platform && \
	ansible-test integration --color yes --venv --requirements --coverage

## Integration completeness checks
collection-test-integration-check:
	./tests/test_integration_check.py

collection-test-completeness: collection-install
	ansible-playbook /tmp/collections/ansible_collections/ansible/platform/tools/check_gateway_up.yaml \
		-e "gateway_password=$(GATEWAY_PASSWORD)" && ./tests/test_completeness.py
