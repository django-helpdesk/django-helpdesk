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


REQUIRED_BINS := node
$(foreach bin,$(REQUIRED_BINS),\
    $(if $(shell command -v $(bin) 2> /dev/null),,$(error Please install: `$(bin)`)))

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
	$(UV) sync --dev --group test
	$(UV) tool install pre-commit --with pre-commit-uv --force-reinstall
	pre-commit install

#: sync - Synchronize the environment with the project configuration
.PHONY: sync
sync:
	$(UV) sync --dev --group test


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
	rm -rf helpdesk/attachments
	# remove the django-created database
	rm -f demodesk/*.sqlite3
	find $(STATIC_DIR) -mindepth 1 -maxdepth 1 ! -name 'flot' ! -name 'README.md' ! -name 'flot-tooltip' ! -name 'morrisjs' ! -name 'timeline3' -exec rm -rf {} +


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
	yarn install
	make static-vendor
	uv  sync --dev --group test
	uv run manage.py migrate --noinput
	# Install fixtures
	uv run manage.py loaddata emailtemplate.json
	# The password for the "admin" user is 'Pa33w0rd' for the demo project.
	uv run manage.py loaddata demo.json
	# Staff, customers and tickets dated relative to today, same password.
	uv run manage.py demo_data


#: rundemo - Run demo server using Python3.
.PHONY: rundemo
rundemo: demo
	uv run manage.py runserver 8080

#: messages - Regenerate and compile the translation catalogs.
# makemessages --all would look in the demo project's LOCALE_PATHS, so every
# language in src/helpdesk/locale is passed explicitly.
.PHONY: messages
messages:
	cd src/helpdesk && for lang in $$(ls locale); do \
		DJANGO_SETTINGS_MODULE=demodesk.config.settings PYTHONPATH=..:../.. \
		$(UV) run django-admin makemessages --no-obsolete -l $$lang || exit 1; \
	done
	cd src/helpdesk && $(UV) run django-admin compilemessages

#: migrations - Create Django migrations for this project.
.PHONY: migrations
migrations: demo
	uv run manage.py makemigrations


#: release - Tag and push to PyPI.
.PHONY: release
release:
	$(TOX) -e release

# Yarn
STATIC_DIR := src/helpdesk/static/helpdesk/vendor


# Use jq to read the top-level 'dependencies' keys from package.json
# The tr command converts newlines to spaces for Make.

VENDORS := $(shell node get_deps.js | tr '\n[],' ' ')

.PHONY: static-vendor setup-vendor-dirs
static-vendor: setup-vendor-dirs $(addprefix $(STATIC_DIR)/,$(VENDORS))
	@echo "Static vendor copy complete for: $(VENDORS)"

# Target to create the base vendor directory
setup-vendor-dirs:
	@mkdir -p $(STATIC_DIR)

# A Pattern Rule for copying each vendor
# This rule applies to every vendor listed in the VENDORS variable
# TODO It would be worth experimenting with node -p "require.resolve('PACKAGE')"
$(STATIC_DIR)/%:
	@VENDOR_NAME=$*; \
	DEST_DIR=$(STATIC_DIR)/$$VENDOR_NAME; \
	SRC_DIR=node_modules/$$VENDOR_NAME; \
	DATATABLES_DIR=$(STATIC_DIR)/datatables; \
	echo "Processing vendor: $$VENDOR_NAME"; \
	\
	if [ ! -d "$$SRC_DIR" ]; then \
		echo "  -> ERROR: $$SRC_DIR not found. Run 'yarn install' first."; \
		exit 1; \
	fi; \
	\
	echo "  -> for $$VENDOR_NAME"; \
	rm -rf $$DEST_DIR; \
	mkdir -p $$DEST_DIR; \
	if [ "$$VENDOR_NAME" = "datatables" ]; then \
		if [ -d "$$SRC_DIR/media" ]; then \
			cp -r $$SRC_DIR/media/* $$DEST_DIR/; \
		fi; \
	elif echo "$$VENDOR_NAME" | grep -q "datatables"; then \
		echo "  -> [CASE: datatables] Matched! Copying JS/CSS..."; \
		mkdir -p $$DATATABLES_DIR/js $$DATATABLES_DIR/css $$DATATABLES_DIR/images; \
		if [ -d "$$SRC_DIR/js" ]; then \
			cp $$SRC_DIR/js/*.js $$DATATABLES_DIR/js/ 2>/dev/null || true; \
		fi; \
		if [ -d "$$SRC_DIR/css" ]; then \
			cp $$SRC_DIR/css/*.css $$DATATABLES_DIR/css/ 2>/dev/null || true; \
		fi; \
		if [ -d "$$SRC_DIR/images" ]; then \
			cp $$SRC_DIR/images/* $$DATATABLES_DIR/images/ 2>/dev/null || true; \
		fi; \
		rm -rf $$DEST_DIR; \
	elif [ -d "$$SRC_DIR/dist" ]; then \
		echo "  -> Copying 'dist' folder..."; \
		if [ "$$VENDOR_NAME" = "jquery-ui" ]; then \
			echo "  -> Copying 'themes' folder..."; \
			cp -r $$SRC_DIR/dist/themes/base/* $$DEST_DIR/; \
		elif [ "$$VENDOR_NAME" = "metismenu" ]; then \
			DEST_DIR=$(STATIC_DIR)/metisMenu; \
			mkdir -p $$DEST_DIR; \
		fi; \
		cp -r $$SRC_DIR/dist/* $$DEST_DIR/; \
		if [ "$$VENDOR_NAME" = "jquery-easing" ]; then \
			for f in $$DEST_DIR/*.js*; do \
				mv "$$f" "$$(echo "$$f" | sed -E 's/\.([0-9]+\.[0-9]+)\.umd/.umd/; s/\.umd//')" ; \
			done; \
		fi; \
	elif [ -d "$$SRC_DIR/umd" ]; then \
		echo "  -> Copying 'umd' folder..."; \
		cp -r $$SRC_DIR/umd $$DEST_DIR/; \
	elif ls $$SRC_DIR/*.min.js >/dev/null 2>&1; then \
		echo "  -> Copying root-level files (*.min.js only)..."; \
		cp $$SRC_DIR/*.min.js $$DEST_DIR/; \
	elif [ -d "$$SRC_DIR/js" ]; then \
		echo "  -> Copying js/* and cs/* ..."; \
		cp -r $$SRC_DIR/js $$DEST_DIR/; \
		if [ -d "$$SRC_DIR/css" ]; then \
			cp -r $$SRC_DIR/css $$DEST_DIR/; \
		fi ;\
		if [ -d "$$SRC_DIR/webfonts" ]; then \
			cp -r $$SRC_DIR/webfonts $$DEST_DIR/; \
		fi ;\
	else \
		echo "  -> WARNING: No standard dist folder found."; \
		find $SRC_DIR -maxdepth 1 -type f \( -name "*.js" -o -name "*.css" -o -name "*.map" \) -exec cp {} $DEST_DIR/ \; 2>/dev/null || true; \
	fi \



