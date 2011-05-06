django-helpdesk - A Django powered ticket tracker for small enterprise.
=======================================================================

Copyright 2009-11 Jutda and Ross Poulton. All Rights Reserved. See LICENSE for details.

django-helpdesk was formerly known as Jutda Helpdesk, named after the 
company who originally created it. As of January 2011 the name has been 
changed to reflect what it really is: a Django-powered ticket tracker with
contributors reaching far beyond Jutda.

Complete documentation is available in the docs/ directory, or online at http://django-helpdesk.readthedocs.org/.

You can see a demo installation at http://demo.jutdahelpdesk.com

Licensing
=========

See the file 'LICENSE' for licensing terms. Note that django-helpdesk is 
distributed with 3rd party products which have their own licenses. See 
LICENSE.3RDPARTY for license terms for included packages.

Dependencies (pre-flight checklist)
===================================

1. Python 2.4+ 
2. Django (1.2 or newer)
3. South for database migrations (highly recommended, but not required). Download from http://south.aeracode.org/
4. An existing WORKING Django project with database etc. If you
   cannot log into the Admin, you won't get this product working.

**NOTE REGARDING SQLITE AND SEARCHING:**
If you use sqlite as your database, the search function will not work as
effectively as it will with other databases due to its inability to do
case-insensitive searches. It's recommended that you use PostgreSQL or MySQL
if possible. For more information, see this note in the Django documentation:
http://docs.djangoproject.com/en/dev/ref/databases/#sqlite-string-matching

When you try to do a keyword search using sqlite, a message will be displayed
to alert you to this shortcoming. There is no way around it, sorry.

Upgrading from previous versions
================================

We highly recommend that you use South (available 
from http://south.aeracode.org/) to assist with management of database schema
changes. 

If you are upgrading from a previous version that did NOT use South for 
migrations (i.e. prior to April 2011) then you will need to 'fake' the first
migration::

    python manage.py migrate helpdesk 0001 --fake

If you are upgrading from a previous version of django-helpdesk that DID use
South, simply download an up to date version of the code base (eg by using 
`git pull`) then migrate the database::

    python manage.py migrate helpdesk --db-dry-run # DB untouched
    python manage.py migrate helpdesk 

Lastly, restart your web server software (eg Apache) or FastCGI instance, to 
ensure the latest changes are in use.

You can continue to the 'Initial Configuration' area, if needed.

Django 1.2.x and latest version of django-helpdesk
==================================================

If you are running Django 1.2.x then you will need to install django-staticfiles
(http://pypi.python.org/pypi/django-staticfiles/) and add the following to your 
existing `settings.py` and `urls.py` files:

settings.py::
    MEDIA_ROOT = '/var/www/media/'
    MEDIA_URL = '/media/'
    STATIC_ROOT = '/var/www/static/'
    STATIC_URL = '/static/'

    INSTALLED_APPS = (
        'staticfiles',             
    )

    TEMPLATE_CONTEXT_PROCESSORS = (
        'staticfiles.context_processors.static',
    )

urls.py::
    from staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()

Once those changes are made, run the following commands to take a copy of the static files::

    $ cd /var/www
    $ mkdir static
    $ cd static
    $ ln -sf /path/to/helpdesk/static/helpdesk/ helpdesk

Installation
============

``pip install django-helpdesk``

For further installation information see docs/install.html and docs/configuration.html

Internationalisation
====================

If you want to help translate django-helpdesk into languages other than English, we encourage you to make use of our Transifex project.

http://www.transifex.net/projects/p/django-helpdesk/resource/core/

Feel free to request access to contribute your translations.
