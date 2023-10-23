FROM python:3.10-slim-bullseye
LABEL src=https://github.com/django-helpdesk/django-helpdesk
RUN apt-get update
RUN apt-get install -yqq \
   postgresql-common \
   postgresql-client \
   cron \
   git
COPY requirements.txt /opt/django-helpdesk/requirements.txt
COPY standalone/extra-requirements.txt /opt/django-helpdesk/standalone/extra-requirements.txt
RUN pip3 install -r /opt/django-helpdesk/requirements.txt
RUN pip3 install -r /opt/django-helpdesk/standalone/extra-requirements.txt
COPY . /opt/django-helpdesk
WORKDIR /opt/django-helpdesk
RUN pip3 install -e .
RUN DJANGO_HELPDESK_SECRET_KEY=foo python3 standalone/manage.py collectstatic

RUN echo "* * * * * root . /etc/env && /usr/local/bin/python3 /opt/django-helpdesk/standalone/manage.py get_email >> /var/log/cron.log 2>&1" > /etc/crontab
RUN chmod 0644 /etc/crontab
ENTRYPOINT sh /opt/django-helpdesk/standalone/entrypoint.sh