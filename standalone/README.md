Django-helpdesk standalone
-------------------------------

This is a standalone installation of Django-helpdesk allowing you to run django-helpdesk as a production standalone application in docker.

To install run `setup.sh` and then `docker-compose up` in this directory.


To create an admin user exec into the newly created container

    docker ps
    docker exec -it standalone-django-helpdesk-1 bash

In the container cd to `/opt/django-helpdesk/standalone` and run

    python3 manage.py createsuperuser

You should now be able to log in to the server by visiting `localhost:80`. You will also need to access the `/admin` url to set up new users. You also need to set the Site in the admin so that URLs in ticket emails will work.

Configuration for production use
--------------------------------------

For production use you will need to change the URL from `localhost` in the `Caddyfile`. You will also need to update the `docker-compose` file to fix paths. By default all files are stored in `/tmp`.

You should be able to set custom settings by bindmounting a `local_settings.py` file into `/opt/django-helpdesk/standalone/config/local_settings.py`

You can change the logo at the top left  of the helpdesk by bindmounting a file into `/opt/django-helpdesk/helpdesk/templates/helpdesk/custom_navigation_header.html` with contents like:

```
<style>
 .navbar-brand {
     background: url("https://www.libertyaces.com/files/liberty-logo.png") no-repeat;
     background-size: auto;
     width: 320px;
     background-size: contain;
     height: 40px;
     text-align: right;
 }
</style>
```

Here is an example `local_settings` file for using AWS SES for sending emails:

```
import os

DEFAULT_FROM_EMAIL = "support@bitswan.space"
SERVER_EMAIL = "support@bitswan.space"
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
EMAIL_BACKEND = "django_ses.SESBackend"
AWS_SES_REGION_NAME = "eu-west-1"
AWS_SES_REGION_ENDPOINT = "email.eu-west-1.amazonaws.com"
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
```

In this case you'll also have to bindmout a file to `/opt/extra-dependencies.txt` with the contents:

```
django-ses
```

You would of course also have to edit docker.env to add your secrets.
