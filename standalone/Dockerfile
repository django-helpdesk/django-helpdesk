#see github workflows for docker build command
FROM python:3.11-slim-bullseye
LABEL src=https://github.com/django-helpdesk/django-helpdesk
RUN apt-get update
RUN apt-get install -yqq \
   postgresql-common \
   postgresql-client \
   cron \
   git
 
COPY django-helpdesk /opt/django-helpdesk
RUN pip3 install --upgrade pip
RUN pip3 install packaging
RUN pip3 install -r /opt/django-helpdesk/requirements.txt
RUN pip3 install -r /opt/django-helpdesk/standalone/requirements.txt
WORKDIR /opt/django-helpdesk
RUN pip3 install -e .
RUN DJANGO_HELPDESK_SECRET_KEY=foo python3 standalone/manage.py collectstatic

RUN echo "* * * * * root . /etc/env && /usr/local/bin/python3 /opt/django-helpdesk/standalone/manage.py get_email >> /var/log/cron.log 2>&1" > /etc/crontab
RUN chmod 0644 /etc/crontab
ENTRYPOINT sh /opt/django-helpdesk/standalone/entrypoint.sh
