#!/bin/sh
# if docker.env does not exist create it from the template
if [ ! -f docker.env ]; then
  # try using openssl for random string generator for cross platform usability
  which openssl
  if [ $?==0 ]; then
    key1=$(openssl rand -base64 15)
    key2=$(openssl rand -base64 15)
  else
    # try mcookie which is generally only available on linux distros
    which mcookie
    if [ $?==0 ]; then
      key1=$(mcookie)
      key2=$(mcookie)
    fi
  fi
  if [ ! -z $key1 ]; then
    cp docker.env.template docker.env
    echo "DJANGO_HELPDESK_SECRET_KEY="$key1 >> docker.env
    echo "POSTGRES_PASSWORD="$key1 >> docker.env
  else
    echo "Failed to find a program to generate secret keys."
    echo "You will have to manually update the docker.env with values for DJANGO_HELPDESK_SECRET_KEY"
  fi
fi

