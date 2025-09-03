#see github workflows for docker build command
FROM python:3.11-slim-bullseye
LABEL src=https://github.com/django-helpdesk/django-helpdesk
RUN apt-get update
RUN apt-get install -yqq \
   postgresql-common \
   postgresql-client \
   cron \
   git \
   dos2unix

# Copy everything needed
COPY . /opt/django-helpdesk/

# Fix line endings for shell scripts
RUN dos2unix /opt/django-helpdesk/standalone/entrypoint.sh
RUN chmod +x /opt/django-helpdesk/standalone/entrypoint.sh
RUN pip install -r /opt/django-helpdesk/standalone/requirements-extras.txt
RUN pip install packaging
RUN pip install --upgrade pip
WORKDIR /opt/django-helpdesk

# Install standalone requirements only
RUN pip install -r standalone/requirements.txt

WORKDIR /opt/django-helpdesk/standalone
ENV DJANGO_SETTINGS_MODULE=standalone.config.settings
ENV PYTHONPATH=/opt/django-helpdesk/src:/opt/django-helpdesk

RUN DJANGO_HELPDESK_SECRET_KEY=foo python3 manage.py collectstatic --noinput

RUN echo "* * * * * root . /etc/env && /usr/local/bin/python3 /opt/django-helpdesk/standalone/manage.py get_email >> /var/log/cron.log 2>&1" > /etc/crontab
RUN chmod 0644 /etc/crontab
ENTRYPOINT ["sh", "/opt/django-helpdesk/standalone/entrypoint.sh"]