Django-helpdesk standalone
-------------------------------

This is a standalone installation of Django-helpdesk allowing you to run django-helpdesk as a production standalone application in docker.

To install run `setup.sh` and then `docker-compose up` in this directory.


To create an admin user exec into the newly created container

    docker ps
    docker exec -it standalone-web-1 bash

In the container cd to `/opt/django-helpdesk/standalone` and run

    python3 manage.py createsuperuser

You should now be able to log in to the server by visiting `localhost:80`. You will also need to access the `/admin` url to set up new users.

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
