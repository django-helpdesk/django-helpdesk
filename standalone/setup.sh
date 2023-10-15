#!/bin/sh

# if docker.env does not exist create it from the template
if [ ! -f docker.env ]; then
    cp docker.env.template docker.env
    echo "DJANGO_HELPDESK_SECRET_KEY="$(mcookie) >> docker.env
    echo "POSTGRES_PASSWORD="$(mcookie) >> docker.env
fi
