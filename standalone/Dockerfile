#see github workflows for docker build command
FROM python:3.11-slim-bullseye
LABEL src=https://github.com/django-helpdesk/django-helpdesk
RUN apt-get update
RUN apt-get install -yqq \
   postgresql-common \
   postgresql-client \
   cron \
   git

# Copy directories
COPY django-helpdesk/src/ /opt/django-helpdesk/src/
COPY django-helpdesk/standalone/ /opt/django-helpdesk/standalone/

# Copy files
COPY django-helpdesk/pyproject.toml /opt/django-helpdesk/
COPY django-helpdesk/README.rst /opt/django-helpdesk/

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN pip3 install --upgrade pip
RUN pip3 install packaging
WORKDIR /opt/django-helpdesk
ENV UV_SYSTEM_PYTHON=1
RUN uv sync 
RUN uv pip install -r /opt/django-helpdesk/standalone/requirements.txt
RUN DJANGO_HELPDESK_SECRET_KEY=foo python3 standalone/manage.py collectstatic

RUN echo "* * * * * root . /etc/env && /usr/local/bin/python3 /opt/django-helpdesk/standalone/manage.py get_email >> /var/log/cron.log 2>&1" > /etc/crontab
RUN chmod 0644 /etc/crontab
ENTRYPOINT sh /opt/django-helpdesk/standalone/entrypoint.sh
