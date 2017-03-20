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


#: develop - Install minimal development utilities for Python3
.PHONY: develop
develop:
	$(PIP) install -e .

#: develop - Install minimal development utilities for Python2
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


#: documentation - Build documentation (Sphinx, README, ...)
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

#: demo - Setup demo project using Python2.
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


#: runserver - Run demo server using Python3
.PHONY: rundemo
rundemo: demo
	demodesk runserver 8080

#: runserver - Run demo server using Python2
.PHONY: rundemo2
rundemo2: demo2
	demodesk runserver 8080


#: release - Tag and push to PyPI.
.PHONY: release
release:
	$(TOX) -e release
