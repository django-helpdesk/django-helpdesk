#!/usr/bin/env bash
# Build script for the demo hosted on Render, see demodesk/render.yaml.
set -o errexit

cd "$(dirname "$0")/.."

# Vendored JS/CSS (Bootstrap, jQuery, DataTables...) are not committed and
# must be in place before the package is installed.
npm install --no-audit --no-fund --no-package-lock
make static-vendor

pip install . gunicorn whitenoise

python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py loaddata emailtemplate.json
# The password for the "admin" user is 'Pa33w0rd'.
python manage.py loaddata demo.json
