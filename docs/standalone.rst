Django-Helpdesk Standalone Installation
=======================================

Installation
------------

1. Clone the django-helpdesk repository:

   .. code-block:: bash
   
    git clone git@github.com:django-helpdesk/django-helpdesk.git

2. Go to the standalone helpdesk installation directory:

   .. code-block:: bash
   
    cd django-helpdesk/standalone

3. Execute the installation script:
   
   .. code-block:: bash
   
    ./setup.sh

4. Start the services:

   .. code-block:: bash
   
    docker-compose up

Creating an Admin User
----------------------

1. List the running containers:

   .. code-block:: bash
   
    docker ps

2. Execute into the `standalone-django-helpdesk-1` container:

   .. code-block:: bash

    docker exec -it standalone-django-helpdesk-1 bash

3. Change directory to the application's root:

   .. code-block:: bash
   
    cd /opt/django-helpdesk/standalone

4. Create a superuser:

   .. code-block:: bash
   
    python3 manage.py createsuperuser

5. Visit `localhost:80` in your browser to access the server. Navigate to the `/admin` URL to set up new users. Ensure to configure the "Site" in the admin section for ticket email URLs to function correctly.

Configuration for Production Use
--------------------------------

1. Update the `Caddyfile` to replace the `localhost` URL with your desired production URL.

2. Modify the `docker-compose` file to adjust the paths. By default, files are stored in `/tmp`.

3. For custom configurations, bindmount a `local_settings.py` into `/opt/django-helpdesk/standalone/config/local_settings.py`.

4. To customize the logo in the top-left corner of the helpdesk:

   .. code-block:: html
   
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

AWS SES Email Configuration
---------------------------

An example `local_settings` configuration for utilizing AWS SES for email:

.. code-block:: python

    from .settings import *
    import os

    DEFAULT_FROM_EMAIL = "support@bitswan.space"
    SERVER_EMAIL = "support@bitswan.space"
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    EMAIL_BACKEND = "django_ses.SESBackend"
    AWS_SES_REGION_NAME = "eu-west-1"
    AWS_SES_REGION_ENDPOINT = "email.eu-west-1.amazonaws.com"
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

To integrate `django-ses`, bindmount a file to `/opt/extra-dependencies.txt` containing:

.. code-block:: text

    django-ses

Make sure you update the `docker.env` file with the necessary secrets.


S3 base attachment support
---------------------------

Working from the previous SES example we add the following to `local_settings`:

.. code-block:: python

    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "eu-central-1")
    AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "bitswan-helpdesk-attachments")
    AWS_QUERYSTRING_AUTH = os.environ.get("AWS_QUERYSTRING_AUTH", True)
    AWS_QUERYSTRING_EXPIRE = os.environ.get(
        "AWS_QUERYSTRING_EXPIRE", 60 * 60
    )
    AWS_DEFAULT_ACL = "private"

    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

To integrate `django-ses`, bindmount a file to `/opt/extra-dependencies.txt` containing:

.. code-block:: text

    django-storages
    boto3
