# --- Stage 1: Build frontend assets ---
FROM node:26 AS frontend-builder

# Copy source and build static assets
WORKDIR /app

COPY django-helpdesk/ .

# Enable Corepack to use the defined packageManager in package.json
RUN npm install -g corepack # no longer packaged by defaults as of node 26
RUN corepack enable
# Install dependencies
RUN yarn install
COPY . .
RUN yarn build:static

# --- Stage 2: Main Django image ---
FROM python:3.15-slim-bookworm AS app
LABEL src=https://github.com/django-helpdesk/django-helpdesk
RUN apt-get update && apt-get install -yqq \
   postgresql-common \
   postgresql-client \
   cron \
   git \
   && rm -rf /var/lib/apt/lists/* 

# Copy directories
COPY django-helpdesk/src/ /opt/django-helpdesk/src/
COPY django-helpdesk/dockerized/ /opt/django-helpdesk/dockerized/
COPY --from=frontend-builder /app/src/helpdesk/static/helpdesk/vendor /opt/django-helpdesk/src/helpdesk/static/helpdesk/vendor

# Copy files
COPY django-helpdesk/pyproject.toml /opt/django-helpdesk/
COPY django-helpdesk/README.rst /opt/django-helpdesk/

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN pip3 install --upgrade pip
RUN pip3 install packaging
WORKDIR /opt/django-helpdesk

ENV UV_SYSTEM_PYTHON=1
RUN uv sync
RUN uv pip install -r /opt/django-helpdesk/dockerized/requirements.txt

WORKDIR /opt/django-helpdesk/dockerized
ENV DJANGO_SETTINGS_MODULE=dockerized.config.settings
ENV PYTHONPATH=/opt/django-helpdesk/src:/opt/django-helpdesk

RUN DJANGO_HELPDESK_SECRET_KEY=foo python3 manage.py collectstatic --noinput

RUN echo "* * * * * root . /etc/env && /usr/local/bin/python3 /opt/django-helpdesk/dockerized/manage.py get_email >> /var/log/cron.log 2>&1" > /etc/crontab
RUN chmod 0644 /etc/crontab
# Make sure entrypoint script is executable
RUN chmod +x /opt/django-helpdesk/dockerized/entrypoint.sh
ENTRYPOINT [ "/opt/django-helpdesk/dockerized/entrypoint.sh" ]
