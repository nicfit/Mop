PYTEST_ARGS ?=
PYPI_REPO ?= pypitest
PROJECT_NAME = $(shell python ./setup.py --name 2> /dev/null)
VERSION = $(shell python ./setup.py --version 2> /dev/null)
RELEASE_TAG = v$(VERSION)
RELEASE_NAME = $(shell python setup.py --release-name 2> /dev/null)
CHANGELOG = HISTORY.rst

desktopdir = ${HOME}/.local/share/applications

.PHONY: build dist requirements


### Build
all: build

build:
	python ./setup.py build

%.desktop: %.desktop.in
	sed -e "s|@install_source@|`pwd`|g"\
        -e "s|@exec_prefix@|`dirname `command -v mop``|g"\
        $< > $@
	desktop-file-validate $@


### Clean
clean: clean-dist clean-test
	rm -rf ./build
	find -type d -name __pycache__ | xargs -r rm -rf
	rm -rf Mop.egg-info
	-rm Mop.desktop

clean-dist:
	rm -rf ./dist
	find . -type f -name '*~' | xargs -r rm

clean-test:
	rm -rf .tox
	-rm .coverage


### Develop
setup.py: pyproject.toml poetry.lock
	dephell deps convert --from-format poetry --from pyproject.toml \
                         --to-format setuppy --to setup.py

develop: setup.py
	poetry install

lint:
	tox -e lint

test:
	tox -- $(PYTEST_ARGS)

test-all:
	tox --parallel=all

test-dist: dist
	@for f in `find dist -type f -name ${PROJECT_NAME}-${VERSION}.tar.gz \
              -o -name \*.egg -o -name \*.whl`; do \
		twine check $$f ; \
	done


### Install
install: build install-desktop
	python ./setup.py install

install-desktop: Mop.desktop MopFix.desktop
	@test -d ${desktopdir} || mkdir -p ${desktopdir}
	for f in $?; do \
		desktop-file-install --dir=${desktopdir} $${f}; \
	done
	update-desktop-database ${desktopdir}


### Distribute
sdist: build setup.py
	python ./setup.py sdist --formats=gztar,zip

bdist: setup.py
	python ./setup.py bdist_egg
	python ./setup.py bdist_wheel

dist: clean sdist bdist
	@# The cd dist keeps the dist/ prefix out of the md5sum files
	cd dist && \
	for f in $$(ls); do \
		md5sum $${f} > $${f}.md5; \
	done
	@ls -l dist

requirements:
	poetry update
	poetry install
	poetry export -f requirements.txt --output requirements.txt

install-requirements:
	poetry install --no-dev

install-dev-requirements:
	poetry install

pypi-release:
	# FIXME: poetry publish
	for f in `find dist -type f -name ${PROJECT_NAME}-${VERSION}.tar.gz \
              -o -name \*.egg -o -name \*.whl`; do \
        if test -f $$f ; then \
            twine upload --verbose -r ${PYPI_REPO} --skip-existing $$f ; \
        fi \
	done

authors:
	# FIXME: dephell generate authors ??
	@IFS=$$'\n';\
	for auth in `git authors --list | sed 's/.* <\(.*\)>/\1/' | grep -v users.noreply.github.com`; do \
		echo "Checking $$auth...";\
		grep "$$auth" AUTHORS.rst || echo "  * $$auth" >> AUTHORS.rst;\
	done

info:
	@echo "VERSION: $(VERSION)"
	@echo "RELEASE_TAG: $(RELEASE_TAG)"
	@echo "RELEASE_NAME: $(RELEASE_NAME)"

check-version-tag:
	@if git tag -l | grep -E '^$(shell echo $${RELEASE_TAG} | sed 's|\.|.|g')$$' > /dev/null; then \
        echo "Version tag '${RELEASE_TAG}' already exists!"; \
        false; \
    fi

check-manifest:
	tox -e check-manifest

freeze-release:
	@(git diff --quiet && git diff --quiet --staged) || \
        (printf "\n!!! Working repo has uncommited/unstaged changes. !!!\n" && \
         printf "\nCommit and try again.\n" && false)

changelog:
	touch $(CHANGELOG)

pre-release: info clean\
             requirements test test-dist check-manifest check-version-tag\
             authors changelog

tag-release:
	git tag -a $(RELEASE_TAG) -m "Release $(RELEASE_TAG)"
	git push --tags origin

release: pre-release freeze-release test-all dist tag-release pypi-release
