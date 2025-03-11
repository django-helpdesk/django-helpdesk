Standalone Installation
=======================================

You can find standalone docker images at `djangohelpdesk/standalone:latest <https://hub.docker.com/r/djangohelpdesk/standalone/tags>`_.

You will also find an alternative `standalone-extras <https://hub.docker.com/r/djangohelpdesk/standalone-extras>`_ image with extra libraries needed to use the standalone image on cloud platforms such as AWS. You can find a full list of extra packages included in the extra's image `here <https://github.com/django-helpdesk/django-helpdesk/blob/main/standalone/requirements-extras.txt>`_.

Installation using docker compose
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

   Set the POSTGRES major version if you are deploying to an existing POSTGRES instance other than the default shown within the docker-compose file. For example:

   .. code-block:: bash

      export POSTGRES_MAJOR_VERSION=15
   
4. Start the services:

   .. code-block:: bash
   
    docker compose up


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

2. For custom configurations, bindmount a `local_settings.py` into `/opt/django-helpdesk/standalone/config/local_settings.py`.

3. To customize the logo in the top-left corner of the helpdesk:

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

# Environment Variables Reference

## Database Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| ```POSTGRES_DB``` | ```postgres``` | Database name |
| ```POSTGRES_USER``` | ```postgres``` | Database user |
| ```POSTGRES_PASSWORD``` | ```postgres``` | Database password |
| ```POSTGRES_HOST``` | ```postgres``` | Database host |
| ```POSTGRES_PORT``` | ```5432``` | Database port |

## Email Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| ```DEFAULT_FROM_EMAIL``` | ```example@example.com``` | Default sender email address |
| ```SERVER_EMAIL``` | ```example@example.com``` | Server email address |
| ```EMAIL_HOST``` | *Required* | SMTP server host |
| ```EMAIL_PORT``` | *Required* | SMTP server port |

## Static Files
| Variable | Default | Description |
|----------|---------|-------------|
| ```DJANGO_HELPDESK_STATIC_ROOT``` | ```./static``` | Static files root directory |
| ```DJANGO_HELPDESK_STATIC_URL``` | ```/static/``` | Static files URL prefix |

## Security Settings
| Variable | Default | Description |
|----------|---------|-------------|
| ```DJANGO_HELPDESK_SECRET_KEY``` | *Required* | Django secret key |
| ```DJANGO_HELPDESK_ALLOWED_HOSTS``` | ```*, localhost, 0.0.0.0``` | Comma-separated list of allowed hosts |

## Helpdesk Core Settings
| Variable | Default | Description |
|----------|---------|-------------|
| ```HELPDESK_USE_EMAIL_AS_SUBMITTER``` | ```True``` | Use email as ticket submitter |
| ```HELPDESK_EMAIL_ON_TICKET_ASSIGN``` | ```True``` | Send email on ticket assignment |
| ```HELPDESK_EMAIL_ON_TICKET_CHANGE``` | ```True``` | Send email on ticket changes |
| ```HELPDESK_LOGIN_VIEW_TICKETLIST``` | ```True``` | Show ticket list after login |
| ```HELPDESK_PRESET_REPLIES``` | ```True``` | Enable preset replies |
| ```HELPDESK_TICKETS_PER_PAGE``` | ```25``` | Number of tickets per page |

## Public Portal Settings
| Variable | Default | Description |
|----------|---------|-------------|
| ```HELPDESK_PUBLIC_ENABLED``` | ```True``` | Enable public web portal |
| ```HELPDESK_VIEW_A_TICKET_PUBLIC``` | ```True``` | Allow public ticket viewing |
| ```HELPDESK_SUBMIT_A_TICKET_PUBLIC``` | ```True``` | Allow public ticket submission |
| ```HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT``` | ```False``` | Redirect to login instead of public portal |

## Feature Toggles
| Variable | Default | Description |
|----------|---------|-------------|
| ```HELPDESK_KB_ENABLED``` | ```True``` | Enable knowledge base |
| ```HELPDESK_TICKETS_TIMELINE_ENABLED``` | ```True``` | Enable ticket timeline |
| ```HELPDESK_SHOW_CHANGE_PASSWORD``` | ```True``` | Allow users to change passwords |



AWS SES Email Configuration
---------------------------

You will need to use the standalone-extras image for SES support.

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

Make sure you update the `docker.env` file with the necessary secrets.


S3 base attachment support
---------------------------

You will need to use the standalone-extras image for S3 support.

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
