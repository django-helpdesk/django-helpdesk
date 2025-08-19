# Shortcuts for django-helpdesk testing and development using make
#
# For standard installation of django-helpdesk as a library,
# see INSTALL and the documentation in docs/.
#
# For details about how to develop django-helpdesk,
# see CONTRIBUTING.rst.
UV = uv
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
	$(UV) venv
	$(UV) sync --all-extras --dev --group test
	$(UV) tool install pre-commit --with pre-commit-uv --force-reinstall
	pre-commit install

#: sync - Synchronise the envoronment with the project configuration
.PHONY: sync
sync:
	$(UV) sync --all-extras --dev --group test


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
	$(UV) run quicktest.py
	

#: format - Run the PEP8 formatter.
.PHONY: format
format:
	uv tool run ruff check --fix # Fix linting errors
	uv tool run ruff format # fix formatting errors


#: checkformat - checks formatting against configured format specifications for the project.
.PHONY: checkformat
checkformat:
	uv tool run ruff check # linting check
	uv tool run ruff format --check # format check


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
# Requires using the PYTHONPATH prefix because the project directory is not set in the path
.PHONY: demo
demo:
	uv  sync  --all-extras --dev --group test --group teams
	uv run demodesk/manage.py migrate --noinput
	# Install fixtures
	uv run demodesk/manage.py loaddata emailtemplate.json
	# The password for the "admin" user is 'Pa33w0rd' for the demo project.
	uv run demodesk/manage.py loaddata demo.json


#: rundemo - Run demo server using Python3.
.PHONY: rundemo
rundemo: demo
	uv run demodesk/manage.py runserver 8080
	
#: migrations - Create Django migrations for this project.
.PHONY: migrations
migrations: demo
	uv run demodesk/manage.py makemigrations


#: release - Tag and push to PyPI.
.PHONY: release
release:
	$(TOX) -e release
