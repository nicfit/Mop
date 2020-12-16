PROJECT_NAME = $(shell python ./setup.py --name 2> /dev/null)

VERSION = $(shell python ./setup.py --version 2> /dev/null)
# FIXME, not in setup any longer
RELEASE_NAME = $(shell python ./setup.py --release-name 2> /dev/null)

PYTEST_ARGS ?=
PYPI_REPO ?= pypi
VENV_NAME ?= $(PROJECT_NAME)
RELEASE_TAG = v$(VERSION)
ABOUT_PY = mop/__about__.py
CHANGELOG = HISTORY.rst
desktopdir = ${HOME}/.local/share/applications

all: build test  ## Build and test


# Meta
help: ## List all commands
	@# This code borrowed from https://github.com/jedie/poetry-publish/blob/master/Makefile
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9 -]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

info:  ## Show project metadata
	@echo "VERSION: $(VERSION)"
	@echo "RELEASE_TAG: $(RELEASE_TAG)"
	@echo "RELEASE_NAME: $(RELEASE_NAME)"
	poetry show


## Build
.PHONY: build
build: $(ABOUT_PY) setup.py  ## Build the project

setup.py: pyproject.toml poetry.lock
	dephell deps convert --from pyproject.toml --to setup.py

$(ABOUT_PY): pyproject.toml
	regarding -o $@

data/%.desktop: data/%.desktop.in
	sed -e "s|@install_source@|`pwd`|g"\
        -e "s|@mop_exec@|`command -v mop`|g"\
        $< > $@
	desktop-file-validate $@

# Note, this clean rule is NOT to be called as part of `clean`
clean-autogen:
	-rm $(ABOUT_PY) setup.py


## Clean
clean: clean-test clean-dist  ## Clean the project
	rm -rf ./build
	rm -rf {M,m}op.egg-info
	find -type d -name __pycache__ | xargs -r rm -rf
	-rm data/*.desktop



## Test
.PHONY: test
test:  ## Run tests with default python
	tox -e py -- $(PYTEST_ARGS)

test-all:  ## Run tests with all supported versions of Python
	tox --parallel=all -- $(PYTEST_ARGS)

test-dist: dist
	poetry check
	@for f in `find dist -type f -name ${PROJECT_NAME}-${VERSION}.tar.gz \
              -o -name \*.egg -o -name \*.whl`; do \
		twine check $$f ; \
	done

lint:  ## Check coding style
	tox -e lint

clean-test:  ## Clean test artifacts (included in `clean`)
	rm -rf .tox
	-rm .coverage


## Distribute
sdist: build
	poetry build --format sdist

bdist: build
	poetry build --format wheel

.PHONY: dist
dist: clean sdist bdist  ## Create source and binary distribution files
	@# The cd dist keeps the dist/ prefix out of the md5sum files
	@cd dist && \
	for f in $$(ls); do \
		md5sum $${f} > $${f}.md5; \
	done
	@ls dist

clean-dist:  ## Clean distribution artifacts (included in `clean`)
	rm -rf dist
	find . -type f -name '*~' | xargs -r rm

check-manifest:
	check-manifest

_check-version-tag:
	@if git tag -l | grep -E '^$(shell echo ${RELEASE_TAG} | sed 's|\.|.|g')$$' > /dev/null; then \
        echo "Version tag '${RELEASE_TAG}' already exists!"; \
        false; \
    fi

authors:
	dephell generate authors

_pypi-release:
	poetry publish -r ${PYPI_REPO}


## Install
install: build install-desktop  ## Install project and dependencies
	poetry install --no-dev

install-dev: build  ## Install project, dependencies, and developer tools
	poetry install

install-desktop: data/Mop.desktop data/MopFix.desktop
	@test -d ${desktopdir} || mkdir -p ${desktopdir}
	for f in $?; do \
		desktop-file-install --dir=${desktopdir} $${f}; \
	done
	update-desktop-database ${desktopdir}


## Release
release: pre-release _freeze-release test-all dist _tag-release upload-release

upload-release: _pypi-release

pre-release: clean-autogen build install-dev info _check-version-tag clean \
             test test-dist check-manifest authors changelog
	@git status -s -b

BUMP ?= prerelease
bump-release: requirements
	@# TODO: is not a pre-release, clear release_name
	poetry version $(BUMP)

requirements:
	poetry show --outdated
	poetry update --lock
	poetry export -f requirements.txt --output requirements.txt

next-release: install-dev info

_freeze-release:
	@(git diff --quiet && git diff --quiet --staged) || \
        (printf "\n!!! Working repo has uncommitted/un-staged changes. !!!\n" && \
         printf "\nCommit and try again.\n" && false)

_tag-release:
	git tag -a $(RELEASE_TAG) -m "Release $(RELEASE_TAG)"
	git push --tags origin

changelog:
	@echo "FIXME: changelog target not yet implemented"

## Runtime environment
venv:
	source /usr/bin/virtualenvwrapper.sh && \
 		mkvirtualenv $(VENV_NAME) && \
 		pip install -U pip && \
		poetry install --no-dev

clean-venv:
	source /usr/bin/virtualenvwrapper.sh && \
 		rmvirtualenv $(VENV_NAME)

