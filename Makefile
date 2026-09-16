SPHINXOPTS      ?=
BUILDDIR        = _build
DOCS_DIR        = docs
VENV            = .venv
PYTHON          = $(VENV)/bin/python
RUFFPATH        = $(VENV)/bin/ruff
PRECOMMIT       = $(VENV)/bin/pre-commit
SPHINXBUILD     = $(VENV)/bin/sphinx-build
SPHINXAUTOBUILD = $(VENV)/bin/sphinx-autobuild
ALLSPHINXOPTS   = -W -d $(BUILDDIR)/doctrees $(SPHINXOPTS) .


# environment management
.venv:  ## Create a Python virtual environment, install every extra needed for development, and install pre-commit hooks
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[test,cli,docs,lint]"
	$(PRECOMMIT) install

.PHONY: init
init: .venv  ## Alias for the default target above

.PHONY: dev
dev: .venv  ## Alias for the default target above

.PHONY: clean
clean:  ## Clean the docs build directory
	cd $(DOCS_DIR) && rm -rf $(BUILDDIR) reference/_generated reference/api

.PHONY: clean-all
clean-all: clean  ## Clean the docs build directory and the virtual environment
	rm -rf $(VENV)/
# /environment management


# development
.PHONY: lint
lint: .venv  ## Check for lint issues with ruff (same as CI would, if it ran ruff)
	$(RUFFPATH) check .

.PHONY: format
format: .venv  ## Format the code base with ruff, auto-fixing what it can
	$(RUFFPATH) format
	-$(RUFFPATH) check --fix .

.PHONY: test
test: .venv  ## Run the test suite
	$(PYTHON) -m pytest

.PHONY: dist
dist: .venv  ## Build the sdist and wheel into dist/
	$(PYTHON) -m build
# /development


# documentation builders
.PHONY: html
html: .venv  ## Build the documentation as HTML
	cd $(DOCS_DIR) && $(realpath $(SPHINXBUILD)) -b html $(ALLSPHINXOPTS) $(BUILDDIR)/html
	@echo
	@echo "Build finished. The HTML pages are in $(DOCS_DIR)/$(BUILDDIR)/html."

.PHONY: livehtml
livehtml: .venv  ## Rebuild the documentation on changes, with live-reload in the browser
	cd $(DOCS_DIR) && $(realpath $(SPHINXAUTOBUILD)) \
		--watch "../inspect_jitsi/" \
		--ignore "*/test/*" \
		--ignore "*/reference/_generated/*" \
		--ignore "*/reference/api/*" \
		-b html . "$(BUILDDIR)/html" $(SPHINXOPTS)

.PHONY: linkcheck
linkcheck: .venv  ## Check the documentation for broken links
	cd $(DOCS_DIR) && $(realpath $(SPHINXBUILD)) -b linkcheck $(ALLSPHINXOPTS) $(BUILDDIR)/linkcheck
	@echo
	@echo "Link check complete; look for any errors in the above output " \
		"or in $(DOCS_DIR)/$(BUILDDIR)/linkcheck/ ."
# /documentation builders


.PHONY: help
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
