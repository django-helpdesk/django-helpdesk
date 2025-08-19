#!/bin/bash


# don't forget to add this script to the /etc/crontab:
#
# */1 * * * * username /home/username/django/project/poll_helpdesk_email_queues.sh >> /tmp/foo.log 2>&1 

# set your django and project paths here
PATHTODJANGO="/home/username/django/libraries/lib/python"
PATHTOPROJECT="/home/username/django/project/"


export PYTHONPATH=$PYTHONPATH:$PATHTODJANGO:$PATHTOPROJECT:

cd $PATHTOPROJECT 
/usr/bin/python manage.py get_email


