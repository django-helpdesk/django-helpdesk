# Shortcuts for django-helpdesk testing and development using make
#
# For standard installation of django-helpdesk as a library,
# see INSTALL and the documentation in docs/.
#
# For details about how to develop django-helpdesk,
# see CONTRIBUTING.rst.
PIP = pip3
TOX = tox


#: help - Display callable targets.
.PHONY: help
help:
	@echo "django-helpdesk make shortcuts"
	@echo "Here are available targets:"
	@egrep -o "^#: (.+)" [Mm]akefile  | sed 's/#: /* /'


#: develop - Install minimal development utilities for Python3.
.PHONY: develop
develop:
	$(PIP) install -e .

#: develop2 - Install minimal development utilities for Python2.
.PHONY: develop2
develop2:
	pip2 install -e .


#: clean - Basic cleanup, mostly temporary files.
.PHONY: clean
clean:
	find . -name "*.pyc" -delete
	find . -name '*.pyo' -delete
	find . -name "__pycache__" -delete


#: distclean - Remove local builds, such as *.egg-info.
.PHONY: distclean
distclean: clean
	rm -rf *.egg
	rm -rf *.egg-info
	rm -rf demo/*.egg-info
	rm -rf helpdesk/attachments/
	# remove the django-created database
	rm -f demo/demodesk/*.sqlite3


#: maintainer-clean - Remove almost everything that can be re-generated.
.PHONY: maintainer-clean
maintainer-clean: distclean
	rm -rf build/
	rm -rf dist/
	rm -rf .tox/


#: test - Run test suites.
.PHONY: test
test:
	mkdir -p var
	$(PIP) install -e .[test]
	$(TOX)


#: documentation - Build documentation (Sphinx, README, ...).
.PHONY: documentation
documentation: sphinx readme


#: sphinx - Build Sphinx documentation (docs).
.PHONY: sphinx
sphinx:
	$(TOX) -e sphinx


#: readme - Build standalone documentation files (README, CONTRIBUTING...).
.PHONY: readme
readme:
	$(TOX) -e readme


#: demo - Setup demo project using Python3.
.PHONY: demo
demo:
	$(PIP) install -e .
	$(PIP) install -e demo
	demodesk migrate --noinput
	# Create superuser; user will be prompted to manually set a password
	# When you get a prompt, enter a password of your choosing.
	# We suggest a default of 'Test1234' for the demo project.
	demodesk createsuperuser --username admin --email helpdesk@example.com
	# Install fixtures
	demodesk loaddata emailtemplate.json
	demodesk loaddata demo.json

#: demo2 - Setup demo project using Python2.
.PHONY: demo2
demo2:
	pip2 install -e .
	pip2 install -e demo
	demodesk migrate --noinput
	# Create superuser; user will be prompted to manually set a password.
	# When you get a prompt, enter a password of your choosing.
	# We suggest a default of 'Test1234' for the demo project.
	demodesk createsuperuser --username admin --email helpdesk@example.com
	# Install fixtures (helpdesk templates as well as demo ticket data)
	demodesk loaddata emailtemplate.json
	demodesk loaddata demo.json


#: rundemo - Run demo server using Python3.
.PHONY: rundemo
rundemo: demo
	demodesk runserver 8080

#: rundemo2 - Run demo server using Python2.
.PHONY: rundemo2
rundemo2: demo2
	demodesk runserver 8080

VERSION := $(shell python ./setup.py --version 2>&1)
RELEASE_TAG := v$(VERSION)
PREV_VERSION := $(shell git describe --match='v*' 2>&1 | sed -e s'/\(v[0-9.]*\).*/\1/')

#: release - Tag and push to PyPI.
.PHONY: release
release:
	@echo ""

	@echo "Performing pre-release checks for version $(VERSION)"

	@echo -n "Looking for an existing tag $(RELEASE_TAG)... "
	@if git tag -l $(RELEASE_TAG) | grep $(RELEASE_TAG); then \
	    echo ""; \
	    echo "Error: A release tag $(RELEASE_TAG) already exists."; \
	    echo "  To make a new release, please increment the version"; \
	    echo "  number in setup.py, (use semantic versioning).";\
	    echo ""; \
	    false; \
	fi
	@echo "None found. Good"

	@echo -n "Looking for release notes for $(VERSION)... "
	@if ! grep -q '^$(VERSION) ' CHANGES; then \
	    echo "None found. Bad"; \
	    echo ""; \
	    echo "Error: No release notes found for version $(VERSION)"; \
	    echo ""; \
	    echo "  Please look through completed Trello cards and recent"; \
	    echo "  commits, then summarize changes in the file"; \
	    echo "  CHANGES"; \
	    echo ""; \
	    echo "  The following output may prove useful:"; \
	    echo ""; \
	    echo "  $$ git log $(PREV_VERSION).."; \
	    echo ""; \
	    git --no-pager log $(PREV_VERSION)..; \
	    false; \
	fi
	@echo "Found them. Good"

	@echo -n "Checking for locally-modified files... "
	@mods=$$(git ls-files -m); if [ "$${mods}" != "" ]; then \
	    echo "Found some. Bad"; \
	    echo ""; \
	    echo "Error: The following files have modifications."; \
	    echo "  Please commit the desired changes to git before"; \
	    echo "  attempting a release."; \
	    echo ""; \
	    echo "$$mods"; \
	    echo ""; \
	    false; \
	fi
	@echo "None found. Good"

	@echo -n "Checking for unpushed commits..."
	@commits=$$(git log --oneline origin/master..); \
        if [ "$${commits}" != "" ]; then \
	    echo "Found some. Bad"; \
	    echo ""; \
	    echo "Error: The following commits are not on origin/master."; \
	    echo "  Please push these out before attempting a release."; \
            echo ""; \
            echo "$$commits"; \
            echo ""; \
            false; \
        fi
	@echo "None found. Good"

	@echo ""
	@echo "Preparing to package and release version $(VERSION)"
	@echo "to the Nimbis private repository. You have 10 seconds to abort."
	@echo ""
	@for cnt in $$(seq 10 -1 1); do echo -n "$$cnt... "; sleep 1; done
	@echo "0"

	@echo "python setup.py sdist upload -r nimbis"
	@if ! python setup.py sdist upload -r nimbis; then \
	    echo ""; \
	    echo "Error: Failed to upload new release."; \
	    echo "  Please resolve any error messages above, and then"; \
	    echo "  try again."; \
	    false; \
	fi

	@echo ""
	@echo "Successfully released a package with version $(VERSION)"

	@if ! git tag -s -m "Release $(VERSION)" $(RELEASE_TAG); then \
	    echo ""; \
	    echo "Error: Packaged release has been uploaded, but failed to"; \
	    echo "  create a tag. Please create and push a $(RELEASE_TAG)"; \
	    echo "  tag manually now"; \
	    false; \
        fi

	@if ! git push origin $(RELEASE_TAG); then \
	    echo ""; \
	    echo "Error: Packaged release has been uploaded and tagged."; \
	    echo "  But an error occurred while pushing the tag. Please"; \
	    echo "  manually push the $(RELEASE_TAG) tag now"; \
	    false; \
	fi


